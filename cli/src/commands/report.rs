//! The machine-readable shapes of a `vson validate` run: `json` and `sarif`.
//!
//! `text` is for a person at a terminal and is unchanged. These two are for a
//! build. The record set behind both is the same one `tools/validate_report.py`
//! emits — one [`Finding`] per violation, with the shape, the focus node, the
//! result path and the severity kept as fields rather than rendered into a
//! sentence — plus the source position this side resolves
//! ([`super::sourcemap`]). docs/vson.md §5.16 is the normative description of
//! both; this module is the implementation of that clause and must not drift
//! from it.
//!
//! **Why SARIF.** It is the one report format GitHub, GitLab and every code
//! scanner already read, so a violation becomes an annotation on the offending
//! line without anybody writing a parser. What is emitted is SARIF 2.1.0
//! (OASIS, March 2020) with the required properties present and no optional
//! extension: `version` and `runs` on the log, `tool.driver.name` on the run,
//! and `message.text` on every result — with `ruleId`, `level` and `locations`
//! filled in as well, because those three are what a scanner needs to group,
//! rank and place a finding even though the schema leaves them optional.
//!
//! **What a passing run emits.** A conformant document produces a report with
//! zero findings, not an empty file: a caller that cannot tell "clean" from
//! "the tool never ran" is back where it started.

use super::sourcemap::{Located, SourceMap, Syntax};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

/// The `--format json` document version. Bumped when a field is removed or its
/// meaning changes; adding a field is not a break (docs/vson.md §5.16).
pub const REPORT_VERSION: &str = "vson-validate/1";

/// The record version `tools/validate_report.py` announces. Checked rather than
/// assumed: a binary reading records from an older checkout's `tools/` — the
/// `--home` case — must say so instead of silently mis-shaping them.
pub const RECORDS_VERSION: &str = "vson-validate-records/1";

const SARIF_SCHEMA: &str =
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json";
const INFORMATION_URI: &str = "https://github.com/yamancan/visual-scene-ontology";

/// One violation, as the Python reporter emits it plus the position this side
/// resolves. Field order is the order both formats print.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    /// Which gate reported it: `shacl`, `owl-consistency` or `c2`.
    pub gate: String,
    /// A stable identifier to group by — `vson/shacl/<ShapeName>` and friends.
    pub rule: String,
    /// `violation`, `warning` or `info`, from `sh:resultSeverity`.
    pub severity: String,
    pub message: String,
    pub shape: Option<String>,
    pub constraint: Option<String>,
    pub focus_node: Option<String>,
    pub result_path: Option<String>,
    pub value: Option<String>,
    /// Filled in here, never by the reporter: it reads transpiled Turtle and
    /// has no sight of the source the author wrote.
    #[serde(default, skip_deserializing)]
    pub location: Option<Located>,
}

impl Finding {
    /// Attach the source position, if one can be established.
    ///
    /// The focus node is the anchor when there is one. A C2 orphan term has no
    /// focus node — the finding is about a *name* the document uses — so the
    /// term itself is looked up instead.
    fn locate(&mut self, map: &SourceMap) {
        self.location = match (&self.focus_node, &self.value) {
            (Some(node), _) => map.locate_node(node),
            (None, Some(term)) if self.gate == "c2" => map.locate_term(term),
            _ => None,
        };
    }
}

/// What the Python reporter returns for one document.
#[derive(Debug, Deserialize)]
pub struct Records {
    pub report: String,
    pub conforms: bool,
    pub gate: Option<String>,
    pub findings: Vec<Finding>,
}

/// One input's outcome.
#[derive(Debug, Serialize)]
pub struct FileReport {
    /// The path the *user* named — `-` for stdin, never the temp file the gates
    /// actually read.
    pub path: String,
    pub syntax: &'static str,
    pub conforms: bool,
    /// The first gate that failed, or null.
    pub gate: Option<String>,
    pub findings: Vec<Finding>,
}

impl FileReport {
    pub fn new(path: String, records: Records, map: Option<&SourceMap>) -> Self {
        let mut findings = records.findings;
        if let Some(map) = map {
            for finding in &mut findings {
                finding.locate(map);
            }
        }
        FileReport {
            path,
            syntax: map.map_or(Syntax::Turtle, SourceMap::syntax).as_str(),
            conforms: records.conforms,
            gate: records.gate,
            findings,
        }
    }
}

#[derive(Debug, Serialize)]
struct Tool {
    name: &'static str,
    version: &'static str,
}

#[derive(Debug, Serialize)]
struct Summary {
    files: usize,
    conformant: usize,
    findings: usize,
}

/// The whole run, as `--format json` prints it.
#[derive(Debug, Serialize)]
pub struct Report {
    report: &'static str,
    tool: Tool,
    /// Which shapes file decided C3. Only `strict` decides conformance
    /// (docs/vson.md §6.1).
    profile: &'static str,
    conforms: bool,
    summary: Summary,
    files: Vec<FileReport>,
}

impl Report {
    pub fn new(profile: &'static str, files: Vec<FileReport>) -> Self {
        let conformant = files.iter().filter(|f| f.conforms).count();
        let findings = files.iter().map(|f| f.findings.len()).sum();
        Report {
            report: REPORT_VERSION,
            tool: Tool {
                name: "vson",
                version: env!("CARGO_PKG_VERSION"),
            },
            profile,
            conforms: conformant == files.len(),
            summary: Summary {
                files: files.len(),
                conformant,
                findings,
            },
            files,
        }
    }

    pub fn conforms(&self) -> bool {
        self.conforms
    }

    /// `--format json`.
    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("a Report always serializes") + "\n"
    }

    /// `--format sarif` — one run, one result per finding.
    pub fn to_sarif(&self) -> String {
        let mut rules: Vec<Value> = Vec::new();
        let mut rule_index: Vec<&str> = Vec::new();
        let mut results: Vec<Value> = Vec::new();

        for file in &self.files {
            for finding in &file.findings {
                let index = match rule_index.iter().position(|id| *id == finding.rule) {
                    Some(index) => index,
                    None => {
                        rule_index.push(&finding.rule);
                        rules.push(rule_descriptor(finding));
                        rule_index.len() - 1
                    }
                };
                results.push(result_for(file, finding, index));
            }
        }

        let log = json!({
            "$schema": SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "vson",
                        "version": env!("CARGO_PKG_VERSION"),
                        "informationUri": INFORMATION_URI,
                        "rules": rules,
                    }
                },
                // Declared, not defaulted: `sourcemap` counts columns in
                // Unicode scalar values, and SARIF's own default is UTF-16 code
                // units — a silent difference on any line with an emoji.
                "columnKind": "unicodeCodePoints",
                "results": results,
            }]
        });
        serde_json::to_string_pretty(&log).expect("a SARIF log always serializes") + "\n"
    }
}

/// The `reportingDescriptor` for a rule, from the first finding that used it.
fn rule_descriptor(finding: &Finding) -> Value {
    let mut descriptor = json!({
        "id": finding.rule,
        "name": finding.rule.rsplit('/').next().unwrap_or(&finding.rule),
        "shortDescription": { "text": finding.message },
        "properties": { "gate": finding.gate },
    });
    // The one link that is real: a VSON shape IRI dereferences to the shapes
    // file. No help URI is invented for the gates that have none.
    if let Some(shape) = &finding.shape {
        descriptor["helpUri"] = json!(shape);
    }
    descriptor
}

fn result_for(file: &FileReport, finding: &Finding, rule_index: usize) -> Value {
    let mut physical = json!({
        "artifactLocation": { "uri": uri_for(&file.path) }
    });
    if let Some(at) = &finding.location {
        physical["region"] = json!({ "startLine": at.line, "startColumn": at.column });
    }
    let mut properties = json!({
        "gate": finding.gate,
        "severity": finding.severity,
    });
    for (key, value) in [
        ("focusNode", &finding.focus_node),
        ("resultPath", &finding.result_path),
        ("shape", &finding.shape),
        ("constraint", &finding.constraint),
        ("value", &finding.value),
    ] {
        if let Some(value) = value {
            properties[key] = json!(value);
        }
    }
    if let Some(at) = &finding.location {
        properties["resolvedFrom"] = json!(at.resolved_from);
    }
    json!({
        "ruleId": finding.rule,
        "ruleIndex": rule_index,
        "level": level_for(&finding.severity),
        "message": { "text": finding.message },
        "locations": [{ "physicalLocation": physical }],
        "properties": properties,
    })
}

/// SARIF levels are a closed set of four; SHACL severities are three. Anything
/// unrecognised lands on `warning` — SARIF's own default — rather than being
/// promoted to an error nobody asked for.
fn level_for(severity: &str) -> &'static str {
    match severity {
        "violation" => "error",
        "info" => "note",
        _ => "warning",
    }
}

/// A SARIF `artifactLocation.uri`. Relative, with `./` stripped, because that
/// is what a scanner joins against the repository root; an absolute path is
/// left alone rather than mangled into a wrong relative one.
fn uri_for(path: &str) -> String {
    let path = path.replace('\\', "/");
    path.strip_prefix("./").unwrap_or(&path).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn finding() -> Finding {
        Finding {
            gate: "shacl".into(),
            rule: "vson/shacl/DirectionalNeedsViewerShape".into(),
            severity: "violation".into(),
            message: "Directional spatial facts require exactly one vso:viewer".into(),
            shape: Some("https://w3id.org/vson/v1/shapes#DirectionalNeedsViewerShape".into()),
            constraint: Some("http://www.w3.org/ns/shacl#MinCountConstraintComponent".into()),
            focus_node: Some("https://example.org/scenes/anonymous#sf".into()),
            result_path: Some("https://w3id.org/vson/v1/ontology#viewer".into()),
            value: None,
            location: Some(Located {
                line: 11,
                column: 14,
                anchor: "sf".into(),
                resolved_from: "penman-variable",
            }),
        }
    }

    fn one_bad_file() -> Report {
        Report::new(
            "strict",
            vec![FileReport {
                path: "./tests/fixtures/bad.vson".into(),
                syntax: "penman",
                conforms: false,
                gate: Some("shacl".into()),
                findings: vec![finding()],
            }],
        )
    }

    #[test]
    fn sarif_carries_every_property_a_scanner_requires() {
        let log: Value = serde_json::from_str(&one_bad_file().to_sarif()).unwrap();
        assert_eq!(log["version"], "2.1.0");
        let run = &log["runs"][0];
        assert_eq!(run["tool"]["driver"]["name"], "vson");
        let result = &run["results"][0];
        assert_eq!(result["ruleId"], "vson/shacl/DirectionalNeedsViewerShape");
        assert_eq!(result["level"], "error");
        assert!(result["message"]["text"].is_string());
        let region = &result["locations"][0]["physicalLocation"]["region"];
        assert_eq!(region["startLine"], 11);
        assert_eq!(region["startColumn"], 14);
        // The rule the result points at must exist at the index it names.
        let index = result["ruleIndex"].as_u64().unwrap() as usize;
        assert_eq!(
            run["tool"]["driver"]["rules"][index]["id"],
            result["ruleId"]
        );
    }

    #[test]
    fn a_sarif_uri_is_repository_relative() {
        let log: Value = serde_json::from_str(&one_bad_file().to_sarif()).unwrap();
        let uri = &log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
            ["artifactLocation"]["uri"];
        assert_eq!(uri, "tests/fixtures/bad.vson", "the leading ./ is stripped");
    }

    #[test]
    fn a_clean_run_is_a_report_with_no_results_not_an_empty_one() {
        let report = Report::new(
            "strict",
            vec![FileReport {
                path: "examples/throne_room.ttl".into(),
                syntax: "turtle",
                conforms: true,
                gate: None,
                findings: vec![],
            }],
        );
        assert!(report.conforms());
        let log: Value = serde_json::from_str(&report.to_sarif()).unwrap();
        assert_eq!(log["runs"][0]["results"].as_array().unwrap().len(), 0);
        assert_eq!(log["runs"][0]["tool"]["driver"]["name"], "vson");

        let doc: Value = serde_json::from_str(&report.to_json()).unwrap();
        assert_eq!(doc["conforms"], true);
        assert_eq!(doc["summary"]["findings"], 0);
    }

    #[test]
    fn a_finding_with_no_position_still_names_its_file() {
        let mut bare = finding();
        bare.location = None;
        let report = Report::new(
            "strict",
            vec![FileReport {
                path: "scene.ttl".into(),
                syntax: "turtle",
                conforms: false,
                gate: Some("shacl".into()),
                findings: vec![bare],
            }],
        );
        let log: Value = serde_json::from_str(&report.to_sarif()).unwrap();
        let physical = &log["runs"][0]["results"][0]["locations"][0]["physicalLocation"];
        assert_eq!(physical["artifactLocation"]["uri"], "scene.ttl");
        assert!(
            physical.get("region").is_none(),
            "no region is emitted rather than a guessed line 1"
        );
    }

    #[test]
    fn two_findings_of_one_rule_share_one_descriptor() {
        let report = Report::new(
            "strict",
            vec![FileReport {
                path: "a.vson".into(),
                syntax: "penman",
                conforms: false,
                gate: Some("shacl".into()),
                findings: vec![finding(), finding()],
            }],
        );
        let log: Value = serde_json::from_str(&report.to_sarif()).unwrap();
        assert_eq!(
            log["runs"][0]["tool"]["driver"]["rules"]
                .as_array()
                .unwrap()
                .len(),
            1
        );
        assert_eq!(log["runs"][0]["results"].as_array().unwrap().len(), 2);
    }
}

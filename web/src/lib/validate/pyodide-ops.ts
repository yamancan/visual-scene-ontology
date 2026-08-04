// Adapter-free core of the in-browser verification stack, shared by the
// module worker (vson.worker.ts) and the offline Node parity test
// (tests/worker-parity.test.ts). It takes an ALREADY-LOADED pyodide instance,
// writes a repo-shaped filesystem from build-time ?raw imports of the same
// canonical files the CLI reads, installs the committed wheels, and exposes
// the five operations the studio needs: p2t, x2t, validate, caption, fol.
//
// The two-gate validate() mirrors the first two gates of `vson validate`
// (cli/src/commands/validate.rs): Gate 1 is pyshacl over shapes + the
// vso/rcc8/allen ontology trio with inference=rdfs and allow_warnings
// (tools/shacl_helper.py semantics); Gate 2 is the owlrl OWL 2 RL
// disjointness/distinctness check (tools/owlrl_check.py). Like the CLI, Gate 2
// runs only when Gate 1 passes.
//
// The CLI's third gate — C2 vocabulary closure, tools/c2_check.py, added in
// v1.3 — is deliberately NOT here yet. It is one more Python module and one
// more result to render, and the studio's verification panel is shaped around
// two verdicts. Until that lands, this pipeline is a strict subset of the CLI's:
// everything it rejects, the CLI rejects, and a document it passes may still
// fail C2. Nothing in the studio may describe this as running "the same gates
// as vson validate".
//
// Install path: pyodide.loadPackage with EXPLICIT wheel URLs — single path,
// no micropip, no resolver, no index lookup. The wheel list is single-sourced
// from static/pyodide/wheels/wheels.lock.json (sha256-pinned by
// tests/wheels-lock.test.ts), so worker and test install byte-identical
// files from git.

import type { PyodideAPI } from 'pyodide';

// ── repo sources, inlined at build time ────────────────────────────────────
// The exact tree the Python modules expect: `tools.resource` resolves
// repository-relative paths against the directory `tools/` sits in, so the
// routing tables (cli/src/penman/routing-tables.json), shapes/ and ontology/
// must be mounted at those paths beside it, and caption.py reads verbs.json
// beside itself. tools/__init__.py carries that resolver, which is why it is
// mounted rather than left an empty stub. equiv.py and
// skill_check.py are deliberately absent — they serve only `make
// x-skill-check`, never a studio operation.
import toolsInit from '../../../../tools/__init__.py?raw';
import vsonAstPy from '../../../../tools/vson_ast.py?raw';
import shaclHelperPy from '../../../../tools/shacl_helper.py?raw';
import owlrlCheckPy from '../../../../tools/owlrl_check.py?raw';
import penmanInit from '../../../../tools/penman/__init__.py?raw';
import vsonPenmanPy from '../../../../tools/penman/vson_penman.py?raw';
import vsonXInit from '../../../../tools/vson_x/__init__.py?raw';
import vsonXPy from '../../../../tools/vson_x/vson_x.py?raw';
import renderInit from '../../../../tools/render/__init__.py?raw';
import captionPy from '../../../../tools/render/caption.py?raw';
import folPy from '../../../../tools/render/fol.py?raw';
import verbsJson from '../../../../tools/render/verbs.json?raw';
import routingTablesJson from '../../../../cli/src/penman/routing-tables.json?raw';
import shapesTtl from '../../../../shapes/vson-shapes.ttl?raw';
import vsoTtl from '../../../../ontology/vso.ttl?raw';
import rcc8Ttl from '../../../../ontology/rcc8.ttl?raw';
import allenTtl from '../../../../ontology/allen.ttl?raw';

import wheelsLock from '../../../static/pyodide/wheels/wheels.lock.json';

import type { ConformanceReport } from '../types';
import { parseViolationReport } from './report';

/** Where the repo-shaped tree is mounted inside the Pyodide FS. */
export const VSON_HOME = '/vson';

const REPO_FILES: Record<string, string> = {
	'tools/__init__.py': toolsInit,
	'tools/vson_ast.py': vsonAstPy,
	'tools/shacl_helper.py': shaclHelperPy,
	'tools/owlrl_check.py': owlrlCheckPy,
	'tools/penman/__init__.py': penmanInit,
	'tools/penman/vson_penman.py': vsonPenmanPy,
	'tools/vson_x/__init__.py': vsonXInit,
	'tools/vson_x/vson_x.py': vsonXPy,
	'tools/render/__init__.py': renderInit,
	'tools/render/caption.py': captionPy,
	'tools/render/fol.py': folPy,
	'tools/render/verbs.json': verbsJson,
	'cli/src/penman/routing-tables.json': routingTablesJson,
	'shapes/vson-shapes.ttl': shapesTtl,
	'ontology/vso.ttl': vsoTtl,
	'ontology/rcc8.ttl': rcc8Ttl,
	'ontology/allen.ttl': allenTtl
};

/** The committed wheel set, in lock order — the complete offline closure. */
export const WHEEL_FILENAMES: readonly string[] = wheelsLock.wheels.map((w) => w.filename);

/** Same-origin wheel URLs for the browser worker (or fs paths for Node). */
export function wheelUrls(base = '/pyodide/wheels'): string[] {
	return WHEEL_FILENAMES.map((f) => `${base}/${f}`);
}

// ── results ────────────────────────────────────────────────────────────────

export interface GateResult {
	conforms: boolean;
	report: string;
}

export interface ValidateResult {
	/** The CLI verdict: Gate 1 AND Gate 2. */
	conforms: boolean;
	/**
	 * Report text with the same content `vson validate` forwards: the pyshacl
	 * report when Gate 1 fails, the owl-consistency clash lines when Gate 2
	 * fails, empty when both gates pass.
	 */
	report: string;
	gate1: GateResult;
	/** null when Gate 1 already failed — the CLI never runs Gate 2 then. */
	gate2: GateResult | null;
}

/**
 * Fill the envelope's existing ConformanceReport shape (types.ts) through the
 * relocated parseViolationReport — identical to what the adapter-node extract
 * route did, so ConformancePane needs zero changes.
 */
export function toConformanceReport(v: ValidateResult): ConformanceReport {
	const violations = parseViolationReport(v.report);
	return { conforms: v.conforms, ...(violations.length ? { violations } : {}) };
}

export interface VsonOps {
	/** VSON-P (Penman) → VSON-T (Turtle-star). Byte-equal to `vson convert p2t`. */
	p2t(vsonP: string): string;
	/** VSON-X (compact) → VSON-T. Byte-equal to `vson convert x2t`. */
	x2t(vsonX: string): string;
	/**
	 * Two-gate verdict over a VSON-T document. `onGate1` fires with the SHACL
	 * result before the ~2.8s OWL 2 RL closure runs, for progressive UI.
	 */
	validate(turtle: string, onGate1?: (gate1: GateResult) => void): ValidateResult;
	/** Deterministic English caption of a VSON-T graph (tools/render/caption.py). */
	caption(turtle: string): string;
	/** Prolog-style FOL facts of a VSON-T graph (tools/render/fol.py). */
	fol(turtle: string): string;
}

// ── python bootstrap ───────────────────────────────────────────────────────
// Runs once after the wheels are installed. Imports resolve from VSON_HOME on
// sys.path; every op is a top-level function looked up (and cached) as a
// PyProxy. Gate results cross the boundary as JSON strings — no PyProxy
// lifetime to manage.

const BOOTSTRAP = `
import json
import sys

if ${JSON.stringify(VSON_HOME)} not in sys.path:
    sys.path.insert(0, ${JSON.stringify(VSON_HOME)})

import rdflib
from rdflib import OWL

from tools import owlrl_check as _vson_owl
from tools import shacl_helper as _vson_shacl
from tools.penman.vson_penman import to_turtle as _vson_p2t_impl
from tools.render.caption import render as _vson_caption_impl
from tools.render.fol import render as _vson_fol_impl
from tools.vson_x import to_turtle as _vson_x2t_impl


def _vson_graph(ttl):
    g = rdflib.Graph()
    g.parse(data=ttl, format="turtle")
    return g


def _vson_p2t(text):
    return _vson_p2t_impl(text)


def _vson_x2t(text):
    return _vson_x2t_impl(text)


def _vson_gate1(ttl):
    conforms, report = _vson_shacl.validate_graph(_vson_graph(ttl))
    return json.dumps({"conforms": bool(conforms), "report": report})


def _vson_gate2(ttl):
    # Same clash inventory and phrasing as tools.owlrl_check.main().
    found = _vson_owl.clashes_for(_vson_graph(ttl))
    lines = []
    for x, a, b in found:
        if a == OWL.sameAs:
            lines.append(
                "<%s> and <%s> are asserted distinct yet inferred owl:sameAs" % (x, b)
            )
        else:
            lines.append("<%s> is inferred into both <%s> and <%s>" % (x, a, b))
    if lines:
        lines.append("owl-consistency: OWL 2 RL disjointness clash detected.")
    return json.dumps({"conforms": not lines, "report": "\\n".join(lines)})


def _vson_caption(ttl):
    return _vson_caption_impl(_vson_graph(ttl))


def _vson_fol(ttl):
    return _vson_fol_impl(_vson_graph(ttl))
`;

// ── init ───────────────────────────────────────────────────────────────────

export interface InitVsonOpsOptions {
	/**
	 * Explicit wheel locations handed verbatim to pyodide.loadPackage: same-
	 * origin /pyodide/wheels/*.whl URLs in the worker, absolute filesystem
	 * paths of the SAME committed files in the Node test.
	 */
	wheelUrls: string[];
}

type PyStringFn = (arg: string) => string;

function writeRepoTree(pyodide: PyodideAPI): void {
	for (const [rel, contents] of Object.entries(REPO_FILES)) {
		const abs = `${VSON_HOME}/${rel}`;
		pyodide.FS.mkdirTree(abs.slice(0, abs.lastIndexOf('/')));
		pyodide.FS.writeFile(abs, contents);
	}
}

// A Python exception surfaces in JS as an Error whose message is the full
// traceback. The last line ("SyntaxError: expected ...") is the part a
// repair prompt or a UI line can use; keep it, drop the frames.
function opError(e: unknown, label: string): Error {
	const raw = e instanceof Error ? e.message : String(e);
	const lines = raw
		.trim()
		.split('\n')
		.filter((l) => l.trim().length > 0);
	return new Error(`${label}: ${(lines[lines.length - 1] ?? raw).trim()}`);
}

export async function initVsonOps(pyodide: PyodideAPI, opts: InitVsonOpsOptions): Promise<VsonOps> {
	writeRepoTree(pyodide);
	// Explicit locations only: loadPackage installs exactly these files and
	// never consults an index, so the install is offline by construction.
	await pyodide.loadPackage(opts.wheelUrls, { messageCallback: () => {} });
	pyodide.runPython(BOOTSTRAP);

	const fn = (name: string): PyStringFn => pyodide.globals.get(name) as PyStringFn;
	const p2tFn = fn('_vson_p2t');
	const x2tFn = fn('_vson_x2t');
	const gate1Fn = fn('_vson_gate1');
	const gate2Fn = fn('_vson_gate2');
	const captionFn = fn('_vson_caption');
	const folFn = fn('_vson_fol');

	const call = (f: PyStringFn, label: string, arg: string): string => {
		try {
			return f(arg);
		} catch (e) {
			throw opError(e, label);
		}
	};

	return {
		p2t: (vsonP) => call(p2tFn, 'p2t', vsonP),
		x2t: (vsonX) => call(x2tFn, 'x2t', vsonX),
		validate: (turtle, onGate1) => {
			const gate1 = JSON.parse(call(gate1Fn, 'validate/shacl', turtle)) as GateResult;
			onGate1?.(gate1);
			if (!gate1.conforms) {
				return { conforms: false, report: gate1.report, gate1, gate2: null };
			}
			const gate2 = JSON.parse(call(gate2Fn, 'validate/owl', turtle)) as GateResult;
			return {
				conforms: gate2.conforms,
				report: gate2.conforms ? '' : gate2.report,
				gate1,
				gate2
			};
		},
		caption: (turtle) => call(captionFn, 'caption', turtle),
		fol: (turtle) => call(folFn, 'fol', turtle)
	};
}

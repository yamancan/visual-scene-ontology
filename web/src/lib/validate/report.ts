// Minimal violation parser: pyshacl --abort prints structured-ish output.
// We extract one entry per `Constraint Violation in ...` block.
// Pure string manipulation, no Node deps — importable from server routes,
// client components, and workers alike.
export interface ParsedViolation {
	message: string;
	shape: string;
	focus_node?: string;
	result_path?: string;
	severity?: 'Violation' | 'Warning' | 'Info';
}

// Strip pyshacl's IRI/blank-node decoration down to the bare local name so
// the UI can match it against graph node ids. Examples seen in the wild:
//   "<https://example.org/scenes/2026-05-02#sf1>"  → "sf1"
//   "vson:sf1"                                     → "sf1"
//   "_:b0"                                         → "b0"
//   "sf1"                                          → "sf1"
export function localName(raw: string): string {
	let s = raw.trim();
	if (s.startsWith('<') && s.endsWith('>')) s = s.slice(1, -1);
	const hash = s.lastIndexOf('#');
	if (hash >= 0) s = s.slice(hash + 1);
	const slash = s.lastIndexOf('/');
	if (slash >= 0) s = s.slice(slash + 1);
	const colon = s.lastIndexOf(':');
	if (colon >= 0) s = s.slice(colon + 1);
	if (s.startsWith('_:')) s = s.slice(2);
	return s;
}

export function parseViolationReport(report: string): ParsedViolation[] {
	const out: ParsedViolation[] = [];
	const blocks = report.split(/Constraint (?:Violation|Warning) in /);
	for (let i = 1; i < blocks.length; i++) {
		const b = blocks[i];
		const shape = (b.match(/^([A-Za-z]+ConstraintComponent)/) || ['', 'unknown'])[1];
		const message = (b.match(/Message:\s*(.+)/) || ['', ''])[1].trim();
		const fnRaw = (b.match(/Focus Node:\s*(.+)/) || ['', ''])[1].trim();
		const focus_node = fnRaw ? localName(fnRaw) : undefined;
		const rpRaw = (b.match(/Result Path:\s*(.+)/) || ['', ''])[1].trim();
		const result_path = rpRaw ? localName(rpRaw) : undefined;
		const severityRaw = (b.match(/Severity:\s*sh:(\w+)/) || ['', ''])[1];
		const severity = severityRaw
			? ((severityRaw[0].toUpperCase() + severityRaw.slice(1)) as 'Violation' | 'Warning' | 'Info')
			: 'Violation';
		out.push({ message, shape, focus_node, result_path, severity });
	}
	return out;
}

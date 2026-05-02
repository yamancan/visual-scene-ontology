// Spawn the Rust `vson` binary for transpile + validate. We write the
// Penman text to a temp file because the v0.1 CLI doesn't read stdin yet.
// Migrate to stdin once the CLI grows that flag (cli/src/commands/convert.rs).

import { spawn } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { env } from '$env/dynamic/private';

const REPO_ROOT = resolve(process.cwd(), '..');
const VSON_BIN = env.VSON_BIN || resolve(REPO_ROOT, 'cli/target/release/vson');

interface SpawnResult {
	code: number;
	stdout: string;
	stderr: string;
}

async function run(args: string[], cwd?: string): Promise<SpawnResult> {
	return new Promise((resolveSpawn) => {
		const proc = spawn(VSON_BIN, args, {
			cwd: cwd ?? REPO_ROOT,
			env: { ...process.env, VSON_HOME: REPO_ROOT }
		});
		let stdout = '';
		let stderr = '';
		proc.stdout.on('data', (d) => (stdout += d));
		proc.stderr.on('data', (d) => (stderr += d));
		proc.on('error', (e) => resolveSpawn({ code: -1, stdout, stderr: stderr + String(e) }));
		proc.on('close', (code) => resolveSpawn({ code: code ?? -1, stdout, stderr }));
	});
}

export interface TranspileOk {
	ok: true;
	turtle: string;
}
export interface TranspileErr {
	ok: false;
	error: string;
}

export async function transpilePenmanToTurtle(
	vson_p: string
): Promise<TranspileOk | TranspileErr> {
	const dir = await mkdtemp(join(tmpdir(), 'vson-'));
	const file = join(dir, 'in.vson');
	try {
		await writeFile(file, vson_p, 'utf8');
		const r = await run(['convert', 'p2t', file]);
		if (r.code === 0) return { ok: true, turtle: r.stdout };
		return { ok: false, error: r.stderr.trim() || `vson exited ${r.code}` };
	} finally {
		await rm(dir, { recursive: true, force: true });
	}
}

export interface ValidateResult {
	conforms: boolean;
	report: string;
}

export async function validateTurtle(turtle: string): Promise<ValidateResult> {
	const dir = await mkdtemp(join(tmpdir(), 'vson-'));
	const file = join(dir, 'data.ttl');
	try {
		await writeFile(file, turtle, 'utf8');
		const r = await run(['validate', file]);
		// vson exits 0 on conform, 1 on violation, 2 on usage error.
		const conforms = r.code === 0;
		return { conforms, report: (r.stdout + r.stderr).trim() };
	} finally {
		await rm(dir, { recursive: true, force: true });
	}
}

// Minimal violation parser: pyshacl --abort prints structured-ish output.
// We extract one entry per `Constraint Violation in ...` block.
export interface ParsedViolation {
	message: string;
	shape: string;
	focus_node?: string;
	result_path?: string;
	severity?: 'Violation' | 'Warning' | 'Info';
}

// Strip pyshacl's IRI/blank-node decoration down to the bare local name so
// the UI can match it against graph node ids. Examples seen in the wild:
//   "<http://vson.dev/scene/2026-05-02#sf1>"  → "sf1"
//   "vson:sf1"                                 → "sf1"
//   "_:b0"                                     → "b0"
//   "sf1"                                      → "sf1"
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
		const shape = (b.match(/^([A-Za-z]+ConstraintComponent)/) || [, 'unknown'])[1];
		const message = (b.match(/Message:\s*(.+)/) || [, ''])[1].trim();
		const fnRaw = (b.match(/Focus Node:\s*(.+)/) || [, ''])[1].trim();
		const focus_node = fnRaw ? localName(fnRaw) : undefined;
		const rpRaw = (b.match(/Result Path:\s*(.+)/) || [, ''])[1].trim();
		const result_path = rpRaw ? localName(rpRaw) : undefined;
		const severityRaw = (b.match(/Severity:\s*sh:(\w+)/) || [, ''])[1];
		const severity = severityRaw
			? ((severityRaw[0].toUpperCase() + severityRaw.slice(1)) as
					| 'Violation'
					| 'Warning'
					| 'Info')
			: 'Violation';
		out.push({ message, shape, focus_node, result_path, severity });
	}
	return out;
}

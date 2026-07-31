// Provenance gate for the COMMITTED validation wheels under
// static/pyodide/wheels/. The Pyodide worker installs exactly these files via
// loadPackage with explicit same-origin URLs — no micropip, no resolver, no
// PyPI — so the wheel set on disk IS the dependency closure. This test pins
// it three ways:
//
//   1. the exact expected filename set (swapping or bumping a wheel requires
//      a conscious edit here),
//   2. wheels.lock.json lists precisely the wheels on disk, and
//   3. every committed wheel's sha256 matches its lock entry.
//
// Wheel-set provenance (verified spike): the working Pyodide install ends
// with importable rdflib, pyshacl, owlrl, html5rdf, prettytable, pyparsing,
// packaging, wcwidth. rdflib needs pyparsing at import; pyshacl needs
// packaging; prettytable needs wcwidth. pyparsing/packaging/wcwidth are the
// pyodide 314.0.3 distribution wheels (sha256s equal the npm package's
// pyodide-lock.json entries); the rest are the pinned PyPI wheels.

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WHEELS_DIR = resolve(__dirname, '../static/pyodide/wheels');
const LOCK_PATH = resolve(WHEELS_DIR, 'wheels.lock.json');

// The complete, closed wheel set. Order matches the lock (sorted by filename).
const EXPECTED_WHEELS = [
	'html5rdf-1.2.1-py2.py3-none-any.whl',
	'owlrl-7.6.2-py3-none-any.whl',
	'packaging-26.1-py3-none-any.whl',
	'prettytable-3.18.0-py3-none-any.whl',
	'pyparsing-3.3.2-py3-none-any.whl',
	'pyshacl-0.40.1-py3-none-any.whl',
	'rdflib-7.6.0-py3-none-any.whl',
	'wcwidth-0.6.0-py3-none-any.whl'
];

interface WheelsLock {
	wheels: Array<{ filename: string; sha256: string }>;
}

const lock = JSON.parse(readFileSync(LOCK_PATH, 'utf8')) as WheelsLock;

describe('committed pyodide wheels', () => {
	it('lock file lists exactly the expected wheel set, sorted', () => {
		expect(lock.wheels.map((w) => w.filename)).toEqual(EXPECTED_WHEELS);
	});

	it('wheels on disk are exactly the locked set — nothing extra, nothing missing', () => {
		const onDisk = readdirSync(WHEELS_DIR)
			.filter((f) => f.endsWith('.whl'))
			.sort();
		expect(onDisk).toEqual(EXPECTED_WHEELS);
	});

	it('every committed wheel byte-matches its locked sha256', () => {
		for (const { filename, sha256 } of lock.wheels) {
			const bytes = readFileSync(resolve(WHEELS_DIR, filename));
			const actual = createHash('sha256').update(bytes).digest('hex');
			expect(actual, `sha256 drift in ${filename}`).toBe(sha256);
		}
	});
});

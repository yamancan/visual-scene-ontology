import { describe, it, expect } from 'vitest';
import { localName, parseViolationReport } from './report';

describe('localName', () => {
	it('unwraps angle-bracketed IRI and takes fragment', () => {
		expect(localName('<https://example.org/scenes/abc#sf1>')).toBe('sf1');
	});

	it('takes last segment after slash when no fragment', () => {
		expect(localName('<https://example.org/scenes/sf1>')).toBe('sf1');
	});

	it('strips qname prefix', () => {
		expect(localName('vson:sf1')).toBe('sf1');
	});

	it('strips blank-node prefix', () => {
		expect(localName('_:b0')).toBe('b0');
	});

	it('passes bare names through', () => {
		expect(localName('sf1')).toBe('sf1');
	});

	it('handles whitespace', () => {
		expect(localName('  vson:sf1  ')).toBe('sf1');
	});
});

describe('parseViolationReport', () => {
	it('returns empty array for empty input', () => {
		expect(parseViolationReport('')).toEqual([]);
	});

	it('extracts shape and focus_node and normalizes IRI', () => {
		const report = `Validation Report
Conforms: False
Constraint Violation in MinCountConstraintComponent (http://www.w3.org/ns/shacl#MinCountConstraintComponent):
\tSeverity: sh:Violation
\tSource Shape: vss:DirectionalNeedsViewerShape
\tFocus Node: <https://example.org/scenes/abc#sf1>
\tResult Path: vson:viewer
\tMessage: SpatialFact with :directional must carry :viewer.
`;
		const out = parseViolationReport(report);
		expect(out).toHaveLength(1);
		expect(out[0].shape).toBe('MinCountConstraintComponent');
		expect(out[0].focus_node).toBe('sf1');
		expect(out[0].result_path).toBe('viewer');
		expect(out[0].severity).toBe('Violation');
		expect(out[0].message).toMatch(/SpatialFact/);
	});

	it('parses multiple blocks', () => {
		const report = `Validation Report
Conforms: False
Constraint Violation in DatatypeConstraintComponent (...):
\tSource Shape: vss:A
\tFocus Node: vson:e1
\tMessage: bad type
Constraint Violation in MinCountConstraintComponent (...):
\tSource Shape: vss:B
\tFocus Node: <http://x/#alice>
\tMessage: missing
`;
		const out = parseViolationReport(report);
		expect(out).toHaveLength(2);
		expect(out[0].focus_node).toBe('e1');
		expect(out[1].focus_node).toBe('alice');
	});
});

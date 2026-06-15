import { describe, it, expect } from 'vitest';
import { parseBbox, cropStyle, fmtBbox } from './bbox';

describe('parseBbox', () => {
	it('parses a well-formed normalized tuple', () => {
		const b = parseBbox('0.30,0.10,0.40,0.80');
		expect(b).not.toBeNull();
		expect(b!.x).toBeCloseTo(0.3);
		expect(b!.y).toBeCloseTo(0.1);
		expect(b!.w).toBeCloseTo(0.4);
		expect(b!.h).toBeCloseTo(0.8);
		expect(b!.isFullImage).toBe(false);
	});

	it('tolerates whitespace around components', () => {
		const b = parseBbox(' 0.30 , 0.10 , 0.40 , 0.80 ');
		expect(b).not.toBeNull();
		expect(b!.w).toBeCloseTo(0.4);
	});

	it('detects a full-image bbox (≥95% both dims, ≤5% origin)', () => {
		expect(parseBbox('0,0,1,1')!.isFullImage).toBe(true);
		expect(parseBbox('0.02,0.03,0.97,0.98')!.isFullImage).toBe(true);
		// just short of the threshold on one dimension
		expect(parseBbox('0,0,0.94,1')!.isFullImage).toBe(false);
		// covers enough but offset origin → not full
		expect(parseBbox('0.1,0.1,0.95,0.95')!.isFullImage).toBe(false);
	});

	it('returns null on garbage / wrong arity / non-finite', () => {
		expect(parseBbox(undefined)).toBeNull();
		expect(parseBbox(null)).toBeNull();
		expect(parseBbox('')).toBeNull();
		expect(parseBbox('1,2,3')).toBeNull();
		expect(parseBbox('1,2,3,4,5')).toBeNull();
		expect(parseBbox('a,b,c,d')).toBeNull();
		expect(parseBbox('0.1,0.2,foo,0.4')).toBeNull();
	});

	it('tolerates a bare number (single value → not 4 numbers → null)', () => {
		// A lone number cannot be four components, so it parses to null.
		expect(parseBbox(0.5)).toBeNull();
	});
});

describe('cropStyle', () => {
	it('computes sprite math for a non-full bbox', () => {
		const b = parseBbox('0.30,0.10,0.40,0.80')!;
		const style = cropStyle(b, 'data:image/png;base64,AAAA');
		// w=0.4 → 250%, h=0.8 → 125%
		expect(style).toContain('background-size:250% 125%');
		// posX = 0.30/(1-0.40)*100 = 50%, posY = 0.10/(1-0.80)*100 = 50%
		expect(style).toContain('background-position:50% 50%');
		expect(style).toContain('background-image:url("data:image/png;base64,AAAA")');
		expect(style).toContain('background-repeat:no-repeat');
		expect(style).toContain('background-color:var(--bg-2)');
	});

	it('falls back to cover/center for a full-image bbox', () => {
		const b = parseBbox('0,0,1,1')!;
		const style = cropStyle(b, 'data:image/png;base64,AAAA');
		expect(style).toContain('background-size:cover');
		expect(style).toContain('background-position:center');
		expect(style).not.toContain('%');
	});
});

describe('fmtBbox', () => {
	it('formats each component to two decimals', () => {
		const b = parseBbox('0.30,0.10,0.40,0.80')!;
		expect(fmtBbox(b)).toBe('x=0.30 y=0.10 w=0.40 h=0.80');
	});
});

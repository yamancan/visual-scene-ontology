// Contract tests for the client-side extraction/correction orchestrator.
// Everything runs against injected mocks (chat + worker ops + fetch) — zero
// network, zero Pyodide. The load-bearing contracts:
//
//   - repair loop: 0 / 1 / 2 rounds, bounded by MAX_REPAIR_RETRIES, with the
//     server-era reason strings fed back to the model;
//   - X-mode drift state machine and the 0.25/drift confidence downgrade;
//   - correction caps enforced BEFORE anything is sent anywhere;
//   - sha256 demo short-circuit: a byte-exact demo upload renders the baked
//     envelope with no chat call and no worker op;
//   - limits pinned by value — changing a bound requires editing this file.

import { describe, it, expect, vi } from 'vitest';

import {
	base64ToBytes,
	correctScene,
	demoEnvelopeForSha,
	extractScene,
	OrchestratorError,
	sha256Hex,
	type OrchestratorDeps
} from './orchestrator';
import {
	MAX_CORRECTION_CHARS,
	MAX_CORRECTIONS,
	MAX_REPAIR_RETRIES,
	MAX_SOURCE_CHARS,
	SHACL_REPORT_SLICE_CHARS
} from './limits';
import type { ChatRequest, ChatResponse } from '../openrouter/client';
import type { GateResult, ValidateResult } from '../validate/pyodide-ops';
import type { VsonEnvelope } from '../types';
import { buildRepairPrompt } from '../prompts/bodies';

// ── fixtures ───────────────────────────────────────────────────────────────

const IMAGE_B64 = btoa('not-really-a-png');

function chatReply(content: string, input = 10, output = 5): ChatResponse {
	return {
		id: 'gen-1',
		model: 'mock/model',
		choices: [{ index: 0, message: { role: 'assistant', content }, finish_reason: 'stop' }],
		usage: { prompt_tokens: input, completion_tokens: output, total_tokens: input + output }
	};
}

const PASS: ValidateResult = {
	conforms: true,
	report: '',
	gate1: { conforms: true, report: '' },
	gate2: { conforms: true, report: '' }
};

// Shaped like a real pyshacl report so parseViolationReport finds the block.
const SHACL_FAIL_REPORT = [
	'Validation Report',
	'Conforms: False',
	'Results (1):',
	'Constraint Violation in ClassConstraintComponent (http://www.w3.org/ns/shacl#ClassConstraintComponent):',
	'\tSeverity: sh:Violation',
	'\tSource Shape: vsh:SpatialFactShape',
	'\tFocus Node: vson:sf1',
	'\tResult Path: vso:hasGround',
	'\tMessage: SpatialFact requires a ground'
].join('\n');

const FAIL: ValidateResult = {
	conforms: false,
	report: SHACL_FAIL_REPORT,
	gate1: { conforms: false, report: SHACL_FAIL_REPORT },
	gate2: null
};

interface DepsOpts {
	/** Sequential chat outcomes: assistant text, or an Error to reject with. */
	chat?: (string | Error)[];
	/** p2t implementation; may throw. Default: deterministic wrapper. */
	p2t?: (vsonP: string) => string;
	x2t?: (vsonX: string) => string;
	/** Sequential validate verdicts; the last one repeats. Default: PASS. */
	validate?: ValidateResult[];
	demoIndex?: Record<string, string>;
	demoFiles?: Record<string, unknown>;
	/** When set, the demo index fetch itself fails with this HTTP status. */
	demoIndexStatus?: number;
}

function makeDeps(opts: DepsOpts = {}) {
	const chat = vi.fn<OrchestratorDeps['chat']>();
	for (const r of opts.chat ?? []) {
		if (r instanceof Error) chat.mockRejectedValueOnce(r);
		else chat.mockResolvedValueOnce(chatReply(r));
	}

	const p2tImpl = opts.p2t ?? ((vsonP: string) => `# p2t\n${vsonP}\n`);
	const x2tImpl = opts.x2t ?? ((vsonX: string) => `# x2t\n${vsonX}`);
	const p2t = vi.fn(async (vsonP: string) => p2tImpl(vsonP));
	const x2t = vi.fn(async (vsonX: string) => x2tImpl(vsonX));

	const verdicts = [...(opts.validate ?? [PASS])];
	const validate = vi.fn(
		async (_turtle: string, onGate1?: (gate1: GateResult) => void): Promise<ValidateResult> => {
			const v = verdicts.length > 1 ? verdicts.shift()! : verdicts[0];
			onGate1?.(v.gate1);
			return v;
		}
	);

	const fetchFn = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
		const url = String(input);
		if (url === '/demos/envelopes/index.json') {
			if (opts.demoIndexStatus) return new Response('down', { status: opts.demoIndexStatus });
			return new Response(JSON.stringify(opts.demoIndex ?? {}), { status: 200 });
		}
		const file = url.replace('/demos/envelopes/', '');
		if (opts.demoFiles && file in opts.demoFiles) {
			return new Response(JSON.stringify(opts.demoFiles[file]), { status: 200 });
		}
		return new Response('not found', { status: 404 });
	}) as unknown as typeof fetch;

	const deps: OrchestratorDeps = { chat, ops: { p2t, x2t, validate }, fetchFn };
	return { deps, chat, p2t, x2t, validate };
}

/** All text parts of a chat request's user message, joined. */
function userText(req: ChatRequest): string {
	const user = req.messages.find((m) => m.role === 'user');
	if (!user || typeof user.content === 'string') return (user?.content as string) ?? '';
	return user.content
		.filter((b): b is Extract<typeof b, { type: 'text' }> => b.type === 'text')
		.map((b) => b.text)
		.join('\n');
}

async function caught(p: Promise<unknown>): Promise<OrchestratorError> {
	try {
		await p;
	} catch (e) {
		return e as OrchestratorError;
	}
	throw new Error('expected the promise to reject');
}

// ── helpers under test ─────────────────────────────────────────────────────

describe('sha256Hex + base64ToBytes', () => {
	it('computes the canonical sha256 of the decoded bytes', async () => {
		expect(await sha256Hex(base64ToBytes(btoa('abc')))).toBe(
			'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
		);
	});
});

// ── limits pinned by value ─────────────────────────────────────────────────

describe('limits — conscious-edit gate', () => {
	it('pins every bound the flows rely on', () => {
		expect(MAX_REPAIR_RETRIES).toBe(2);
		expect(MAX_SOURCE_CHARS).toBe(64 * 1024);
		expect(MAX_CORRECTIONS).toBe(50);
		expect(MAX_CORRECTION_CHARS).toBe(2 * 1024);
		expect(SHACL_REPORT_SLICE_CHARS).toBe(4000);
	});

	it('buildRepairPrompt slices the SHACL report at the shared bound', () => {
		const prompt = buildRepairPrompt('(doc)', 'x'.repeat(SHACL_REPORT_SLICE_CHARS + 1000));
		expect(prompt).toContain('x'.repeat(SHACL_REPORT_SLICE_CHARS));
		expect(prompt).not.toContain('x'.repeat(SHACL_REPORT_SLICE_CHARS + 1));
	});
});

// ── extraction: repair rounds ──────────────────────────────────────────────

describe('extractScene — Penman repair loop', () => {
	const baseReq = { image_b64: IMAGE_B64, mime: 'image/png' as const };

	it('0 rounds: a conforming first answer ships with shacl_retries 0', async () => {
		const { deps, chat, p2t, validate } = makeDeps({
			chat: ['(s / Composition)'],
			validate: [PASS]
		});

		const envelope = await extractScene(baseReq, deps);

		expect(chat).toHaveBeenCalledTimes(1);
		expect(p2t).toHaveBeenCalledTimes(1);
		expect(validate).toHaveBeenCalledTimes(1);
		expect(envelope.version).toBe('1.2');
		expect(envelope.vson_p).toBe('(s / Composition)');
		expect(envelope.vson_t).toBe('# p2t\n(s / Composition)\n');
		expect(envelope.conformance).toEqual({ conforms: true });
		expect(envelope.extraction?.shacl_retries).toBe(0);
		expect(envelope.extraction?.input_tokens).toBe(10);
		expect(envelope.extraction?.output_tokens).toBe(5);
		expect(envelope.source?.sha256).toBe(await sha256Hex(base64ToBytes(IMAGE_B64)));
	});

	it('sends the image and the bare user instruction on the initial call', async () => {
		const { deps, chat } = makeDeps({ chat: ['(s / Composition)'] });

		await extractScene({ ...baseReq, model: 'mock/model' }, deps);

		const req = chat.mock.calls[0][0];
		expect(req.model).toBe('mock/model');
		const system = req.messages[0];
		expect(system.role).toBe('system');
		expect(Array.isArray(system.content) && system.content[0]).toMatchObject({
			type: 'text',
			cache_control: { type: 'ephemeral' }
		});
		const user = req.messages[1];
		expect(Array.isArray(user.content) && user.content[0]).toEqual({
			type: 'image_url',
			image_url: { url: `data:image/png;base64,${IMAGE_B64}` }
		});
		expect(userText(req)).toContain('Emit the VSON-P document');
	});

	it('1 round: a SHACL failure feeds the report back and ships the repaired doc', async () => {
		const { deps, chat } = makeDeps({
			chat: ['(bad / Doc)', '(good / Doc)'],
			validate: [FAIL, PASS]
		});

		const envelope = await extractScene(baseReq, deps);

		expect(chat).toHaveBeenCalledTimes(2);
		const repairText = userText(chat.mock.calls[1][0]);
		expect(repairText).toContain('(bad / Doc)');
		expect(repairText).toContain('SpatialFact requires a ground');
		expect(envelope.vson_p).toBe('(good / Doc)');
		expect(envelope.conformance?.conforms).toBe(true);
		expect(envelope.extraction?.shacl_retries).toBe(1);
		// usage accumulates across the initial call and the repair round
		expect(envelope.extraction?.input_tokens).toBe(20);
		expect(envelope.extraction?.output_tokens).toBe(10);
	});

	it('2 rounds: retries stop at MAX_REPAIR_RETRIES and ship conforms=false with parsed violations', async () => {
		const { deps, chat, validate } = makeDeps({
			chat: ['(bad / Doc)', '(bad2 / Doc)', '(bad3 / Doc)'],
			validate: [FAIL, FAIL, FAIL]
		});

		const envelope = await extractScene(baseReq, deps);

		expect(chat).toHaveBeenCalledTimes(1 + MAX_REPAIR_RETRIES);
		expect(validate).toHaveBeenCalledTimes(3);
		expect(envelope.extraction?.shacl_retries).toBe(MAX_REPAIR_RETRIES);
		expect(envelope.conformance?.conforms).toBe(false);
		expect(envelope.conformance?.violations).toEqual([
			{
				message: 'SpatialFact requires a ground',
				shape: 'ClassConstraintComponent',
				focus_node: 'sf1',
				result_path: 'hasGround',
				severity: 'Violation'
			}
		]);
	});

	it('a transpile failure feeds the parse error as the repair reason', async () => {
		let calls = 0;
		const { deps, chat } = makeDeps({
			chat: ['(broken / Doc)', '(fixed / Doc)'],
			p2t: (vsonP) => {
				calls++;
				if (calls === 1) throw new Error('p2t: SyntaxError: unbalanced parens');
				return `# p2t\n${vsonP}\n`;
			},
			validate: [PASS]
		});

		const envelope = await extractScene(baseReq, deps);

		expect(userText(chat.mock.calls[1][0])).toContain(
			'Penman parse error: p2t: SyntaxError: unbalanced parens'
		);
		expect(envelope.extraction?.shacl_retries).toBe(1);
		expect(envelope.conformance?.conforms).toBe(true);
	});

	it('a chat failure mid-repair abandons the loop and ships the current state', async () => {
		const { deps, chat } = makeDeps({
			chat: ['(bad / Doc)', new Error('network unreachable')],
			validate: [FAIL]
		});

		const envelope = await extractScene(baseReq, deps);

		expect(chat).toHaveBeenCalledTimes(2);
		expect(envelope.vson_p).toBe('(bad / Doc)');
		expect(envelope.conformance?.conforms).toBe(false);
		expect(envelope.extraction?.shacl_retries).toBe(1);
	});

	it('throws empty-output when the reply holds no Penman document', async () => {
		const { deps } = makeDeps({ chat: ['sorry, I cannot help with that'] });

		const err = await caught(extractScene(baseReq, deps));

		expect(err).toBeInstanceOf(OrchestratorError);
		expect(err.kind).toBe('empty-output');
	});

	it('threads the progressive-verdict hook through to each validation round', async () => {
		const onGate1 = vi.fn();
		const { deps } = makeDeps({ chat: ['(bad / Doc)', '(good / Doc)'], validate: [FAIL, PASS] });

		await extractScene({ ...baseReq, onGate1 }, deps);

		expect(onGate1).toHaveBeenCalledTimes(2);
		expect(onGate1).toHaveBeenNthCalledWith(1, FAIL.gate1);
		expect(onGate1).toHaveBeenNthCalledWith(2, PASS.gate1);
	});

	it('rejects a mime outside image/jpeg|png before doing anything', async () => {
		const { deps, chat } = makeDeps();

		const err = await caught(
			extractScene({ image_b64: IMAGE_B64, mime: 'image/gif' as 'image/png' }, deps)
		);

		expect(err.kind).toBe('input');
		expect(chat).not.toHaveBeenCalled();
	});
});

// ── extraction: X-mode drift ───────────────────────────────────────────────

describe('extractScene — VSON-X drift machine', () => {
	const xReq = { image_b64: IMAGE_B64, mime: 'image/png' as const, variant: 'skill-x' as const };

	it('a clean X answer ships with the vson_p sentinel and no confidence penalty', async () => {
		const { deps, x2t, p2t } = makeDeps({ chat: ['~scene\n~ent p Persona'], validate: [PASS] });

		const envelope = await extractScene(xReq, deps);

		expect(x2t).toHaveBeenCalledTimes(1);
		expect(p2t).not.toHaveBeenCalled();
		expect(envelope.vson_p).toBe('');
		expect(envelope.vson_x).toBe('~scene\n~ent p Persona\n');
		expect(envelope.extraction?.shacl_retries).toBe(0);
		expect(envelope.extraction?.confidence_overall).toBeUndefined();
	});

	it('one drift then a fix: confidence 0.75, DRIFT marker in the repair prompt', async () => {
		const { deps, chat } = makeDeps({
			chat: ['(s / Composition)', '~scene\n~ent p Persona'],
			validate: [PASS]
		});

		const envelope = await extractScene(xReq, deps);

		const repairText = userText(chat.mock.calls[1][0]);
		expect(repairText).toContain('VSON-X parse error: model emitted Penman, not VSON-X');
		expect(repairText).toContain('(DRIFT: model emitted Penman; first character must be ~)');
		expect(envelope.vson_x).toBe('~scene\n~ent p Persona\n');
		expect(envelope.conformance?.conforms).toBe(true);
		expect(envelope.extraction?.shacl_retries).toBe(1);
		expect(envelope.extraction?.confidence_overall).toBe(0.75);
	});

	it('persistent drift exhausts both retries: confidence 0.25, empty document, conforms=false', async () => {
		const { deps, chat } = makeDeps({
			chat: ['(p1 / Doc)', '(p2 / Doc)', '(p3 / Doc)']
		});

		const envelope = await extractScene(xReq, deps);

		expect(chat).toHaveBeenCalledTimes(3);
		expect(envelope.vson_x).toBe('');
		expect(envelope.vson_t).toBe('');
		expect(envelope.graph).toEqual({ nodes: [], edges: [] });
		expect(envelope.conformance?.conforms).toBe(false);
		expect(envelope.extraction?.shacl_retries).toBe(MAX_REPAIR_RETRIES);
		// initial drift + two drifting repairs = 3 drifts → 1 - 0.75
		expect(envelope.extraction?.confidence_overall).toBe(0.25);
	});

	it('throws empty-output when the reply is neither X nor Penman', async () => {
		const { deps } = makeDeps({ chat: ['no document at all'] });

		const err = await caught(extractScene(xReq, deps));

		expect(err.kind).toBe('empty-output');
	});
});

// ── demo short-circuit ─────────────────────────────────────────────────────

function bakedEnvelope(promptVersion: string): VsonEnvelope {
	return {
		scene_id: 'baked01',
		version: '1.2',
		source: { kind: 'image', sha256: 'deadbeef' },
		vson_p: '(s / Composition)',
		vson_t: '',
		conformance: { conforms: true },
		extraction: { model: 'baked/model', prompt_version: promptVersion }
	};
}

describe('extractScene — sha256 demo short-circuit', () => {
	it('a byte-exact demo upload renders the baked envelope: no chat, no worker', async () => {
		const sha = await sha256Hex(base64ToBytes(IMAGE_B64));
		const baked = bakedEnvelope('skill@1.0.0');
		const { deps, chat, p2t, validate } = makeDeps({
			demoIndex: { [sha]: 'kitchen.json' },
			demoFiles: { 'kitchen.json': baked }
		});

		const envelope = await extractScene({ image_b64: IMAGE_B64, mime: 'image/png' }, deps);

		expect(envelope).toEqual(baked);
		expect(chat).not.toHaveBeenCalled();
		expect(p2t).not.toHaveBeenCalled();
		expect(validate).not.toHaveBeenCalled();
	});

	it('a variant mismatch falls through to live extraction', async () => {
		const sha = await sha256Hex(base64ToBytes(IMAGE_B64));
		const { deps, chat } = makeDeps({
			demoIndex: { [sha]: 'kitchen.json' },
			demoFiles: { 'kitchen.json': bakedEnvelope('skill@1.0.0') },
			chat: ['~scene\n~ent p Persona'],
			validate: [PASS]
		});

		const envelope = await extractScene(
			{ image_b64: IMAGE_B64, mime: 'image/png', variant: 'skill-x' },
			deps
		);

		expect(chat).toHaveBeenCalledTimes(1);
		expect(envelope.vson_x).toBe('~scene\n~ent p Persona\n');
	});

	it('an unreachable demo index degrades to the live path, never to an error', async () => {
		const { deps, chat } = makeDeps({
			demoIndexStatus: 500,
			chat: ['(s / Composition)'],
			validate: [PASS]
		});

		const envelope = await extractScene({ image_b64: IMAGE_B64, mime: 'image/png' }, deps);

		expect(chat).toHaveBeenCalledTimes(1);
		expect(envelope.conformance?.conforms).toBe(true);
	});

	it('matches on the version NAME left of @ — the full variant bakes as orchestrator-system@…, not full@…', async () => {
		const { deps } = makeDeps({
			demoIndex: { feedface: 'throne.json' },
			demoFiles: { 'throne.json': bakedEnvelope('orchestrator-system@1.0') }
		});

		expect(await demoEnvelopeForSha('feedface', 'full', deps.fetchFn)).toEqual(
			bakedEnvelope('orchestrator-system@1.0')
		);
		expect(await demoEnvelopeForSha('feedface', 'skill', deps.fetchFn)).toBeNull();
	});
});

// ── correction ─────────────────────────────────────────────────────────────

describe('correctScene — caps enforced before anything is sent', () => {
	const base = { notation: 'p' as const, source: '(s / Composition)', corrections: [] };

	async function expectInputError(req: Parameters<typeof correctScene>[0], message: string) {
		const { deps, chat } = makeDeps();
		const err = await caught(correctScene(req, deps));
		expect(err).toBeInstanceOf(OrchestratorError);
		expect(err.kind).toBe('input');
		expect(err.message).toBe(message);
		expect(chat).not.toHaveBeenCalled();
	}

	it('rejects an empty source document', async () => {
		await expectInputError({ ...base, source: '   ' }, 'expected a non-empty source document');
	});

	it('rejects a source over 64 KB', async () => {
		await expectInputError(
			{ ...base, source: 'x'.repeat(MAX_SOURCE_CHARS + 1) },
			'source exceeds 64 KB cap'
		);
	});

	it('rejects more than 50 corrections', async () => {
		const corrections = Array.from({ length: MAX_CORRECTIONS + 1 }, (_, i) => ({ id: `e${i}` }));
		await expectInputError(
			{ ...base, corrections },
			`too many corrections (max ${MAX_CORRECTIONS})`
		);
	});

	it('rejects a correction item over 2 KB', async () => {
		const corrections = [{ id: 'e1', note: 'x'.repeat(MAX_CORRECTION_CHARS) }];
		await expectInputError({ ...base, corrections }, 'correction item exceeds 2 KB cap');
	});

	it('rejects a scene note over 2 KB', async () => {
		await expectInputError(
			{ ...base, sceneNote: 'x'.repeat(MAX_CORRECTION_CHARS + 1) },
			'sceneNote exceeds 2 KB cap'
		);
	});

	it('rejects an unknown notation', async () => {
		await expectInputError({ ...base, notation: 'z' as 'p' }, "notation must be 'p' or 'x'");
	});
});

describe('correctScene — correction round-trip', () => {
	it('builds the correction prompt and runs the same repair loop', async () => {
		const { deps, chat } = makeDeps({
			chat: ['(s / Composition :corrected true)'],
			validate: [PASS]
		});

		const envelope = await correctScene(
			{
				notation: 'p',
				source: '(s / Composition)',
				corrections: [{ id: 'p1', klass: 'Chair' }],
				sceneNote: 'the chair is red'
			},
			deps
		);

		const text = userText(chat.mock.calls[0][0]);
		expect(text).toContain('applying targeted corrections');
		expect(text).toContain('- entity @p1: set class to Chair');
		expect(text).toContain('Scene note: the chair is red');
		expect(text).toContain('(s / Composition)');
		expect(envelope.vson_p).toBe('(s / Composition :corrected true)');
		expect(envelope.extraction?.prompt_version).toBe('skill@1.0.0');
		// no image → source carries only the kind
		expect(envelope.source).toEqual({ kind: 'image' });
	});

	it('hashes an attached image into source.sha256 and sends it with the prompt', async () => {
		const { deps, chat } = makeDeps({ chat: ['(s / Composition)'], validate: [PASS] });

		const envelope = await correctScene(
			{
				notation: 'p',
				source: '(s / Composition)',
				corrections: [],
				image_b64: IMAGE_B64,
				mime: 'image/jpeg'
			},
			deps
		);

		expect(envelope.source).toEqual({
			kind: 'image',
			sha256: await sha256Hex(base64ToBytes(IMAGE_B64))
		});
		const user = chat.mock.calls[0][0].messages[1];
		expect(Array.isArray(user.content) && user.content[0]).toEqual({
			type: 'image_url',
			image_url: { url: `data:image/jpeg;base64,${IMAGE_B64}` }
		});
	});

	it('the X notation uses the X correction prompt and the x2t path', async () => {
		const { deps, chat, x2t } = makeDeps({ chat: ['~scene\n~ent p Persona'], validate: [PASS] });

		const envelope = await correctScene(
			{
				notation: 'x',
				source: '~scene\n~ent p Persona\n',
				corrections: [{ id: 'p', remove: true }]
			},
			deps
		);

		const text = userText(chat.mock.calls[0][0]);
		expect(text).toContain('VSON-X');
		expect(text).toContain('- entity @p: REMOVE this entity');
		expect(x2t).toHaveBeenCalledTimes(1);
		expect(envelope.vson_p).toBe('');
		expect(envelope.vson_x).toBe('~scene\n~ent p Persona\n');
		expect(envelope.extraction?.prompt_version).toBe('skill-x@1.0.0');
	});
});

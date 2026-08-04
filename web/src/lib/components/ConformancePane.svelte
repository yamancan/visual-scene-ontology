<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { formatMs, isPrebuilt } from '$lib/utils';
	// Pure string transform, no Pyodide in its import graph.
	import { removeOneViewer } from '$lib/validate/tamper';
	import type { Violation } from '$lib/types';
	// Type-only: erased at build, so this pane still costs zero Pyodide bytes
	// until someone presses the button below.
	import type { WorkerPhase } from '$lib/validate/client';

	let env = $derived(scene.envelope);
	let conforms = $derived(env?.conformance.conforms ?? false);
	let violations = $derived(env?.conformance.violations ?? []);
	let extraction = $derived(env?.extraction);
	let prebuilt = $derived(isPrebuilt(extraction?.model));

	// Re-verification of a prebuilt envelope. The verdict a demo or a spec
	// example carries was recorded when the file was baked — it is a record,
	// not a demonstration, and a visitor has no reason to take it on trust.
	// This runs the two browser gates over the document actually on screen and
	// reports what they say, without touching the envelope: the stored verdict
	// stays the record, this is a second opinion beside it.
	//
	// Opt-in by construction. The client — and the ~16 MB runtime behind it —
	// is dynamic-imported inside the handler, so the keyless demo path still
	// downloads no Pyodide byte for anyone who never presses this.
	type Recheck =
		| { state: 'idle' }
		| { state: 'running'; note: string }
		| { state: 'done'; conforms: boolean; gate1: boolean; gate2: boolean | null; ms: number }
		| { state: 'failed'; message: string };

	const PHASE_NOTE: Record<WorkerPhase, string> = {
		downloading: 'downloading runtime…',
		booting: 'booting python…',
		installing: 'installing gates…',
		ready: 'running gates…'
	};

	let recheck = $state<Recheck>({ state: 'idle' });

	// The counterfactual: the same two gates, over a COPY of this document with
	// one vso:viewer triple dropped ($lib/validate/tamper). Every keyless
	// surface of this studio is green by construction, so nothing here has ever
	// shown a gate biting — this does, without a key, a model, or a pixel.
	//
	// `whatIfSource` is both the qualification test and the payload: it is null
	// unless the document really carries a directional fact with a viewer, and
	// the affordance below renders only when it is not. No disabled state.
	//
	// The verdict renders BESIDE the real one; scene.envelope is never written.
	type WhatIf =
		| { state: 'idle' }
		| { state: 'running'; note: string }
		| { state: 'done'; conforms: boolean; violations: Violation[] }
		| { state: 'failed'; message: string };

	let whatIf = $state<WhatIf>({ state: 'idle' });
	let whatIfSource = $derived(env?.vson_t ? removeOneViewer(env.vson_t) : null);

	// Every run carries a token. A gate verdict takes ~3s and the document it
	// was computed over can be replaced meanwhile (a new scene, a second press);
	// a run whose token is stale settles into nothing rather than printing its
	// verdict under a document it never saw. The two interactions count
	// separately so that starting one never strands the other mid-flight.
	let run = 0;
	let whatIfRun = 0;

	$effect(() => {
		void scene.envelope;
		run += 1;
		whatIfRun += 1;
		recheck = { state: 'idle' };
		whatIf = { state: 'idle' };
	});

	async function reverify() {
		const turtle = env?.vson_t;
		if (!turtle || recheck.state === 'running') return;
		const token = ++run;
		recheck = { state: 'running', note: 'starting…' };
		const t0 = performance.now();
		try {
			const { validationClient } = await import('$lib/validate/client');
			const client = validationClient();
			const stopWatching = client.subscribe((s) => {
				if (token !== run || recheck.state !== 'running') return;
				if (s.state === 'starting') recheck = { state: 'running', note: PHASE_NOTE[s.phase] };
				else if (s.state === 'ready') recheck = { state: 'running', note: PHASE_NOTE.ready };
			});
			try {
				const result = await client.validate(turtle);
				if (token !== run) return;
				recheck = {
					state: 'done',
					conforms: result.conforms,
					gate1: result.gate1.conforms,
					gate2: result.gate2?.conforms ?? null,
					ms: Math.round(performance.now() - t0)
				};
			} finally {
				stopWatching();
			}
		} catch (err) {
			if (token !== run) return;
			recheck = { state: 'failed', message: (err as Error).message };
		}
	}

	// Same worker, same two gates, same progress phases as reverify() above —
	// the only difference is the document handed over: an in-memory copy that
	// nothing else ever reads. `restore` drops the copy; the real verdict was
	// on screen the whole time.
	async function runWhatIf() {
		const removal = whatIfSource;
		if (!removal || whatIf.state === 'running') return;
		const token = ++whatIfRun;
		whatIf = { state: 'running', note: 'starting…' };
		try {
			const { validationClient, toConformanceReport } = await import('$lib/validate/client');
			const client = validationClient();
			const stopWatching = client.subscribe((s) => {
				if (token !== whatIfRun || whatIf.state !== 'running') return;
				if (s.state === 'starting') whatIf = { state: 'running', note: PHASE_NOTE[s.phase] };
				else if (s.state === 'ready') whatIf = { state: 'running', note: PHASE_NOTE.ready };
			});
			try {
				const report = toConformanceReport(await client.validate(removal.turtle));
				if (token !== whatIfRun) return;
				whatIf = {
					state: 'done',
					conforms: report.conforms,
					violations: report.violations ?? []
				};
			} finally {
				stopWatching();
			}
		} catch (err) {
			if (token !== whatIfRun) return;
			whatIf = { state: 'failed', message: (err as Error).message };
		}
	}

	function restoreWhatIf() {
		whatIfRun += 1;
		whatIf = { state: 'idle' };
	}

	function shortShape(s: string): string {
		const i = s.indexOf(':');
		return i >= 0 ? s.slice(i + 1) : s;
	}

	function jumpToNode(id: string | undefined) {
		if (!id) return;
		scene.setSelected(id);
		scene.setRailTab('source');
	}
</script>

<section class="wrap">
	{#if env}
		<div class="hero" class:pass={conforms} class:fail={!conforms}>
			<div class="hero-stat">
				<span class="hero-num font-mono">{env.graph?.nodes.length ?? 0}</span>
				<span class="hero-label font-mono">nodes</span>
			</div>
			<div class="hero-divider"></div>
			<div class="hero-stat">
				<span class="hero-num font-mono">{env.graph?.edges.length ?? 0}</span>
				<span class="hero-label font-mono">edges</span>
			</div>
			<div class="hero-divider"></div>
			<div class="hero-stat conf">
				<span class="hero-num font-mono">{conforms ? 'PASS' : violations.length}</span>
				<span class="hero-label font-mono">{conforms ? 'shacl' : 'violations'}</span>
			</div>
		</div>

		{#if !conforms && violations.length > 0}
			<div class="viol-list">
				<div class="section-label font-mono">violations</div>
				{#each violations as v, i (i)}
					<div class="viol">
						<div class="viol-head">
							<span class="viol-shape font-mono">{shortShape(v.shape)}</span>
							{#if v.focus_node}
								<button
									type="button"
									class="viol-focus font-mono"
									onclick={() => jumpToNode(v.focus_node)}
									title="Jump to this node in the graph + Penman"
								>
									{v.focus_node}
								</button>
							{/if}
						</div>
						<div class="viol-msg">{v.message}</div>
					</div>
				{/each}
			</div>
		{:else if conforms}
			<div class="pass-msg">
				<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
					<path
						d="M3 8.5 L7 12 L13 4"
						stroke="var(--success)"
						stroke-width="2"
						fill="none"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
				<span>Document satisfies every published SHACL shape.</span>
			</div>
		{/if}

		{#if extraction}
			<dl class="meta">
				{#if prebuilt}
					<div class="meta-row">
						<dt>source</dt>
						<dd>prebuilt fixture</dd>
					</div>
					<div class="meta-row">
						<dt>prompt</dt>
						<dd>{extraction.prompt_version ?? 'skill@1.0.0'}</dd>
					</div>
					<div class="meta-row">
						<dt>cost</dt>
						<dd><span class="ok">$0 · cached</span></dd>
					</div>
				{:else}
					<div class="meta-row">
						<dt>model</dt>
						<dd title={extraction.model}>{extraction.model}</dd>
					</div>
					<div class="meta-row">
						<dt>prompt</dt>
						<dd>{extraction.prompt_version ?? '—'}</dd>
					</div>
					<div class="meta-row">
						<dt>latency</dt>
						<dd>{((extraction.latency_ms ?? 0) / 1000).toFixed(2)}s</dd>
					</div>
					<div class="meta-row">
						<dt>repairs</dt>
						<dd>
							{extraction.shacl_retries ?? 0}
							{#if (extraction.shacl_retries ?? 0) > 0}<span class="warn"> · used</span>{:else}<span
									class="ok"
								>
									· clean</span
								>{/if}
						</dd>
					</div>
					<div class="meta-row">
						<dt>tokens in</dt>
						<dd>{(extraction.input_tokens ?? 0).toLocaleString()}</dd>
					</div>
					<div class="meta-row">
						<dt>tokens out</dt>
						<dd>{(extraction.output_tokens ?? 0).toLocaleString()}</dd>
					</div>
				{/if}
			</dl>
		{/if}

		{#if prebuilt && env.vson_t}
			<div class="recheck">
				<button
					type="button"
					class="recheck-btn font-mono"
					onclick={reverify}
					disabled={recheck.state === 'running'}
					title="Runs pyshacl (Gate 1), then owlrl (Gate 2), over this document in a Pyodide worker in this tab. The first run downloads ~16 MB of runtime; after that it is cached. The CLI's third gate — C2 vocabulary closure — does not run in the browser."
				>
					{recheck.state === 'running' ? recheck.note : 'verify in this browser'}
				</button>
				{#if recheck.state === 'done'}
					<div
						class="recheck-out font-mono"
						class:ok={recheck.conforms}
						class:bad={!recheck.conforms}
					>
						pyshacl {recheck.gate1 ? 'pass' : 'fail'} · owlrl
						{recheck.gate2 === null ? 'not run' : recheck.gate2 ? 'pass' : 'fail'} ·
						{formatMs(recheck.ms)}
					</div>
					<div class="recheck-note font-mono">
						ran here, just now · C2 vocabulary closure is CLI-only
					</div>
				{:else if recheck.state === 'failed'}
					<div class="recheck-out bad font-mono">{recheck.message}</div>
				{/if}
			</div>
		{/if}

		{#if whatIfSource}
			<div class="whatif">
				{#if whatIf.state === 'idle'}
					<button type="button" class="whatif-ask font-mono" onclick={runWhatIf}>
						what if the viewer were removed?
					</button>
				{:else if whatIf.state === 'running'}
					<span class="whatif-ask running font-mono">{whatIf.note}</span>
				{:else}
					<div class="whatif-head">
						<span class="section-label font-mono">what-if · viewer removed</span>
						<button type="button" class="whatif-ask font-mono" onclick={restoreWhatIf}>
							restore
						</button>
					</div>
					<div class="whatif-diff font-mono">
						<span class="minus" aria-hidden="true">−</span>
						:{whatIfSource.fact} vso:viewer :{whatIfSource.viewer}
					</div>
					{#if whatIf.state === 'failed'}
						<div class="recheck-out bad font-mono">{whatIf.message}</div>
					{:else if whatIf.violations.length > 0}
						<div class="viol-list">
							{#each whatIf.violations as v, i (i)}
								<div class="viol">
									<div class="viol-head">
										<span class="viol-shape font-mono">{shortShape(v.shape)}</span>
										{#if v.focus_node}
											<span class="viol-node font-mono">{v.focus_node}</span>
										{/if}
									</div>
									<div class="viol-msg">{v.message}</div>
								</div>
							{/each}
						</div>
					{:else}
						<div class="recheck-out font-mono">both gates still pass on the copy.</div>
					{/if}
					<p class="whatif-note">
						A copy of this scene, with the viewer removed — the loaded document is untouched and
						nothing was written anywhere. Checked in your browser; no key, no model, no image read.
					</p>
				{/if}
			</div>
		{/if}

		{#if env.source?.sha256}
			<div class="src-line font-mono" title={env.source.sha256}>
				<span class="src-key">sha256</span>
				<span class="src-val">{env.source.sha256.slice(0, 12)}…{env.source.sha256.slice(-6)}</span>
			</div>
		{/if}
	{/if}
</section>

<style>
	.wrap {
		display: flex;
		flex-direction: column;
		gap: var(--s4);
		height: 100%;
		padding: var(--s3);
		overflow-y: auto;
	}
	.hero {
		display: flex;
		align-items: stretch;
		justify-content: space-around;
		padding: var(--s3) var(--s2);
		border-radius: var(--radius);
		border: 1px solid var(--border-1);
		background: var(--bg-2);
		flex-shrink: 0;
	}
	.hero.pass {
		border-color: color-mix(in srgb, var(--success) 30%, var(--border-1));
		background: color-mix(in srgb, var(--success) 6%, var(--bg-2));
	}
	.hero.fail {
		border-color: color-mix(in srgb, var(--danger) 30%, var(--border-1));
		background: color-mix(in srgb, var(--danger) 6%, var(--bg-2));
	}
	.hero-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		flex: 1;
	}
	.hero-num {
		font-size: var(--text-xl);
		font-weight: 500;
		line-height: 1;
		color: var(--fg-0);
		font-variant-numeric: tabular-nums;
	}
	.hero.pass .hero-stat.conf .hero-num {
		color: var(--success);
		font-size: var(--text-base);
	}
	.hero.fail .hero-stat.conf .hero-num {
		color: var(--danger);
	}
	.hero-label {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.hero-divider {
		width: 1px;
		background: var(--border-1);
		margin: 4px 0;
	}
	.section-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
		margin-bottom: var(--s2);
	}
	.viol-list {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
	}
	.viol {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: var(--s2) var(--s3);
		border-left: 2px solid var(--danger);
		background: color-mix(in srgb, var(--danger) 5%, var(--bg-2));
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
	}
	.viol-head {
		display: flex;
		align-items: center;
		gap: var(--s2);
		justify-content: space-between;
	}
	.viol-shape {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--danger);
	}
	.viol-focus {
		font-size: 10px;
		color: var(--accent);
		background: var(--accent-bg, color-mix(in srgb, var(--accent) 12%, transparent));
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-1));
		border-radius: var(--radius-sm);
		padding: 1px 6px;
		cursor: pointer;
	}
	.viol-focus:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.viol-msg {
		font-size: var(--text-xs);
		color: var(--fg-1);
		line-height: 1.5;
	}
	.pass-msg {
		display: flex;
		align-items: center;
		gap: var(--s2);
		padding: var(--s2) var(--s3);
		font-size: var(--text-xs);
		color: var(--fg-2);
		background: color-mix(in srgb, var(--success) 8%, var(--bg-2));
		border: 1px solid color-mix(in srgb, var(--success) 22%, var(--border-1));
		border-radius: var(--radius-sm);
	}
	.meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: var(--s2) var(--s3);
		border-radius: var(--radius);
		background: var(--bg-2);
		border: 1px solid var(--border-1);
		font-family: var(--font-mono);
		font-size: 10.5px;
		font-variant-numeric: tabular-nums;
	}
	.meta-row {
		display: grid;
		grid-template-columns: 5rem 1fr;
		column-gap: var(--s3);
		padding: 3px 0;
	}
	.meta-row + .meta-row {
		border-top: 1px dashed color-mix(in srgb, var(--border-1) 60%, transparent);
	}
	.meta dt {
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.meta dd {
		color: var(--fg-1);
		margin: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.meta dd .ok {
		color: var(--success);
	}
	.meta dd .warn {
		color: var(--warning, var(--accent));
	}
	.recheck {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
	}
	.recheck-btn {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-3);
		background: transparent;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		padding: 3px 8px;
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out);
	}
	.recheck-btn:hover:not([disabled]) {
		color: var(--fg-1);
		border-color: var(--accent);
	}
	.recheck-btn[disabled] {
		cursor: default;
		color: var(--fg-4);
	}
	.recheck-out {
		font-size: 10px;
		color: var(--fg-3);
		font-variant-numeric: tabular-nums;
	}
	.recheck-out.ok {
		color: var(--success);
	}
	.recheck-out.bad {
		color: var(--danger);
	}
	.recheck-note {
		font-size: 9px;
		color: var(--fg-4);
	}
	.whatif {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
	}
	/* Quieter than .recheck-btn on purpose: at rest this is one muted line of
	   text, not a control competing with the verdict above it. */
	.whatif-ask {
		font-size: 10px;
		color: var(--fg-4);
		background: transparent;
		border: 0;
		padding: 0;
		text-align: left;
		cursor: pointer;
		transition: color var(--duration-fast) var(--ease-out);
	}
	button.whatif-ask:hover {
		color: var(--fg-1);
		text-decoration: underline;
		text-decoration-style: dotted;
	}
	.whatif-ask.running {
		color: var(--fg-3);
		cursor: default;
	}
	.whatif-head {
		display: flex;
		align-items: baseline;
		gap: var(--s3);
	}
	.whatif-head .section-label {
		margin-bottom: 0;
	}
	.whatif-diff {
		font-size: 10px;
		color: var(--fg-3);
		word-break: break-all;
	}
	.whatif-diff .minus {
		color: var(--danger);
	}
	.viol-node {
		font-size: 10px;
		color: var(--fg-3);
	}
	.whatif-note {
		margin: 0;
		font-size: 9px;
		line-height: 1.6;
		color: var(--fg-4);
	}
	.src-line {
		display: flex;
		align-items: center;
		gap: var(--s2);
		font-size: 10px;
		color: var(--fg-4);
	}
	.src-key {
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.src-val {
		color: var(--fg-3);
	}
</style>

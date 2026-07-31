// Client-side bounds for the extraction and correction flows — one shared
// module, imported by both, single-sourcing the values the two deleted-era
// server routes each carried their own copy of (extract/+server.ts,
// correct/+server.ts). Values are UNCHANGED; what changed is what they
// protect. They were operator-bill defense; with the visitor paying on their
// own key they now bound:
//
//   - the visitor's own spend: every repair round and every inlined
//     correction byte is a paid token on the visitor's OpenRouter key;
//   - verdict latency: each repair round costs a model call plus a full
//     two-gate validation (~3s of Gate 1 + Gate 2 in the browser);
//   - prompt sanity: a 50-edit batch or a 2KB "correction" is a malformed
//     request regardless of who pays for it;
//   - envelope comparability: shacl_retries in live envelopes must stay on
//     the same 0-2 ceiling as the baked v1.2 demo corpus, so version '1.2'
//     keeps meaning the same thing across baked and live output.
//
// Orchestrator unit tests pin every value here — changing a bound requires a
// conscious test edit.

/**
 * Repair rounds after the initial extraction (transpile → validate → repair).
 * Two keeps live shacl_retries statistically comparable with the baked
 * corpus and caps worst-case latency at three model calls per extraction.
 */
export const MAX_REPAIR_RETRIES = 2;

// Correction caps: everything below is inlined into the correction prompt,
// so an uncapped field is an uncapped token bill — now the visitor's.

/** 64 KB source document cap: ~10x the largest document ever extracted. */
export const MAX_SOURCE_CHARS = 64 * 1024;

/** Max corrections per batch: ~2x the entity count of a dense scene. */
export const MAX_CORRECTIONS = 50;

/** Per-correction (and scene-note) cap on the serialized item. */
export const MAX_CORRECTION_CHARS = 2 * 1024;

/**
 * How much of a SHACL report a repair prompt carries. A pathological graph
 * can produce an unbounded report; 4000 chars is plenty for the model to see
 * every distinct violation class without the prompt drowning in repetition.
 */
export const SHACL_REPORT_SLICE_CHARS = 4000;

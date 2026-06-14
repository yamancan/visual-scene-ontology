// re-exports for $lib consumers
export type * from './types';
export { scene } from './scene.svelte';

/** Single source of truth for the version string shown in the UI. */
export const VSON_VERSION = 'v1.1';

import type { PageLoad } from './$types';

// Universal load: the manifest is a compile-time constant of the bundle (see
// $lib/prompts/bodies). Dynamic-imported so the ~36 KB of prompt text rides
// this route's chunk graph only — no other page pays for it.
export const load: PageLoad = async () => {
	const { loadSkillManifest } = await import('$lib/prompts/bodies');
	return {
		skills: loadSkillManifest()
	};
};

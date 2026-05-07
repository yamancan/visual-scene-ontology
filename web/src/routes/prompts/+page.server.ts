import type { PageServerLoad } from './$types';
import { loadSkillManifest } from '$lib/server/prompt';

export const load: PageServerLoad = () => {
	return {
		skills: loadSkillManifest()
	};
};

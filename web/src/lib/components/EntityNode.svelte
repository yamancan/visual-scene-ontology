<script lang="ts">
	import { Handle, Position, type Node, type NodeProps } from '@xyflow/svelte';
	import EntityCard from './EntityCard.svelte';
	import { scene } from '$lib/scene.svelte';
	import type { EntityCardModel } from '$lib/render/sceneView';

	type EntityNodeT = Node<{ entity: EntityCardModel }, 'entity'>;
	let { data, id }: NodeProps<EntityNodeT> = $props();

	let entity = $derived(data.entity);
	let selected = $derived(scene.selectedNodeId === id);

	function onSelect(targetId: string) {
		scene.setSelected(scene.selectedNodeId === targetId ? null : targetId);
	}
</script>

<Handle type="target" position={Position.Left} class="vson-handle" />
<EntityCard {entity} {selected} onselect={onSelect} />
<Handle type="source" position={Position.Right} class="vson-handle" />

<style>
	:global(.svelte-flow__node-entity) {
		padding: 0;
		border: 0;
		background: transparent;
		width: auto;
		min-width: 220px;
		max-width: 280px;
	}
	:global(.svelte-flow__handle.vson-handle) {
		width: 8px;
		height: 8px;
		background: var(--fg-4);
		border: 1px solid var(--bg-1);
	}
</style>

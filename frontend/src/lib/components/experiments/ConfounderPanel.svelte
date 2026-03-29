<script lang="ts">
	import type { ConfounderCheck } from '$lib/api';

	let { confounders }: { confounders: ConfounderCheck[] } = $props();
</script>

{#if confounders.length > 0}
	<div class="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5">
		<h3 class="mb-3 font-['DM_Mono',monospace] text-sm text-[#8a9baa]">Confounders</h3>

		<div class="space-y-2">
			{#each confounders as c}
				<div class="flex items-start gap-2 text-sm">
					{#if c.is_significant}
						<span class="mt-0.5 text-[#D4944C]">!</span>
					{:else}
						<span class="mt-0.5 text-[#4CAF82]">ok</span>
					{/if}
					<div class="min-w-0 flex-1">
						<span class="text-[#b8c8d4]">{c.note}</span>
						{#if c.delta_pct != null}
							<span
								class="ml-1.5 text-xs"
								class:text-[#D4944C]={c.is_significant}
								class:text-[#5e7282]={!c.is_significant}
							>
								({c.delta_pct > 0 ? '+' : ''}{c.delta_pct.toFixed(1)}%)
							</span>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	</div>
{/if}

<script lang="ts">
	type Variant = 'standard' | 'compact' | 'panel';

	let {
		message,
		dismiss,
		variant = 'standard'
	}: { message: string; dismiss: () => void; variant?: Variant } = $props();
</script>

<div class="inline-error" class:compact={variant === 'compact'} class:panel={variant === 'panel'}>
	<p>Error: {message}</p>
	<button type="button" onclick={dismiss} aria-label="Dismiss error">✕</button>
</div>

<style>
	.inline-error {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin: 0 0 16px;
		padding: 12px;
		border: 1px solid rgba(232, 93, 74, 0.3);
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.08);
		color: #e85d4a;
	}

	.inline-error.compact {
		margin-bottom: 18px;
		padding: 10px 14px;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	.inline-error.panel {
		margin-bottom: 14px;
		padding: 20px;
		border-radius: 10px;
	}

	button {
		flex-shrink: 0;
		border: 0;
		padding: 2px 4px;
		background: transparent;
		color: inherit;
		font-size: 12px;
		line-height: 1;
		cursor: pointer;
		opacity: 0.7;
	}

	button:hover {
		opacity: 1;
	}
</style>

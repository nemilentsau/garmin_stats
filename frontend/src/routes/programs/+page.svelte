<script lang="ts">
	import { api, type Program, type ProgramVersion } from '$lib/api';

	let programs = $state<Program[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let filterStatus = $state<string>('all');
	let expandedId = $state<string | null>(null);
	let versions = $state<ProgramVersion[]>([]);
	let versionsLoading = $state(false);
	let importMode = $state(false);
	let importJson = $state('');
	let importError = $state<string | null>(null);
	let importing = $state(false);

	const filtered = $derived(
		filterStatus === 'all'
			? programs
			: programs.filter((p) => p.status === filterStatus)
	);

	async function loadPrograms() {
		loading = true;
		error = null;
		try {
			const res = await api.getPrograms();
			programs = res.programs;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load programs';
		} finally {
			loading = false;
		}
	}

	async function toggleExpand(programId: string) {
		if (expandedId === programId) {
			expandedId = null;
			versions = [];
			return;
		}
		expandedId = programId;
		versionsLoading = true;
		try {
			const res = await api.getProgramVersions(programId);
			versions = res.versions;
		} catch {
			versions = [];
		} finally {
			versionsLoading = false;
		}
	}

	async function retire(programId: string) {
		await api.retireProgram(programId);
		await loadPrograms();
	}

	async function activate(programId: string) {
		await api.activateProgram(programId);
		await loadPrograms();
	}

	async function doImport() {
		importError = null;
		importing = true;
		try {
			const spec = JSON.parse(importJson);
			await api.importProgram(spec);
			importMode = false;
			importJson = '';
			await loadPrograms();
		} catch (e) {
			importError = e instanceof Error ? e.message : 'Invalid JSON';
		} finally {
			importing = false;
		}
	}

	$effect(() => {
		loadPrograms();
	});

	function protocolCount(p: Program): number {
		const spec = p.spec as Record<string, unknown>;
		return Array.isArray(spec?.protocols) ? spec.protocols.length : 0;
	}

	function experimentCount(p: Program): number {
		const spec = p.spec as Record<string, unknown>;
		return Array.isArray(spec?.experiments) ? spec.experiments.length : 0;
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '\u2014';
		const d = new Date(iso);
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
	}
</script>

<svelte:head>
	<title>Programs - Garmin Stats</title>
</svelte:head>

<div class="programs-page">
	<div class="page-header">
		<div class="header-left">
			<h1 class="page-title">Programs</h1>
			<div class="filter-bar">
				{#each ['all', 'active', 'retired', 'draft'] as status}
					<button
						class="filter-btn"
						class:active={filterStatus === status}
						onclick={() => (filterStatus = status)}
					>
						{status[0].toUpperCase() + status.slice(1)}
					</button>
				{/each}
			</div>
		</div>
		<button class="import-btn" onclick={() => (importMode = !importMode)}>
			{importMode ? 'Cancel' : 'Import'}
		</button>
	</div>

	{#if importMode}
		<div class="import-panel">
			<textarea
				class="import-textarea"
				placeholder="Paste program spec JSON here..."
				bind:value={importJson}
				rows={8}
			></textarea>
			{#if importError}
				<p class="import-error">{importError}</p>
			{/if}
			<button class="do-import-btn" onclick={doImport} disabled={importing || !importJson.trim()}>
				{importing ? 'Importing...' : 'Import Program'}
			</button>
		</div>
	{/if}

	{#if loading}
		<p class="status-msg">Loading programs...</p>
	{:else if error}
		<p class="status-msg error">{error}</p>
	{:else if filtered.length === 0}
		<p class="status-msg">No programs found. Import a program spec to get started.</p>
	{:else}
		<div class="program-list">
			{#each filtered as program (program.id)}
				<div class="program-card" class:expanded={expandedId === program.id}>
					<button class="program-header" onclick={() => toggleExpand(program.id)}>
						<div class="program-info">
							<div class="program-name-row">
								<h2 class="program-name">{program.name}</h2>
								<span class="status-badge" class:active={program.status === 'active'} class:retired={program.status === 'retired'}>
									{program.status}
								</span>
							</div>
							<div class="program-meta">
								<span class="meta-item">v{program.version}</span>
								<span class="meta-sep">&middot;</span>
								<span class="meta-item">{protocolCount(program)} protocols</span>
								<span class="meta-sep">&middot;</span>
								<span class="meta-item">{experimentCount(program)} experiments</span>
								<span class="meta-sep">&middot;</span>
								<span class="meta-item">imported {formatDate(program.imported_at)}</span>
							</div>
						</div>
						<span class="expand-icon">{expandedId === program.id ? '\u25B2' : '\u25BC'}</span>
					</button>

					{#if expandedId === program.id}
						<div class="program-detail">
							<div class="detail-grid">
								<div class="detail-block">
									<span class="detail-label">ID</span>
									<span class="detail-value mono">{program.id}</span>
								</div>
								<div class="detail-block">
									<span class="detail-label">VERSION</span>
									<span class="detail-value">{program.version}</span>
								</div>
								<div class="detail-block">
									<span class="detail-label">STATUS</span>
									<span class="detail-value">{program.status}</span>
								</div>
								<div class="detail-block">
									<span class="detail-label">IMPORTED</span>
									<span class="detail-value">{formatDate(program.imported_at)}</span>
								</div>
								<div class="detail-block">
									<span class="detail-label">UPDATED</span>
									<span class="detail-value">{formatDate(program.updated_at)}</span>
								</div>
								{#if program.retired_at}
									<div class="detail-block">
										<span class="detail-label">RETIRED</span>
										<span class="detail-value">{formatDate(program.retired_at)}</span>
									</div>
								{/if}
							</div>

							<div class="detail-actions">
								{#if program.status === 'active'}
									<button class="action-btn retire" onclick={() => retire(program.id)}>
										Retire Program
									</button>
								{:else if program.status === 'retired'}
									<button class="action-btn activate" onclick={() => activate(program.id)}>
										Reactivate Program
									</button>
								{/if}
							</div>

							<div class="versions-section">
								<h3 class="versions-title">Version History</h3>
								{#if versionsLoading}
									<p class="versions-status">Loading...</p>
								{:else if versions.length === 0}
									<p class="versions-status">No previous versions.</p>
								{:else}
									<div class="versions-list">
										{#each versions as ver}
											<div class="version-row">
												<span class="version-num">v{ver.version}</span>
												<span class="version-date">{formatDate(ver.imported_at)}</span>
											</div>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.programs-page {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.page-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
	}

	.header-left {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.page-title {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 24px;
		font-weight: 700;
		color: #e8f0f5;
		margin: 0;
	}

	.filter-bar {
		display: flex;
		gap: 4px;
	}

	.filter-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 4px 10px;
		border-radius: 4px;
		border: none;
		background: transparent;
		color: #4a5e6d;
		cursor: pointer;
		transition: all 0.2s;
	}

	.filter-btn:hover {
		color: #8fa3b0;
	}

	.filter-btn.active {
		color: #5BB5A6;
		background: rgba(91, 181, 166, 0.08);
	}

	.import-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 14px;
		border-radius: 6px;
		border: 1px solid rgba(91, 181, 166, 0.3);
		background: rgba(91, 181, 166, 0.08);
		color: #5BB5A6;
		cursor: pointer;
		transition: all 0.2s;
	}

	.import-btn:hover {
		background: rgba(91, 181, 166, 0.15);
	}

	.import-panel {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.import-textarea {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		background: rgba(0, 0, 0, 0.2);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 6px;
		color: #c8d6e0;
		padding: 12px;
		resize: vertical;
	}

	.import-textarea::placeholder {
		color: #3a4e5d;
	}

	.import-error {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #e06b6b;
		margin: 0;
	}

	.do-import-btn {
		align-self: flex-end;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 14px;
		border-radius: 6px;
		border: none;
		background: #5BB5A6;
		color: #0d1520;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.do-import-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.do-import-btn:hover:not(:disabled) {
		background: #6dc7b8;
	}

	.status-msg {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #5e7282;
		padding: 32px 0;
		text-align: center;
	}

	.status-msg.error {
		color: #e06b6b;
	}

	.program-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.program-card {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 8px;
		overflow: hidden;
		transition: border-color 0.2s;
	}

	.program-card:hover {
		border-color: rgba(255, 255, 255, 0.1);
	}

	.program-card.expanded {
		border-color: rgba(91, 181, 166, 0.2);
	}

	.program-header {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		background: transparent;
		border: none;
		cursor: pointer;
		text-align: left;
		color: inherit;
	}

	.program-info {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.program-name-row {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.program-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 16px;
		font-weight: 600;
		color: #e8f0f5;
		margin: 0;
	}

	.status-badge {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.5px;
		padding: 2px 8px;
		border-radius: 4px;
		text-transform: uppercase;
	}

	.status-badge.active {
		color: #5BB5A6;
		background: rgba(91, 181, 166, 0.12);
	}

	.status-badge.retired {
		color: #8fa3b0;
		background: rgba(143, 163, 176, 0.1);
	}

	.program-meta {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.meta-sep {
		color: #3a4e5d;
	}

	.expand-icon {
		font-size: 10px;
		color: #4a5e6d;
	}

	.program-detail {
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.detail-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
		gap: 12px;
	}

	.detail-block {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.detail-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 1.5px;
		color: #4a5e6d;
	}

	.detail-value {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		color: #c8d6e0;
	}

	.detail-value.mono {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}

	.detail-actions {
		display: flex;
		gap: 8px;
	}

	.action-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 14px;
		border-radius: 6px;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.action-btn.retire {
		background: rgba(224, 107, 107, 0.1);
		color: #e06b6b;
		border: 1px solid rgba(224, 107, 107, 0.2);
	}

	.action-btn.retire:hover {
		background: rgba(224, 107, 107, 0.2);
	}

	.action-btn.activate {
		background: rgba(91, 181, 166, 0.1);
		color: #5BB5A6;
		border: 1px solid rgba(91, 181, 166, 0.2);
	}

	.action-btn.activate:hover {
		background: rgba(91, 181, 166, 0.2);
	}

	.versions-section {
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		padding-top: 16px;
	}

	.versions-title {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 1px;
		color: #5e7282;
		margin: 0 0 10px 0;
		text-transform: uppercase;
	}

	.versions-status {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5e6d;
		margin: 0;
	}

	.versions-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.version-row {
		display: flex;
		align-items: center;
		gap: 12px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
	}

	.version-num {
		color: #5BB5A6;
		min-width: 32px;
	}

	.version-date {
		color: #5e7282;
	}
</style>

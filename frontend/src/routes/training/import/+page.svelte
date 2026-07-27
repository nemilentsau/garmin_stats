<script lang="ts">
	/**
	 * Training Import — upload one authored v3 ZIP package, review the backend's contained
	 * artifact validation and lint report, acknowledge warnings, and activate.
	 *
	 * This page never opens or interprets the package. It base64-encodes the selected ZIP for
	 * the JSON API boundary; every package, artifact, lint, and rollup judgment rendered here
	 * comes straight from `ImportResult` / `LintReport` as returned by
	 * `POST /api/training/import`.
	 */
	import { onMount } from 'svelte';
	import { api, ApiError, type ImportResult, type TrainingBlockStatus } from '$lib/api';
	import { fmtFullDate, isIsoDateString, parseIsoDate } from '$lib/date';
	import { fmt } from '$lib/format';
	import { errorMessage } from '$lib/utils';

	type SelectedPackage = {
		filename: string;
		size: number;
		contentBase64: string;
	};
	let blockLoading = $state(true);
	let blockStatus = $state<TrainingBlockStatus | null>(null);
	let blockLoadError = $state<string | null>(null);

	let selectedPackage = $state<SelectedPackage | null>(null);
	let startDate = $state('');
	let packageReading = $state(false);
	let selectionVersion = 0;

	let importing = $state(false);
	let importError = $state<string | null>(null);
	let result = $state<ImportResult | null>(null);
	let activatedStartDate = $state<string | null>(null);
	let ackedWarnings = $state<string[]>([]);

	const canImport = $derived(
		selectedPackage !== null && isIsoDateString(startDate) && !packageReading && !importing
	);
	const lintReport = $derived(result?.lint_report ?? null);

	const weekKeys = $derived.by(() => {
		if (!lintReport) return [];
		const keys = new Set([
			...Object.keys(lintReport.week_run_miles),
			...Object.keys(lintReport.week_minutes_by_bundle)
		]);
		return [...keys].sort((a, b) => Number(a) - Number(b));
	});

	const bundleIds = $derived.by(() => {
		if (!lintReport) return [];
		const ids = new Set<string>();
		for (const week of Object.values(lintReport.week_minutes_by_bundle)) {
			for (const id of Object.keys(week)) ids.add(id);
		}
		return [...ids].sort();
	});

	const allWarningsAcked = $derived(
		(lintReport?.warnings ?? []).every((w) => ackedWarnings.includes(w))
	);

	/** Fetch active-block state without hiding transport/server failures as an empty state. */
	async function loadBlockStatus(): Promise<void> {
		try {
			blockStatus = await api.getTrainingBlock();
			blockLoadError = null;
		} catch (error: unknown) {
			blockStatus = null;
			blockLoadError =
				error instanceof ApiError && error.status === 404 ? null : errorMessage(error);
		}
	}

	function fmtBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function fmtProgramDate(date: string): string {
		return fmtFullDate(parseIsoDate(date));
	}

	function bytesToBase64(bytes: Uint8Array): string {
		const chunkSize = 0x8000;
		let binary = '';
		for (let offset = 0; offset < bytes.length; offset += chunkSize) {
			binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
		}
		return btoa(binary);
	}

	async function handleFileSelection(e: Event): Promise<void> {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0] ?? null;
		if (!file) return;
		const version = ++selectionVersion;
		packageReading = true;
		selectedPackage = null;
		result = null;
		activatedStartDate = null;
		importError = null;
		ackedWarnings = [];
		try {
			const nextPackage = {
				filename: file.name,
				size: file.size,
				contentBase64: bytesToBase64(new Uint8Array(await file.arrayBuffer()))
			};
			if (version === selectionVersion) selectedPackage = nextPackage;
		} catch (e: unknown) {
			if (version === selectionVersion) importError = errorMessage(e);
		} finally {
			if (version === selectionVersion) packageReading = false;
		}
	}

	function onWarningAckChange(warning: string, e: Event): void {
		const checked = (e.currentTarget as HTMLInputElement).checked;
		ackedWarnings = checked ? [...ackedWarnings, warning] : ackedWarnings.filter((w) => w !== warning);
	}

	async function handleImport(): Promise<void> {
		if (!selectedPackage) return;
		const submittedStartDate = startDate;
		importing = true;
		importError = null;
		try {
			result = await api.importTraining({
				filename: selectedPackage.filename,
				content_base64: selectedPackage.contentBase64,
				start_date: submittedStartDate,
				warning_acks: ackedWarnings
			});
			if (result.activated) {
				activatedStartDate = submittedStartDate;
				await loadBlockStatus();
			}
		} catch (e: unknown) {
			importError = errorMessage(e);
		} finally {
			importing = false;
		}
	}

	onMount(() => {
		void loadBlockStatus().finally(() => {
			blockLoading = false;
		});
	});
</script>

<svelte:head>
	<title>Training Import - Garmin Stats</title>
</svelte:head>

<section class="import-shell">
	<div class="header-bar">
		<h1>Training Import</h1>
		<div
			class="block-status"
			class:empty={!blockLoading && !blockStatus && !blockLoadError}
			class:error={blockLoadError !== null}
		>
			{#if blockLoading}
				Checking active block&hellip;
			{:else if blockLoadError}
				Unable to check active block: {blockLoadError}
			{:else if blockStatus}
				<span class="block-name">{blockStatus.block_name}</span>
				<span>Starts {fmtProgramDate(blockStatus.schedule_start)}</span>
				{#if blockStatus.current_day !== null}
					<span class="block-day">Day {blockStatus.current_day} of {blockStatus.block.window.days}</span>
				{/if}
				{#if blockStatus.burn_in}
					<span class="burn-in-tag">burn-in</span>
				{/if}
			{:else}
				No active block — import one.
			{/if}
		</div>
	</div>

	<div class="panel">
		<div class="panel-header">
			<h2>Training package</h2>
			<span class="hint">one .zip — one authored program</span>
		</div>

		<div class="package-controls">
			<label class="file-picker">
				<span>Program package</span>
				<input
					type="file"
					accept=".zip,application/zip"
					disabled={importing}
					onclick={(e) => ((e.currentTarget as HTMLInputElement).value = '')}
					onchange={handleFileSelection}
				/>
			</label>
			<label class="start-field">
				<span>Program starts</span>
				<input type="date" bind:value={startDate} required disabled={importing} />
			</label>
		</div>

		{#if packageReading}
			<div class="package-summary loading">Reading package&hellip;</div>
		{:else if selectedPackage}
			<div class="package-summary">
				<div>
					<div class="package-name">{selectedPackage.filename}</div>
					<div class="hint">Contents will be validated by the backend before activation.</div>
				</div>
				<span class="package-size">{fmtBytes(selectedPackage.size)}</span>
			</div>
		{/if}

		<div class="import-actions">
			<button type="button" class="action-btn primary" disabled={!canImport} onclick={() => void handleImport()}>
				{importing ? 'Importing…' : 'Import package'}
			</button>
		</div>

		{#if importError}
			<div class="error-banner">{importError}</div>
		{/if}
	</div>

	{#if result}
		<div class="panel">
			{#if result.activated && activatedStartDate}
				<div class="success-banner">Program activated for {fmtProgramDate(activatedStartDate)}. <a href="/today">Go to Today</a></div>
			{/if}

			<div class="panel-header">
				<h2>File Validation</h2>
			</div>
			<table class="data-table">
				<colgroup>
					<col />
					<col style="width: 110px" />
					<col style="width: 60px" />
					<col />
				</colgroup>
				<thead>
					<tr>
						<th>filename</th>
						<th>kind</th>
						<th class="status-col">valid</th>
						<th>errors</th>
					</tr>
				</thead>
				<tbody>
					{#each result.files as f (f.filename)}
						<tr class:invalid={!f.valid}>
							<td>{f.filename}</td>
							<td>{f.kind ?? '—'}</td>
							<td class="status-col">
								<span class="status-mark" class:ok={f.valid} class:bad={!f.valid}>{f.valid ? '✓' : '✗'}</span>
							</td>
							<td class="error-text">{f.errors.join('; ')}</td>
						</tr>
					{/each}
				</tbody>
			</table>

			{#if result.missing_kinds.length > 0}
				<div class="notice-banner">Missing kinds: {result.missing_kinds.join(', ')}</div>
			{/if}

			{#if lintReport}
				<div class="panel-header">
					<h2>Lint Report</h2>
				</div>

				{#if lintReport.errors.length > 0}
					<div class="issue-list">
						{#each lintReport.errors as err}
							<div class="issue-row">{err}</div>
						{/each}
					</div>
				{/if}

				{#if lintReport.warnings.length > 0}
					<div class="warning-list">
						{#each lintReport.warnings as warning}
							<label class="warning-row">
								<input
									type="checkbox"
									checked={ackedWarnings.includes(warning)}
									onchange={(e) => onWarningAckChange(warning, e)}
								/>
								<span>{warning}</span>
							</label>
						{/each}
					</div>
					{#if !allWarningsAcked}
						<div class="hint warning-hint">Acknowledge all warnings, then re-import to activate.</div>
					{/if}
				{/if}

				{#if weekKeys.length > 0}
					<div class="panel-header">
						<h3>Weekly Run Miles</h3>
					</div>
					<table class="data-table stat-table">
						<thead>
							<tr>
								<th>week</th>
								<th class="num">miles</th>
							</tr>
						</thead>
						<tbody>
							{#each weekKeys as wk}
								<tr>
									<td>Week {wk}</td>
									<td class="num">{fmt(lintReport.week_run_miles[wk])}</td>
								</tr>
							{/each}
						</tbody>
					</table>

					<div class="panel-header">
						<h3>Weekly Minutes by Bundle</h3>
					</div>
					<div class="table-scroll">
						<table class="data-table stat-table">
							<thead>
								<tr>
									<th>week</th>
									{#each bundleIds as bundleId}
										<th class="num">{bundleId}</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each weekKeys as wk}
									<tr>
										<td>Week {wk}</td>
										{#each bundleIds as bundleId}
											<td class="num">{fmt(lintReport.week_minutes_by_bundle[wk]?.[bundleId])}</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</section>

<style>
	.import-shell {
		--paper: rgba(255, 255, 255, 0.035);
		--paper-border: rgba(255, 255, 255, 0.08);
		--muted: #7f95a6;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.header-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 12px 16px;
		border-radius: 14px;
		background: var(--paper);
		border: 1px solid var(--paper-border);
	}

	.header-bar h1 {
		margin: 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 20px;
		font-weight: 600;
		color: #eef5f8;
	}

	.block-status {
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: var(--muted);
		white-space: nowrap;
	}

	.block-status.empty {
		color: #6b8292;
	}

	.block-status.error {
		color: #df7d86;
	}

	.block-name {
		color: #eef5f8;
		font-weight: 500;
	}

	.burn-in-tag {
		padding: 1px 6px;
		border-radius: 3px;
		font-size: 10px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		background: rgba(212, 148, 76, 0.15);
		color: #d4944c;
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px;
		border-radius: 14px;
		background: var(--paper);
		border: 1px solid var(--paper-border);
	}

	.panel-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
	}

	.panel-header h2 {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
		font-weight: 600;
	}

	.panel-header h3 {
		margin: 4px 0 0;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #6b8292;
		font-weight: 600;
	}

	.hint {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
	}

	.warning-hint {
		color: #d4944c;
	}

	.package-controls {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 24px;
	}

	.file-picker,
	.start-field {
		display: flex;
		flex-direction: column;
		gap: 7px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.file-picker {
		flex: 1;
	}

	.file-picker input[type='file'] {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
	}

	.start-field input {
		color-scheme: dark;
		min-width: 160px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 8px;
		background: rgba(8, 15, 24, 0.7);
		color: #c8d6df;
		padding: 7px 10px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		font-variant-numeric: tabular-nums lining-nums;
	}

	.file-picker input[type='file']::file-selector-button {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: #5bb5a6;
		background: rgba(91, 181, 166, 0.12);
		border: 1px solid rgba(91, 181, 166, 0.3);
		border-radius: 8px;
		padding: 6px 12px;
		margin-right: 10px;
		cursor: pointer;
		transition: background 0.15s;
	}

	.file-picker input[type='file']::file-selector-button:hover {
		background: rgba(91, 181, 166, 0.22);
	}

	.package-summary {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 10px 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.package-summary.loading {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
	}

	.package-name,
	.package-size {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #c3d3dd;
	}

	.package-name {
		margin-bottom: 3px;
	}

	.package-size {
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
	}

	.table-scroll {
		overflow-x: auto;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}

	.data-table thead th {
		font-weight: 500;
		font-size: 11px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 4px 10px;
		text-align: left;
		white-space: nowrap;
	}

	.data-table tbody td {
		padding: 7px 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		vertical-align: middle;
		color: #c3d3dd;
	}

	.data-table tr.invalid td {
		background: rgba(232, 93, 74, 0.05);
	}

	.num,
	.data-table th.num {
		text-align: right;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
	}

	.status-col {
		text-align: center;
	}

	.status-mark {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	.status-mark.ok {
		color: #5bb5a6;
	}

	.status-mark.bad {
		color: #e85d4a;
	}

	.error-text {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #f2a399;
	}

	.import-actions {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.action-btn {
		padding: 8px 16px;
		border-radius: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
		cursor: pointer;
		transition: background 0.15s;
	}

	.action-btn.primary {
		background: rgba(91, 181, 166, 0.15);
		border: 1px solid rgba(91, 181, 166, 0.3);
		color: #5bb5a6;
	}

	.action-btn.primary:hover:not(:disabled) {
		background: rgba(91, 181, 166, 0.25);
	}

	.action-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.error-banner,
	.notice-banner,
	.success-banner {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		border-radius: 12px;
		padding: 10px 14px;
		border: 1px solid transparent;
	}

	.error-banner {
		color: #f2a399;
		border-color: rgba(232, 93, 74, 0.3);
		background: rgba(232, 93, 74, 0.08);
	}

	.notice-banner {
		color: #d4944c;
		border-color: rgba(212, 148, 76, 0.3);
		background: rgba(212, 148, 76, 0.08);
	}

	.success-banner {
		color: #5bb5a6;
		border-color: rgba(91, 181, 166, 0.3);
		background: rgba(91, 181, 166, 0.08);
	}

	.success-banner a {
		color: inherit;
		text-decoration: underline;
	}

	.issue-list,
	.warning-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 220px;
		overflow-y: auto;
	}

	.issue-row {
		padding: 6px 10px;
		border-radius: 6px;
		background: rgba(232, 93, 74, 0.06);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #f2a399;
	}

	.warning-row {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 6px 10px;
		border-radius: 6px;
		background: rgba(212, 148, 76, 0.06);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #e0c19a;
		cursor: pointer;
	}

	.warning-row input {
		margin-top: 2px;
		flex-shrink: 0;
		accent-color: #5bb5a6;
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';

	import {
		api,
		type ArtifactBundleImportResponse,
		type ArtifactBundlePreviewResponse,
		type ArtifactBundleSpec,
		type AssistantArtifact,
		type CardTemplate,
		type RoutineSchedule
	} from '$lib/api';
	import { COLORS, withAlpha } from '$lib/colors';
	import { errorMessage } from '$lib/utils';

	const artifactStatusAccent: Record<string, string> = {
		validated: COLORS.respiration,
		invalid: COLORS.heartRate,
		activated: COLORS.bodyBattery,
		draft: COLORS.stress
	};

	const bundleStarter: ArtifactBundleSpec = {
		id: 'proper-routine-bundle',
		name: 'Proper Routine Bundle',
		schema_version: 1,
		description: 'Starter proper-spec bundle. Replace with LLM-authored JSON before previewing.',
		card_templates: [
			{
				id: 'starter-breathing-card',
				name: 'Starter Breathing Card',
				renderer: 'timer_session',
				slot_default: 'morning',
				summary: 'Reusable breathwork card template.',
				tags: ['starter', 'breathwork'],
				payload: {
					duration_minutes: 8,
					pattern: '5s in / 5s out',
					instructions: 'Keep the breath smooth and relaxed.',
					rating_prompts: [
						{ key: 'attention_stability', label: 'Attention stability', scale_min: 1, scale_max: 5 }
					]
				}
			}
		],
		routine_specs: [
			{
				id: 'starter-routine',
				name: 'Starter Routine',
				cadence: 'weekly',
				start_date: '2026-03-16',
				status: 'active',
				tags: ['starter'],
				notes: 'One routine schedule driven by the proper bundle format.',
				assignments: [
					{
						id: 'starter-routine-mon-morning',
						card_template_id: 'starter-breathing-card',
						cycle_week: 1,
						weekday: 'monday',
						slot: 'morning',
						position: 10,
						prescription_override_json: {
							duration_minutes: 10,
							instructions: 'Assignment overrides change dose without creating a new card template.'
						}
					}
				]
			}
		]
	};

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);

	let artifacts = $state<AssistantArtifact[]>([]);
	let cards = $state<CardTemplate[]>([]);
	let routines = $state<RoutineSchedule[]>([]);

	let bundleJson = $state(JSON.stringify(bundleStarter, null, 2));
	let preview = $state<ArtifactBundlePreviewResponse | null>(null);
	let importResult = $state<ArtifactBundleImportResponse | null>(null);
	let lastPreviewSource = $state('');
	let showPayloads = $state<Record<string, boolean>>({});

	const inboxArtifacts = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status !== 'activated')
	);
	const validatedCount = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status === 'validated').length
	);
	const invalidCount = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status === 'invalid').length
	);
	const capabilityCount = $derived.by(() =>
		artifacts.filter((artifact) => artifact.kind === 'capability_request').length
	);
	const previewDeltas = $derived.by(() => preview?.deltas ?? []);
	const previewIssues = $derived.by(() => preview?.issues ?? []);
	const previewIsStale = $derived.by(() => lastPreviewSource !== '' && bundleJson !== lastPreviewSource);
	const canImport = $derived.by(
		() => !saving && preview?.valid === true && lastPreviewSource === bundleJson
	);

	function artifactTargetId(artifact: AssistantArtifact): string | null {
		const payload = artifact.payload_json as Record<string, unknown>;
		return typeof payload.id === 'string' ? payload.id : null;
	}

	function artifactDelta(artifact: AssistantArtifact): string {
		if (artifact.kind === 'card_template') {
			const targetId = artifactTargetId(artifact);
			const existing = targetId ? cards.find((card) => card.id === targetId) : null;
			return existing ? 'Updates an active live card' : 'Creates a new live card';
		}
		if (artifact.kind === 'routine_spec') {
			const payload = artifact.payload_json as Record<string, unknown>;
			const targetId = artifactTargetId(artifact);
			const existing = targetId ? routines.find((routine) => routine.id === targetId) : null;
			const assignmentCount = Array.isArray(payload.assignments) ? payload.assignments.length : 0;
			return `${existing ? 'Updates' : 'Creates'} a live routine · ${assignmentCount} assignments`;
		}
		return 'Requests a renderer capability that the app does not ship yet';
	}

	function artifactSummary(artifact: AssistantArtifact): string {
		const payload = artifact.payload_json as Record<string, unknown>;
		if (artifact.kind === 'card_template') {
			return `${String(payload.renderer ?? 'unknown')} · ${String(payload.slot_default ?? 'unslotted')}`;
		}
		if (artifact.kind === 'routine_spec') {
			return `${String(payload.cadence ?? 'unknown')} cadence · starts ${String(payload.start_date ?? 'unknown')}`;
		}
		return String(payload.requested_renderer ?? 'missing capability');
	}

	async function loadPage() {
		error = null;
		const [artifactsResponse, cardsResponse, routinesResponse] = await Promise.all([
			api.getAssistantArtifacts(),
			api.getCards('active'),
			api.getRoutines('active')
		]);
		artifacts = artifactsResponse.artifacts;
		cards = cardsResponse.cards;
		routines = routinesResponse.routines;
	}

	function shouldAutoPreview(): boolean {
		const value = new URL(window.location.href).searchParams.get('autopreview');
		return value === '1' || value === 'true';
	}

	onMount(() => {
		void (async () => {
			await loadPage();
			if (shouldAutoPreview()) {
				await previewBundle();
			}
		})()
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	function resetBundle() {
		bundleJson = JSON.stringify(bundleStarter, null, 2);
		preview = null;
		importResult = null;
		lastPreviewSource = '';
		error = null;
	}

	async function previewBundle() {
		saving = true;
		error = null;
		importResult = null;
		try {
			const payload = JSON.parse(bundleJson) as ArtifactBundleSpec;
			preview = await api.previewAssistantArtifactBundle(payload);
			lastPreviewSource = bundleJson;
		} catch (e: unknown) {
			error = errorMessage(e);
			preview = null;
			lastPreviewSource = '';
		} finally {
			saving = false;
		}
	}

	async function importBundle() {
		if (!canImport) {
			return;
		}

		saving = true;
		error = null;
		try {
			const payload = JSON.parse(bundleJson) as ArtifactBundleSpec;
			importResult = await api.importAssistantArtifactBundle(payload);
			await loadPage();
		} catch (e: unknown) {
			error = errorMessage(e);
			importResult = null;
		} finally {
			saving = false;
		}
	}

	async function activateArtifact(artifactId: string) {
		saving = true;
		error = null;
		try {
			await api.activateAssistantArtifact(artifactId);
			await loadPage();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	function togglePayload(artifactId: string) {
		showPayloads = { ...showPayloads, [artifactId]: !showPayloads[artifactId] };
	}
</script>

<svelte:head>
	<title>Routine Creation - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Opening routine creation flow...</div>
	</section>
{:else}
	<section class="creation-shell">
		<div
			class="hero"
			style={`--hero-a: ${withAlpha(COLORS.respiration, '2f')}; --hero-b: ${withAlpha(COLORS.hrv, '2f')};`}
		>
			<div class="hero-copy">
				<p class="eyebrow">Routine Creation</p>
				<h1>Paste one proper bundle, preview it cleanly, then import drafts for activation.</h1>
				<p>
					The app accepts deterministic bundle JSON only. Markdown conversion happens outside the
					runtime. Nothing touches the live schedule until preview passes, drafts import, and you
					explicitly activate them.
				</p>
			</div>
			<div class="summary-row">
				<div class="summary-stat">
					<span>Inbox</span>
					<strong>{inboxArtifacts.length}</strong>
				</div>
				<div class="summary-stat">
					<span>Validated</span>
					<strong>{validatedCount}</strong>
				</div>
				<div class="summary-stat">
					<span>Invalid</span>
					<strong>{invalidCount}</strong>
				</div>
				<div class="summary-stat accent">
					<span>Capability asks</span>
					<strong>{capabilityCount}</strong>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="studio-grid">
			<section class="panel studio-panel">
				<div class="panel-head">
					<p>Bundle Studio</p>
					<h2>Preview the full card + routine package before any draft hits the database.</h2>
				</div>

				<div class="format-banner">
					<strong>Proper spec only.</strong>
					<span>
						Bundle JSON must contain deterministic `card_templates` and `routine_specs`. Resolve any
						state-dependent branching before preview.
					</span>
				</div>

				<label class="wide-field">
					<span>Bundle JSON</span>
					<textarea bind:value={bundleJson} rows="28"></textarea>
				</label>

				<div class="form-actions">
					<button class="ghost-btn" onclick={resetBundle}>Reset starter</button>
					<div class="action-row">
						<button class="ghost-btn" onclick={previewBundle} disabled={saving}>Preview bundle</button>
						<button class="primary-action" onclick={importBundle} disabled={!canImport}>
							Import drafts
						</button>
					</div>
				</div>

				{#if previewIsStale}
					<div class="stale-banner">
						The JSON changed after the last preview. Preview again before importing.
					</div>
				{/if}

				{#if importResult}
					<div class="import-banner">
						<strong>Imported {importResult.total_imported} drafts</strong>
						<span>
							Drafts are in the inbox now. Activation is still explicit and remains the only step that
							compiles live runtime records.
						</span>
					</div>
				{/if}
			</section>

			<section class="panel preview-panel">
				<div class="panel-head">
					<p>Bundle Preview</p>
					<h2>See create/update deltas and blocking issues before import.</h2>
				</div>

				{#if preview === null}
					<div class="empty-card">
						No preview yet. Paste a proper bundle and run preview to inspect deltas without writing any
						drafts.
					</div>
				{:else}
					<div class="preview-status">
						<span class:ok={preview.valid} class:bad={!preview.valid}>
							{preview.valid ? 'Ready to import' : 'Blocking issues found'}
						</span>
						<strong>{preview.bundle_name}</strong>
					</div>

					{#if previewIssues.length > 0}
						<div class="issue-list">
							{#each previewIssues as issue}
								<div class="issue-card">
									<p>{issue.path}</p>
									<strong>{issue.message}</strong>
								</div>
							{/each}
						</div>
					{/if}

					<div class="delta-list">
						{#each previewDeltas as delta}
							<article class="delta-card">
								<div class="delta-topline">
									<p>{delta.kind}</p>
									<span class:ok={delta.action === 'create'} class:bad={delta.action === 'update'}>
										{delta.action}
									</span>
								</div>
								<h3>{delta.target_id}</h3>
								<p>{delta.summary}</p>
								<code>{delta.artifact_id}</code>
							</article>
						{/each}
					</div>
				{/if}
			</section>
		</div>

		<section class="panel inbox-panel">
			<div class="panel-head">
				<p>Draft Inbox</p>
				<h2>Imported drafts stay inert until activation compiles them into live schedule records.</h2>
			</div>

			{#if inboxArtifacts.length === 0}
				<div class="empty-card">
					No draft artifacts are waiting. Preview and import a proper bundle first, then activate the
					validated artifacts you want to ship live.
				</div>
			{:else}
				<div class="artifact-list">
					{#each inboxArtifacts as artifact}
						<article class="artifact-card">
							<div class="artifact-topline">
								<div>
									<p>{artifact.kind}</p>
									<h3>{artifactTargetId(artifact) ?? artifact.id}</h3>
								</div>
								<span
									class="status-badge"
									style={`--status-accent: ${artifactStatusAccent[artifact.status] ?? '#8fa3b0'};`}
								>
									{artifact.status}
								</span>
							</div>

							<div class="artifact-meta">
								<span>{artifactSummary(artifact)}</span>
								<span>{artifactDelta(artifact)}</span>
							</div>

							{#if artifact.validation_errors.length > 0}
								<div class="error-list">
									{#each artifact.validation_errors as validationError}
										<p>{validationError}</p>
									{/each}
								</div>
							{/if}

							<div class="artifact-actions">
								<button class="ghost-btn" onclick={() => togglePayload(artifact.id)}>
									{showPayloads[artifact.id] ? 'Hide payload' : 'Show payload'}
								</button>
								{#if artifact.status === 'validated' && artifact.kind !== 'capability_request'}
									<button class="primary-action" onclick={() => activateArtifact(artifact.id)} disabled={saving}>
										Activate
									</button>
								{/if}
							</div>

							{#if showPayloads[artifact.id]}
								<pre class="payload-view">{JSON.stringify(artifact.payload_json, null, 2)}</pre>
							{/if}
						</article>
					{/each}
				</div>
			{/if}
		</section>

		<section class="panel callout-panel">
			<div class="panel-head">
				<p>Runtime Boundary</p>
				<h2>Drafts author schedule state. Today and Schedule only execute what is already live.</h2>
			</div>
			<div class="callout-grid">
				<div class="callout-card">
					<span>Live routines</span>
					<strong>{routines.length}</strong>
					<p>Compiled routines are reviewed on the schedule page, not edited here.</p>
				</div>
				<div class="callout-card">
					<span>Live cards</span>
					<strong>{cards.length}</strong>
					<p>Card templates are reusable. Assignment overrides change dose without duplicating cards.</p>
				</div>
				<div class="callout-card action">
					<span>Next step</span>
					<strong>Review schedule</strong>
					<p>After activation, confirm the dated occurrences on the 14-day schedule and in Today.</p>
					<a href="/routines/schedule">Open schedule</a>
				</div>
			</div>
		</section>
	</section>
{/if}

<style>
	.creation-shell {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.empty-card,
	.stale-banner,
	.import-banner {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #95aab7;
		padding: 14px 16px;
		border-radius: 18px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.03);
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
		gap: 18px;
		padding: 24px;
		border-radius: 28px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top left, var(--hero-a), transparent 38%),
			radial-gradient(circle at bottom right, var(--hero-b), transparent 42%),
			linear-gradient(145deg, rgba(10, 20, 32, 0.9), rgba(15, 27, 41, 0.84));
	}

	.eyebrow,
	.panel-head p,
	label span,
	.artifact-card p:first-child,
	.delta-card p,
	.issue-card p,
	.callout-card span {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.hero-copy h1,
	.panel-head h2 {
		margin: 8px 0 0;
		font-size: clamp(28px, 4vw, 40px);
		line-height: 1.04;
		color: #eef5f8;
		max-width: 14ch;
	}

	.hero-copy p:last-child {
		max-width: 60ch;
		color: #abc0cb;
		line-height: 1.6;
	}

	.summary-row,
	.studio-grid,
	.callout-grid,
	.action-row,
	.delta-list,
	.issue-list {
		display: grid;
		gap: 12px;
	}

	.summary-row {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-content: start;
	}

	.summary-stat,
	.panel,
	.artifact-card,
	.callout-card,
	.delta-card,
	.issue-card,
	.format-banner,
	.preview-status {
		padding: 16px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.summary-stat span,
	.callout-card span {
		display: block;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.summary-stat strong,
	.callout-card strong {
		display: block;
		margin-top: 10px;
		font-size: 30px;
	}

	.summary-stat.accent {
		background: linear-gradient(140deg, rgba(91, 181, 166, 0.12), rgba(155, 107, 205, 0.12));
	}

	.studio-grid {
		grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.panel-head h2 {
		font-size: 24px;
		max-width: 24ch;
	}

	.format-banner strong,
	.preview-status strong,
	.issue-card strong,
	.delta-card h3 {
		display: block;
		color: #eef5f8;
	}

	.format-banner {
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: linear-gradient(145deg, rgba(74, 144, 217, 0.1), rgba(91, 181, 166, 0.08));
	}

	.format-banner span,
	.import-banner span,
	.delta-card p:last-child,
	.callout-card p,
	.artifact-meta span {
		color: #a8bac6;
		line-height: 1.55;
	}

	label,
	.wide-field {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	textarea {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.88);
		color: #eef5f8;
		border-radius: 14px;
		padding: 11px 12px;
		font: inherit;
	}

	textarea {
		resize: vertical;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		line-height: 1.5;
	}

	.ghost-btn,
	.primary-action {
		border: 0;
		cursor: pointer;
		font: inherit;
	}

	.ghost-btn {
		padding: 11px 13px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
		color: #d3dfe7;
	}

	.primary-action {
		padding: 11px 14px;
		border-radius: 999px;
		background: linear-gradient(135deg, rgba(91, 181, 166, 0.92), rgba(74, 144, 217, 0.88));
		color: #08111d;
		font-weight: 700;
	}

	.primary-action:disabled,
	.ghost-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.form-actions,
	.artifact-actions,
	.artifact-meta,
	.delta-topline {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.form-actions,
	.artifact-actions,
	.delta-topline {
		justify-content: space-between;
		align-items: center;
	}

	.action-row {
		grid-auto-flow: column;
		justify-content: end;
	}

	.preview-status {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.preview-status span,
	.delta-topline span {
		display: inline-flex;
		width: fit-content;
		padding: 7px 10px;
		border-radius: 999px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
	}

	.ok {
		background: rgba(91, 181, 166, 0.14);
		color: #7be0d0;
	}

	.bad {
		background: rgba(232, 93, 74, 0.12);
		color: #f2a399;
	}

	.issue-list,
	.delta-list,
	.artifact-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.issue-card {
		background: rgba(232, 93, 74, 0.08);
		border-color: rgba(232, 93, 74, 0.18);
	}

	.issue-card strong,
	.error-list p {
		color: #f2a399;
		line-height: 1.55;
	}

	.delta-card code {
		display: inline-flex;
		margin-top: 10px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #95aab7;
		word-break: break-all;
	}

	.import-banner,
	.stale-banner {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.import-banner {
		background: linear-gradient(145deg, rgba(91, 181, 166, 0.12), rgba(74, 144, 217, 0.08));
	}

	.stale-banner {
		background: rgba(232, 171, 74, 0.08);
		border-color: rgba(232, 171, 74, 0.18);
		color: #f1c781;
	}

	.artifact-topline {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.artifact-topline h3 {
		margin: 8px 0 0;
		font-size: 22px;
	}

	.status-badge {
		padding: 8px 10px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--status-accent) 16%, transparent);
		color: var(--status-accent);
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
	}

	.error-list {
		padding: 12px 14px;
		border-radius: 16px;
		background: rgba(232, 93, 74, 0.08);
		border: 1px solid rgba(232, 93, 74, 0.18);
	}

	.error-list p,
	.payload-view {
		margin: 0;
	}

	.payload-view {
		padding: 14px;
		border-radius: 18px;
		background: rgba(8, 15, 24, 0.88);
		border: 1px solid rgba(255, 255, 255, 0.06);
		color: #d6e4ec;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		overflow-x: auto;
	}

	.callout-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.callout-card.action {
		background: linear-gradient(145deg, rgba(91, 181, 166, 0.1), rgba(74, 144, 217, 0.08));
	}

	.callout-card a {
		display: inline-flex;
		margin-top: 10px;
		padding: 11px 14px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.06);
		color: #eef5f8;
		text-decoration: none;
		font-weight: 700;
	}

	@media (max-width: 980px) {
		.hero,
		.studio-grid,
		.callout-grid,
		.summary-row {
			grid-template-columns: 1fr;
		}

		.action-row {
			grid-auto-flow: row;
			justify-content: stretch;
		}
	}
</style>

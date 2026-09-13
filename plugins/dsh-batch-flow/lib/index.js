/**
 * dsh-batch-flow — declarative batch calls, reference-following reads, metering.
 *
 * Three pieces, independently useful:
 * 1. `batch` tool: run a declared list of tool calls (sequence or parallel) with
 *    per-step expectations and an early-exit contract. One model turn instead of N.
 * 2. `read_plus` tool: read a file plus its local references in one result.
 * 3. Metering: per-agent counts (batches, calls, early exits, nudges) plus a
 *    post-execute observer that attributes repeated-call patterns. Advisory only.
 *
 * Design constraints (from the DSH API as verified in 0.1.5-rc.1):
 * - Tool calls go through `ctx.tools.execute()` when available; every nested
 *   call is validated, errors become step failures (never thrown past the batch
 *   boundary except on contract misuse). No rollback — documented, like PTC.
 * - Read resolution is local-filesystem only, capped, cycle-guarded.
 * - Nothing here blocks, vetoes, or rewrites model calls. All observers delegate.
 *
 * @module dsh-batch-flow
 */
import { randomUUID } from 'node:crypto';
import { promises as fsp } from 'node:fs';
import * as path from 'node:path';

export const name = 'dsh-batch-flow';

// Static service dependencies: `ctx.tools` and `ctx.systemPrompt` access below
// require this declaration (the loader rejects undeclared service property
// access). Mirrors dsh-rewind-plugin's `inject = ["commands", "tools"]`.
export const inject = ['tools', 'systemPrompt'];

// Batch-first workflow discipline, shown to the model. This is the steering
// half of the plugin: tools alone don't get adopted (models reach for what
// their priors know), so the discipline is stated where every turn assembles.
const BATCH_FIRST_TEXT = [
	'Batch-first workflow (saves turns and context, same tools underneath):',
	'- Independent calls (reads, searches, checks) go in ONE `batch` call with mode parallel — never one turn per call.',
	'- Use `read_plus` instead of `read` when a file may reference other files; it returns the file plus its local imports in one result.',
	'- Dependent chains go in ONE `batch` call with mode sequence, per-step `expect`, and `on_unexpected: "stop"` — a failed expectation stops the batch instead of cascading.',
	'- Applies to every tool, not just reads: bash commands, searches, edits queued behind checks — anything plannable together.',
	'- If the same tool fails the same way twice, you will get a nudge; a third time escalates. Diagnose (read the output, state the cause) instead of re-running.',
].join('\n');

const PLUGIN = 'dsh-batch-flow';
const MAX_FILES = 10;
const MAX_BYTES_PER_FILE = 20000;
const MAX_BATCH_STEPS = 20;

// ---------------------------------------------------------------------------
// shared tiny helpers (duplicated from the nudge plugin on purpose: the two
// packages must mount and unmount independently for ablation)
// ---------------------------------------------------------------------------

function textOf(result) {
	if (result === null || result === undefined) return '';
	if (typeof result === 'string') return result;
	const content = result.content ?? result.value ?? '';
	if (typeof content === 'string') return content;
	if (Array.isArray(content)) {
		return content.map((part) => {
			if (typeof part === 'string') return part;
			if (part && typeof part === 'object') return part.text ?? part.content ?? '';
			return '';
		}).join('\n');
	}
	if (typeof content === 'object') {
		try { return JSON.stringify(content).slice(0, 4000); } catch { return ''; }
	}
	return String(content ?? '');
}

function exitOf(result, text) {
	const m = /Exit Code:\s*(\d+)/.exec(text)
		?? /exit code\s*(\d+)/i.exec(text)
		?? /exit status\s*(\d+)/i.exec(text);
	if (m) return Number(m[1]);
	if (result && typeof result === 'object' && result.error != null) {
		const c = result.error.code ?? result.error.status ?? result.error.errno;
		if (typeof c === 'number') return c;
	}
	return null;
}

function failedOf(result, text, exit) {
	if (result && result.isError === true) return true;
	if (typeof exit === 'number' && exit !== 0) return true;
	return false;
}

// ---------------------------------------------------------------------------
// metering (in-memory per agent; counts + char volumes as context proxy)
// ---------------------------------------------------------------------------

function newMeter() {
	return {
		batches: 0, batchCalls: 0, earlyExits: 0, readPlus: 0, readPlusFiles: 0,
		inChars: 0, outChars: 0, nudges: 0, id: randomUUID(),
	};
}

function meterOf(meters, agent) {
	let m = meters.get(agent);
	if (!m) { m = newMeter(); meters.set(agent, m); }
	return m;
}

function bump(meter, field, by = 1) {
	if (!meter) return;
	meter[field] = (meter[field] ?? 0) + by;
}

// ---------------------------------------------------------------------------
// read_plus: file + its local references, one result
// ---------------------------------------------------------------------------

const IMPORT_PATTERNS = [
	// JS/TS: import x from './y', import './y', require('./y'), export ... from './y'
	{ ext: ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'], re: /(?:import\s+(?:[^'"]*?\sfrom\s+)?|require\(|export\s+[^;]*?\sfrom\s+)(['"])(\.[^'"]+)\1/g, group: 2 },
	// Python: from .y import z, from . import z, import .y (rare)
	{ ext: ['.py'], re: /^\s*from\s+(\.[A-Za-z0-9_.]+)\s+import\s+/gm, group: 1 },
	// Go: relative-ish imports are rare; same-package files share dirs (handled by sibling scan below)
];

const BINARY_EXT = new Set(['.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.gz', '.pyc', '.o', '.a', '.bin', '.wasm', '.woff', '.woff2', '.ttf', '.mp4', '.mov']);

function candidateRefs(filePath, text) {
	const ext = path.extname(filePath).toLowerCase();
	const out = [];
	for (const pat of IMPORT_PATTERNS) {
		if (!pat.ext.includes(ext)) continue;
		pat.re.lastIndex = 0;
		let m;
		while ((m = pat.re.exec(text)) !== null) {
			let ref = m[pat.group];
			if (ref.startsWith('.')) {
				if (ext === '.py' && !ref.includes('/')) {
					// from .foo import -> foo.py next to the file
					ref = `./${ref.slice(1).split('.')[0]}.py`;
				}
				out.push(ref);
			}
		}
	}
	return [...new Set(out)];
}

function resolveRef(baseFile, ref) {
	let p = path.resolve(path.dirname(baseFile), ref);
	return p;
}

async function readFileSafe(absPath) {
	try {
		const st = await fsp.stat(absPath);
		if (!st.isFile()) return { skipped: 'not-a-file' };
		if (st.size > MAX_BYTES_PER_FILE * 4) return { skipped: `too-large(${st.size})` };
		if (BINARY_EXT.has(path.extname(absPath).toLowerCase())) return { skipped: 'binary' };
		let text = await fsp.readFile(absPath, 'utf8');
		let truncated = false;
		if (text.length > MAX_BYTES_PER_FILE) { text = text.slice(0, MAX_BYTES_PER_FILE); truncated = true; }
		return { text, truncated };
	} catch (error) {
		return { skipped: `unreadable(${error?.code ?? 'err'})` };
	}
}

export async function readPlus(rootDir, relPath, opts = {}) {
	const maxFiles = opts.maxFiles ?? MAX_FILES;
	const visited = new Set();
	const files = [];
	const queue = [relPath];
	while (queue.length > 0 && files.length < maxFiles) {
		const rel = queue.shift();
		const abs = path.resolve(rootDir, rel);
		const norm = path.normalize(abs);
		if (visited.has(norm)) continue;
		visited.add(norm);
		// stay inside the root: no ../ escapes, no node_modules/.git
		const rootNorm = path.normalize(path.resolve(rootDir)) + path.sep;
		if (!norm.startsWith(rootNorm)) { files.push({ path: rel, skipped: 'outside-root' }); continue; }
		if (norm.includes(`${path.sep}node_modules${path.sep}`) || norm.includes(`${path.sep}.git${path.sep}`)) {
			files.push({ path: rel, skipped: 'excluded-dir' }); continue;
		}
	 const got = await readFileSafe(norm);
		if (got.skipped) { files.push({ path: rel, skipped: got.skipped }); continue; }
		const entry = { path: rel, text: got.text, truncated: !!got.truncated };
		files.push(entry);
		for (const ref of candidateRefs(norm, got.text)) {
			const resolved = resolveRef(norm, ref);
			const relResolved = path.relative(rootNorm.slice(0, -1), resolved);
			if (!visited.has(path.normalize(resolved))) queue.push(relResolved);
		}
	}
	return { root: rootDir, entry: relPath, files, capped: queue.length > 0 };
}

function renderReadPlus(result) {
	const parts = [];
	for (const f of result.files) {
		if (f.skipped) { parts.push(`--- ${f.path} (skipped: ${f.skipped})`); continue; }
		parts.push(`--- ${f.path}${f.truncated ? ' (truncated)' : ''}\n${f.text}`);
	}
	if (result.capped) parts.push(`[...file cap (${MAX_FILES}) reached; further references omitted]`);
	return parts.join('\n\n');
}

// ---------------------------------------------------------------------------
// batch: declarative multi-call with expectations + early exit
// ---------------------------------------------------------------------------

function checkExpect(step, text, exit) {
	const exp = step.expect ?? {};
	if (exp.exitCode !== undefined && exp.exitCode !== null && exit !== exp.exitCode) {
		return `expected exit ${exp.exitCode}, got ${exit === null ? 'unknown' : exit}`;
	}
	if (typeof exp.contains === 'string' && !text.includes(exp.contains)) {
		return `expected output containing ${JSON.stringify(exp.contains.slice(0, 80))}`;
	}
	if (typeof exp.matches === 'string') {
		let re;
		try { re = new RegExp(exp.matches); } catch { return `invalid regex ${JSON.stringify(exp.matches)}`; }
		if (!re.test(text)) return `output did not match ${JSON.stringify(exp.matches.slice(0, 80))}`;
	}
	return null;
}

function validateBatchSpec(spec) {
	if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return 'spec must be an object';
	const steps = spec.steps;
	if (!Array.isArray(steps) || steps.length === 0) return 'spec.steps must be a non-empty array';
	if (steps.length > MAX_BATCH_STEPS) return `at most ${MAX_BATCH_STEPS} steps per batch`;
	for (const [i, s] of steps.entries()) {
		if (!s || typeof s !== 'object') return `step ${i}: must be an object`;
		if (typeof s.tool !== 'string' || s.tool === '') return `step ${i}: tool must be a non-empty string`;
		if (s.args !== undefined && (typeof s.args !== 'object' || s.args === null || Array.isArray(s.args))) {
			return `step ${i}: args must be an object when present`;
		}
	}
	const mode = spec.mode ?? 'sequence';
	if (mode !== 'sequence' && mode !== 'parallel') return `mode must be 'sequence' or 'parallel'`;
	const onUnexpected = spec.on_unexpected ?? 'stop';
	if (onUnexpected !== 'stop' && onUnexpected !== 'continue') return `on_unexpected must be 'stop' or 'continue'`;
	return null;
}

async function runStep(tools, agent, step) {
	const started = Date.now();
	try {
		const exec = await tools.execute({
			name: step.tool,
			arguments: step.args ?? {},
			...(agent ? { agent } : {}),
		});
		const text = textOf(exec);
		const exit = exitOf(exec, text);
		const failed = failedOf(exec, text, exit);
		const mismatch = step.expect ? checkExpect(step, text, exit) : null;
		return {
			id: step.id ?? null, tool: step.tool, ok: !failed && mismatch === null,
			failed, mismatch, exit, ms: Date.now() - started,
			output: text.slice(0, 4000),
		};
	} catch (error) {
		return {
			id: step.id ?? null, tool: step.tool, ok: false, failed: true,
			mismatch: null, exit: null, ms: Date.now() - started,
			output: `batch dispatch failed: ${error?.message ?? error}`.slice(0, 500),
			dispatchError: true,
		};
	}
}

export async function runBatch(tools, agent, spec, meter) {
	const invalid = validateBatchSpec(spec);
	if (invalid) throw new Error(`invalid batch spec: ${invalid}`);
	const mode = spec.mode ?? 'sequence';
	const onUnexpected = spec.on_unexpected ?? 'stop';
	const results = [];
	let stoppedEarly = null;
	if (mode === 'parallel') {
		// No rollback by design (same contract as PTC): steps are independent by declaration.
		const settled = await Promise.all(spec.steps.map((s) => runStep(tools, agent, s)));
		for (const r of settled) {
			results.push(r);
			bump(meter, 'batchCalls'); bump(meter, 'outChars', r.output.length);
		}
		const bad = settled.find((r) => !r.ok);
		if (bad && onUnexpected === 'stop') stoppedEarly = `parallel batch: step '${bad.tool}' unsatisfactory (${bad.mismatch ?? `failed${bad.exit === null ? '' : ` exit ${bad.exit}`}`})`;
	} else {
		for (const s of spec.steps) {
			const r = await runStep(tools, agent, s);
			results.push(r);
			bump(meter, 'batchCalls'); bump(meter, 'outChars', r.output.length);
			if (!r.ok && onUnexpected === 'stop') {
				stoppedEarly = `stopped after step '${r.tool}': ${r.mismatch ?? `failed${r.exit === null ? '' : ` exit ${r.exit}`}`}`;
				break;
			}
		}
	}
	if (stoppedEarly) bump(meter, 'earlyExits');
	return { mode, completed: results.length, stoppedEarly, results };
}

function renderBatch(outcome) {
	const lines = [`batch (${outcome.mode}): ${outcome.results.filter((r) => r.ok).length}/${outcome.results.length} ok`];
	for (const r of outcome.results) {
		lines.push(`- [${r.ok ? 'ok' : 'STOP'}] ${r.tool}${r.exit === null || r.exit === undefined ? '' : ` (exit ${r.exit})`}${r.mismatch ? ` — ${r.mismatch}` : ''}`);
		if (!r.ok) lines.push(`  ${r.output.split('\n').find((l) => l.trim() !== '')?.slice(0, 300) ?? ''}`);
	}
	if (outcome.stoppedEarly) lines.push(`Early exit: ${outcome.stoppedEarly}`);
	return lines.join('\n');
}

// ---------------------------------------------------------------------------
// plugin wiring
// ---------------------------------------------------------------------------

export function apply(ctx) {
	const meters = new WeakMap();
	const streaks = new WeakMap(); // agent -> { key, count } for the failure-loop advisor

	// Steering half: without this section the tools exist but models reach for
	// what their priors know (bash/read/grep). Fail-open: a section failure
	// must never break mounting.
	try {
		if (ctx.systemPrompt && typeof ctx.systemPrompt.section === 'function') {
			ctx.systemPrompt.section({
				name: 'batch-flow:batch-first',
				order: 160,
				text: BATCH_FIRST_TEXT,
			});
		} else if (ctx.logger?.warn) {
			ctx.logger.warn('[dsh-batch-flow] systemPrompt.section unavailable; steering section skipped');
		}
	} catch (error) {
		try { ctx.logger?.warn?.(`[dsh-batch-flow] steering section skipped: ${error?.message ?? error}`); } catch { /* noop */ }
	}

	function toolOrNull(name) {
		try {
			if (ctx.tools && typeof ctx.tools.execute === 'function') return true;
			return false;
		} catch { return false; }
	}

	if (ctx.tools && typeof ctx.tools.register === 'function') {
		try {
			ctx.tools.register({
				name: 'batch',
				description: 'Run a declared list of tool calls (sequence or parallel) with per-step expectations and an early-exit contract. One model turn instead of many. No rollback: parallel steps must be independent.',
				parameters: {
					type: 'object',
					properties: {
						spec: {
							type: 'object',
							description: 'Batch spec: {steps:[{tool,args?,expect?:{contains?,matches?,exitCode?},id?}], mode?:sequence|parallel, on_unexpected?:stop|continue}',
						},
						description: { type: 'string', description: 'Short label for this batch (shown in UI)' },
					},
					required: ['spec'],
				},
				output: {
					schema: {
						type: 'object',
						additionalProperties: true,
					},
					render: (_args, value) => [{
						type: 'text',
						text: value && typeof value === 'object' && Array.isArray(value.results)
							? renderBatch(value)
							: 'batch completed (unrecognized result shape)',
					}],
				},
				execute: async (args, exec) => {
					const meter = exec?.agent ? meterOf(meters, exec.agent) : null;
					bump(meter, 'batches');
					if (!toolOrNull()) throw new Error('batch: tool execution backend unavailable in this deployment');
					return runBatch(ctx.tools, exec?.agent ?? null, args?.spec, meter);
				},
			});
		} catch (error) {
			throw new Error(`[dsh-batch-flow] batch registration failed: ${error?.message ?? error}`);
		}

		try {
			ctx.tools.register({
				name: 'read_plus',
				description: 'Read a file plus the local files it references (imports/requires), in one result. Bounded (10 files, 20k chars each), cycle-guarded, stays inside the workspace root.',
				parameters: {
					type: 'object',
					properties: {
						path: { type: 'string', description: 'Workspace-relative file path to read' },
						root: { type: 'string', description: 'Workspace root directory (defaults to the agent working directory)' },
						maxFiles: { type: 'number', description: 'Max files to return (default 10)' },
					},
					required: ['path'],
				},
				output: {
					schema: {
						type: 'object',
						additionalProperties: true,
					},
					render: (_args, value) => [{
						type: 'text',
						text: value && typeof value === 'object' && Array.isArray(value.files)
							? renderReadPlus(value)
							: 'read_plus completed (unrecognized result shape)',
					}],
				},
				execute: async (args, exec) => {
					const meter = exec?.agent ? meterOf(meters, exec.agent) : null;
					const root = args?.root ?? exec?.cwd ?? process.cwd();
					const outcome = await readPlus(root, args.path, { maxFiles: args.maxFiles });
					bump(meter, 'readPlus'); bump(meter, 'readPlusFiles', outcome.files.length);
					return outcome;
				},
			});
		} catch (error) {
			throw new Error(`[dsh-batch-flow] read_plus registration failed: ${error?.message ?? error}`);
		}
	}

	// Failure-loop advisor: 3rd consecutive identical error-shape forces a
	// diagnose-before-retry nudge (the nudge plugin fires at 2; this one
	// escalates when the nudge didn't stick). Advisory only.
	ctx.on?.('tools/post-execute', async (exec, result, next) => {
		let reminder;
		try {
			if (exec?.agent) {
				const text = textOf(result);
				const exit = exitOf(result, text);
				const failed = failedOf(result, text, exit);
				const key = exec.agent;
				let st = streaks.get(key);
				if (!st) { st = { sig: null, count: 0 }; streaks.set(key, st); }
				if (!failed) { st.sig = null; st.count = 0; }
				else {
					const sig = `${exec.name ?? '?'}:${exit ?? text.split('\n').find((l) => l.trim() !== '')?.trim().slice(0, 80) ?? 'err'}`;
					st.count = st.sig === sig ? st.count + 1 : 1;
					st.sig = sig;
					if (st.count === 3) {
						reminder = deepFreezeCompat({
							id: randomUUID(), role: 'user',
							content: [{ type: 'text', text:
								`Third identical failure in a row (${exec.name}). The last two nudges did not change the approach. ` +
								`Stop and diagnose before any further run: state (1) what the error means, (2) what you have ruled out, ` +
								`(3) the single next check that discriminates. Do not re-run the same shape again.` }],
							source: { kind: 'plugin', plugin: PLUGIN, form: 'notice', summary: `${exec.name} 3rd identical failure` },
						});
						const meter = meterOf(meters, exec.agent);
						bump(meter, 'nudges');
					}
				}
			}
		} catch { /* never break the loop */ }
		const downstream = await next();
		if (!reminder) return downstream;
		if (downstream?.kind === 'block') {
			return { kind: 'block', feedback: downstream.feedback, additionalContexts: [reminder, ...(downstream.additionalContexts ?? [])] };
		}
		return { ...(downstream ?? {}), additionalContexts: [reminder, ...(downstream?.additionalContexts ?? [])] };
	});

	ctx.on?.('agent/pre-step', ({ agent, messages }, next) => {
		try {
			if (Array.isArray(messages) && messages.some((m) => m?.source?.kind === 'user')) {
				streaks.delete(agent); meters.delete(agent);
			}
		} catch { /* never break the loop */ }
		return next();
	});
}

function deepFreezeCompat(value) {
	if (value !== null && (typeof value === 'object' || typeof value === 'function') && !Object.isFrozen(value)) {
		for (const k of Object.getOwnPropertyNames(value)) deepFreezeCompat(value[k]);
		Object.freeze(value);
	}
	return value;
}

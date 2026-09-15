/**
 * dsh-error-shape-nudge — second-consecutive-same-error advisory.
 *
 * Watches each agent's tool-result stream in `tools/post-execute`. When the same
 * tool fails the same way twice in a row (same exit/error code), it attaches ONE
 * advisory nudge telling the model to diagnose before re-running (and to prefer a
 * blocking/background wait over polling when it is waiting). It never blocks,
 * vetoes, or rewrites anything; the decision stays entirely with the model.
 *
 * Anti-nag: fires once per streak (at count 2). Further identical failures stay
 * silent until the streak breaks (success, different error, or user message).
 * Every code path delegates via `next()`; nothing here may throw into the loop.
 *
 * @module dsh-error-shape-nudge
 */
import { randomUUID } from 'node:crypto';

export const name = 'dsh-error-shape-nudge';

const PLUGIN_SOURCE = {
	kind: 'plugin',
	plugin: 'dsh-error-shape-nudge',
};

/** Streak threshold: nudge on the Nth consecutive identical error. Fixed at 2. */
const STREAK_THRESHOLD = 2;

/** Max chars of error detail quoted in the nudge. Bounds the reminder, never detection. */
const DETAIL_CHARS = 200;

function deepFreeze(value) {
	if (value !== null && (typeof value === 'object' || typeof value === 'function')
		&& !Object.isFrozen(value)) {
		for (const key of Object.getOwnPropertyNames(value)) deepFreeze(value[key]);
		Object.freeze(value);
	}
	return value;
}

function makeNudge(text, summary) {
	return deepFreeze({
		id: randomUUID(),
		role: 'user',
		content: [{ type: 'text', text }],
		source: { ...PLUGIN_SOURCE, form: 'notice', summary },
	});
}

function textOf(result) {
	if (result === null || result === undefined) return '';
	if (typeof result === 'string') return result;
	const content = result.content ?? result.value ?? '';
	if (typeof content === 'string') return content;
	if (Array.isArray(content)) {
		return content
			.map((part) => {
				if (typeof part === 'string') return part;
				if (part && typeof part === 'object') return part.text ?? part.content ?? '';
				return '';
			})
			.join('\n');
	}
	if (typeof content === 'object') return JSON.stringify(content).slice(0, 2000);
	return String(content ?? '');
}

/**
 * Extract a stable error signature from a tool result, or null when the call
 * did not fail. Order: explicit error code → rendered exit code → first line.
 */
function errorSignature(toolName, result) {
	if (!result) return null;
	const err = result.error;
	const code = err?.code ?? err?.name;
	const text = textOf(result);
	const exit = /Exit Code:\s*(\d+)/.exec(text)?.[1]
		?? /exit code\s*(\d+)/i.exec(text)?.[1]
		?? /exit status\s*(\d+)/i.exec(text)?.[1];
	const failed = result.isError === true
		|| (typeof exit === 'string' && exit !== '0')
		|| (code !== undefined && code !== null && code !== '' && code !== 0 && code !== '0');
	if (!failed) return null;
	const detail = (code !== undefined && code !== null && `${code}` !== ''
		? `${code}`
		: (text.split('\n').find((l) => l.trim() !== '') ?? 'unknown error').trim())
		.slice(0, DETAIL_CHARS);
	const key = exit !== undefined ? `exit:${exit}` : `error:${detail.slice(0, 80)}`;
	return { key: `${toolName}:${key}`, code: exit ?? detail };
}

function nudgeText(exec, sig, count) {
	return `Same error twice in a row (${exec.name} → ${sig.code}). ` +
		`Before running again: read the output above and diagnose the cause — don't just re-run. ` +
		`If you are waiting on a process, use a blocking or background wait instead of polling; ` +
		`if the command itself is wrong, change it. (Nudge ${count} of this streak; further repeats stay silent.)`;
}

/**
 * Crossroads stall-gate (v0.4.0) — fixed-checkpoint periodic review + batch arm.
 *
 * Spec: work/crossroads-r1/SPEC.md. Rationale: trace analysis showed no firing
 * rule built from repetition/monotony/re-read signatures can meet a serious
 * false-alarm bar (OR-combination lit up on 66% of *solved* runs), so the review
 * fires UNCONDITIONALLY at fixed execution checkpoints, never on detection.
 * Signatures supply review content + covariates, not a go/no-go.
 *
 * Arm selection (same code, all trial arms; first hit wins):
 *   1. session tag: opaque `[cx-0]`..`[cx-3]` (= off/ping/review/batch) in any
 *      user message; first tag seen locks the session. GUI-native, per-session,
 *      no restart. Opaque by design (blinding hygiene — see pre-reg mapping).
 *   2. env fallback: CROSSROADS_ARM=off|ping|review|batch (default off).
 *
 * `batch` (v0.4.0): the cost-side member of the family. Three consecutive
 * same-tool (or all-read) non-error executions, one per turn, earn one
 * one-line advisory suggesting a parallel block — with its own opt-out, once
 * per streak, max 3 per session (nag-wallpaper guard). Advisory-only like
 * everything else here: evaluated causally (turns/tokens per episode), never
 * diagnostically. Arms are exclusive: a batch session gets no review/ping.
 *
 * Branch routing is transcript-state only (no outcome, no gold): fewer than 2
 * edits with recorded targets so far -> LOST screen (establish location);
 * otherwise -> WRONG-FIX screen (disprove the diagnosis). Both end with the
 * universal new-evidence tail. Reviews are advisories in the same channel as
 * the streak nudge and coexist with it. Nothing here may throw into the loop.
 *
 * Approximation note: checkpoints count post-execute events, not model turns —
 * parallel batch sub-calls each count. Checkpoints are therefore ">=N tool
 * results seen", reached slightly early under heavy batching. Uniform across
 * arms by construction (same counting rule everywhere).
 */

/** Trial arm. Env fallback; read live (per event) so tests need no reload. */
const GATE_ARMS = new Set(['off', 'ping', 'review', 'batch']);
function gateArmEnv() {
	try {
		const raw = typeof process !== 'undefined' ? process.env?.CROSSROADS_ARM : '';
		const arm = String(raw ?? '').toLowerCase().trim();
		return GATE_ARMS.has(arm) ? arm : 'off';
	} catch { return 'off'; }
}

/** Opaque session tags -> arm. Mapping lives in tasks/PREREG-crossroads.md. */
const TAG_ARMS = { '0': 'off', '1': 'ping', '2': 'review', '3': 'batch' };
const TAG_RE = /\[cx-([0-9])\]/;

/** Extract plain text from a chat message, defensively (mirrors textOf). */
function msgText(m) {
	try {
		if (m === null || m === undefined) return '';
		if (typeof m === 'string') return m;
		const content = m.content ?? m.text ?? '';
		if (typeof content === 'string') return content;
		if (Array.isArray(content)) {
			return content.map((part) => {
				if (typeof part === 'string') return part;
				if (part && typeof part === 'object') return part.text ?? part.content ?? '';
				return '';
			}).join('\n');
		}
		return '';
	} catch { return ''; }
}

/** First session tag in user messages, or null. Unknown tags never match. */
function scanTag(messages) {
	try {
		if (!Array.isArray(messages)) return null;
		for (const m of messages) {
			if (m?.source?.kind !== 'user' && m?.role !== 'user') continue;
			const hit = TAG_RE.exec(msgText(m));
			if (hit && TAG_ARMS[hit[1]] !== undefined) return TAG_ARMS[hit[1]];
		}
		return null;
	} catch { return null; }
}

/** Fixed checkpoints: attach the review to the result of these executions. */
const GATE_CHECKPOINTS = [10, 20];
/** Branch floor: >= this many edits with targets -> WRONG-FIX screen. */
const GATE_BRANCH_EDIT_FLOOR = 2;
/** Evidence window quoted in the universal tail. */
const GATE_EVIDENCE_WINDOW = 10;
/** Tool names treated as edits (heuristic; scaffold differences expected). */
const EDIT_TOOL_RE = /(write|edit|apply_patch|patch|str_replace|create_file|\bsave\b|modify)/i;
/** Tool names treated as reads (shared by read-counting and the batch arm). */
const READ_TOOL_RE = /read|view|show|open|\bcat\b/i;
/** Batch arm: fire after this many consecutive batchable executions. */
const BATCH_STREAK = 3;
/** Batch arm: session cap — further streaks stay silent past this many nudges. */
const BATCH_SESSION_CAP = 3;

/** Extract plausible file targets from a tool execution's params, defensively. */
function editTargets(exec) {
	try {
		const src = exec?.params ?? exec?.args ?? exec?.input ?? null;
		if (!src || typeof src !== 'object') return [];
		const found = [];
		const take = (v) => {
			if (typeof v === 'string' && v.length > 0 && v.length < 300 && !/\n/.test(v)) {
				const t = v.trim();
				if (t && (t.includes('/') || /\.[a-z0-9]{1,5}$/i.test(t))) found.push(t);
			}
		};
		for (const k of ['file', 'path', 'filePath', 'file_path', 'target', 'filename', 'filepath']) take(src[k]);
		if (Array.isArray(src.targets)) src.targets.forEach(take);
		if (found.length === 0) {
			for (const v of Object.values(src)) {
				// Skip shell-ish strings (chaining/metachars) and long blobs:
				// paths never contain & | ; and rarely exceed 120 chars.
				if (typeof v === 'string' && v.length <= 120 && !/[&|;]/.test(v)) take(v);
				if (found.length >= 5) break;
			}
		}
		return [...new Set(found)].slice(0, 5);
	} catch { return []; }
}

function reviewText(branch, n) {
	const tail = ` Then: list evidence first seen in the last ${GATE_EVIDENCE_WINDOW} turns — if none, say so.`;
	if (branch === 'B') {
		return `Checkpoint review (turn ${n}): state your theory of the bug in one sentence. ` +
			`Name one observation that would disprove it, and whether you have seen it. ` +
			`If you cannot name one, stop editing and re-derive the diagnosis before touching code again.` +
			tail + ` (Crossroads review ${n}; advisory only.)`;
	}
	return `Checkpoint review (turn ${n}): quote the observation that establishes the defect is in ` +
		`the files you have touched. Name one location you have not examined that could still contain it. ` +
		`If neither answer has evidence behind it, widen the search before editing again.` +
		tail + ` (Crossroads review ${n}; advisory only.)`;
}

/** Content-free control: same trigger, same channel, matched length, no content. */
function pingText(n) {
	return `Checkpoint (turn ${n}): keep going — continue with the task in the same way. ` +
		`No change of approach is requested; this is a routine pulse, not feedback on your work. ` +
		`Proceed to the next step as you had planned, at your own judgement, without alteration. ` +
		`Continue steadily through the remaining work in the order you see fit. ` +
		`There is nothing further here. (Crossroads pulse ${n}.)`;
}

/** One-line batch suggestion: same order of magnitude as ping/review. */
function batchText(toolLabel, streakN, nudgeN) {
	return `Batch note: ${streakN} ${toolLabel} calls in a row, one per turn. ` +
		`If they were independent, they can go in a single parallel block for fewer turns — ` +
		`same results, less waiting. If a call depended on the previous result, ignore this. ` +
		`(Batch nudge ${nudgeN} of ${BATCH_SESSION_CAP} max this session; advisory only.)`;
}

/** Fresh per-agent gate state. tagArm locks at the first session tag. */
function freshGate(seq, tagArm, batchFired) {
	return {
		seq, tagArm: tagArm ?? null, execs: 0, editsWT: 0, verbs: new Set(),
		reads: 0, errSeen: false, fired: new Set(),
		batchKey: null, batchCount: 0, batchReminded: false,
		batchFired: batchFired ?? 0,
	};
}

export function apply(ctx) {
	// agent -> { key, count, reminded }
	const streaks = new WeakMap();
	// agent -> gate state (see freshGate): counters + tagArm + batch streak/cap
	const gate = new WeakMap();
	let agentSeq = 0;

	function streakKey(agent) {
		let s = streaks.get(agent);
		if (!s) { s = { key: null, count: 0, reminded: false }; streaks.set(agent, s); }
		return s;
	}

	ctx.on('tools/post-execute', async (exec, result, next) => {
		let reminder;
		let gateReminder;
		try {
			if (exec?.agent) {
				const sig = errorSignature(exec.name ?? 'unknown-tool', result);
				const st = streakKey(exec.agent);
				if (sig === null) {
					st.key = null; st.count = 0; st.reminded = false;
				} else if (st.key === sig.key) {
					st.count += 1;
				} else {
					st.key = sig.key; st.count = 1; st.reminded = false;
				}
				if (sig !== null && st.count === STREAK_THRESHOLD && !st.reminded) {
					st.reminded = true;
					reminder = makeNudge(
						nudgeText(exec, sig, st.count),
						`${exec.name} → ${sig.code} ×${st.count}`,
					);
				}
			}
		} catch (error) {
			try { ctx.logger?.warn?.(`[dsh-error-shape-nudge] observe failed: ${error?.message ?? error}`); } catch { /* never break the loop */ }
		}
		try {
			gateReminder = gateObserve(ctx, gate, exec, result, () => ++agentSeq);
		} catch (error) {
			try { ctx.logger?.warn?.(`[dsh-error-shape-nudge] gate failed: ${error?.message ?? error}`); } catch { /* never break the loop */ }
			gateReminder = undefined;
		}
		const downstream = await next();
		const extras = [...(reminder ? [reminder] : []), ...(gateReminder ? [gateReminder] : [])];
		if (extras.length === 0) return downstream;
		if (downstream?.kind === 'block') {
			return { kind: 'block', feedback: downstream.feedback, additionalContexts: [...extras, ...(downstream.additionalContexts ?? [])] };
		}
		return { ...(downstream ?? {}), additionalContexts: [...extras, ...(downstream?.additionalContexts ?? [])] };
	});

	// A user message starts a new context; repetition across it is not a loop.
	// A session tag ([cx-N]) locks the arm on first sight and survives resets.
	ctx.on('agent/pre-step', ({ agent, messages }, next) => {
		try {
			const tag = scanTag(messages);
			if (tag !== null && agent !== undefined && agent !== null) {
				let g = gate.get(agent);
				if (!g) { g = freshGate(++agentSeq, null); gate.set(agent, g); }
				if (g.tagArm === null) g.tagArm = tag;
			}
			if (Array.isArray(messages) && messages.some((m) => m?.source?.kind === 'user' || m?.role === 'user')) {
				streaks.delete(agent);
				// Counters restart on new user context, but a locked arm and the
				// batch session cap persist.
				const prev = (agent !== undefined && agent !== null) ? gate.get(agent) : undefined;
				gate.delete(agent);
				if (prev?.tagArm != null && agent !== undefined && agent !== null) {
					gate.set(agent, freshGate(prev.seq, prev.tagArm, prev.batchFired ?? 0));
				}
			}
		} catch { /* never break the loop */ }
		return next();
	});
}

/**
 * Crossroads gate observation: count executions per agent; at fixed checkpoints
 * attach the ping or the mode-routed review (arms ping/review); in the batch arm
 * attach batch suggestions on batchable streaks instead. Returns a notice or
 * undefined. All throwing paths contained by the caller — this function itself
 * must also never throw.
 */
function gateObserve(ctx, gate, exec, result, nextSeq) {
	if (!exec?.agent) return undefined;
	let g = gate.get(exec.agent);
	if (!g) {
		g = freshGate(nextSeq(), null, 0);
		gate.set(exec.agent, g);
	}
	// Session tag wins over the process env; env is the fallback for tagless runs.
	const arm = g.tagArm ?? gateArmEnv();
	const src = g.tagArm !== null && g.tagArm !== undefined ? 'tag' : 'env';
	if (arm === 'off') return undefined;
	g.execs += 1;
	const toolName = exec.name ?? 'unknown-tool';
	g.verbs.add(toolName);
	if (READ_TOOL_RE.test(toolName)) g.reads += 1;
	const failed = errorSignature(toolName, result) !== null;
	if (failed) g.errSeen = true;
	if (EDIT_TOOL_RE.test(toolName) && editTargets(exec).length > 0) g.editsWT += 1;
	if (arm === 'batch') return gateObserveBatch(ctx, g, toolName, failed, src);
	if (!GATE_CHECKPOINTS.includes(g.execs) || g.fired.has(g.execs)) return undefined;
	g.fired.add(g.execs);
	const branch = g.editsWT >= GATE_BRANCH_EDIT_FLOOR ? 'B' : 'A';
	const text = arm === 'ping' ? pingText(g.execs) : reviewText(branch, g.execs);
	const summary = arm === 'ping' ? `pulse @${g.execs}` : `review-${branch} @${g.execs}`;
	try {
		ctx.logger?.info?.(`[crossroads] ${JSON.stringify({
			v: 1, arm, src, ckpt: g.execs, branch: arm === 'ping' ? '-' : branch,
			execs: g.execs, editsWT: g.editsWT, verbs: g.verbs.size,
			reads: g.reads, errSeen: g.errSeen, agentSeq: g.seq,
		})}`);
	} catch { /* logging must never break the loop */ }
	return makeNudge(text, summary);
}

/**
 * Batch arm: track consecutive batchable executions (same tool, or all reads).
 * Errors break the streak (a failed call is diagnosis material, not batching
 * material). Fires once per streak at BATCH_STREAK, max BATCH_SESSION_CAP
 * per session. Returns a notice or undefined; never throws.
 */
function gateObserveBatch(ctx, g, toolName, failed, src) {
	if (failed) {
		g.batchKey = null; g.batchCount = 0; g.batchReminded = false;
		return undefined;
	}
	const key = READ_TOOL_RE.test(toolName) ? 'READ' : `tool:${toolName}`;
	if (g.batchKey === key) {
		g.batchCount += 1;
	} else {
		g.batchKey = key; g.batchCount = 1; g.batchReminded = false;
	}
	if (g.batchCount !== BATCH_STREAK || g.batchReminded) return undefined;
	if (g.batchFired >= BATCH_SESSION_CAP) return undefined;
	g.batchReminded = true;
	g.batchFired += 1;
	const label = key === 'READ' ? 'read' : `${toolName}`;
	try {
		ctx.logger?.info?.(`[crossroads] ${JSON.stringify({
			v: 1, arm: 'batch', src, ckpt: g.execs, branch: '-',
			streakTool: label, streakN: g.batchCount, nudgeN: g.batchFired,
			execs: g.execs, editsWT: g.editsWT, verbs: g.verbs.size,
			reads: g.reads, errSeen: g.errSeen, agentSeq: g.seq,
		})}`);
	} catch { /* logging must never break the loop */ }
	return makeNudge(batchText(label, g.batchCount, g.batchFired), `batch:${label} x${g.batchCount} (#${g.batchFired})`);
}

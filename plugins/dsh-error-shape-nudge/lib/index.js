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

export function apply(ctx) {
	// agent -> { key, count, reminded }
	const streaks = new WeakMap();

	function streakKey(agent) {
		let s = streaks.get(agent);
		if (!s) { s = { key: null, count: 0, reminded: false }; streaks.set(agent, s); }
		return s;
	}

	ctx.on('tools/post-execute', async (exec, result, next) => {
		let reminder;
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
		const downstream = await next();
		if (!reminder) return downstream;
		if (downstream?.kind === 'block') {
			return { kind: 'block', feedback: downstream.feedback, additionalContexts: [reminder, ...(downstream.additionalContexts ?? [])] };
		}
		return { ...(downstream ?? {}), additionalContexts: [reminder, ...(downstream?.additionalContexts ?? [])] };
	});

	// A user message starts a new context; repetition across it is not a loop.
	ctx.on('agent/pre-step', ({ agent, messages }, next) => {
		try {
			if (Array.isArray(messages) && messages.some((m) => m?.source?.kind === 'user')) {
				streaks.delete(agent);
			}
		} catch { /* never break the loop */ }
		return next();
	});
}

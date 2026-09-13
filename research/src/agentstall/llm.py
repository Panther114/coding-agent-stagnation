"""Minimal client for the OpenCode Go gateway (DeepSeek V4.1 Flash).

Why this exists: the study needs to *run* a model, not just read logged runs, to turn the
observational finding ("failed runs localise better than solved runs") into an interventional
one.  That is the only route to a causal claim, and this is the cheapest model available.

Gateway facts, established empirically plus from https://opencode.ai/docs/go/ :

  endpoint   https://opencode.ai/zen/go/v1/chat/completions   (OpenAI-compatible)
  auth       Authorization: Bearer $OCV41_API_KEY
  session    x-opencode-session: <stable id per conversation>  REQUIRED
             Without it the gateway returns 400 MissingSessionID; it exists so the gateway can
             route and reuse prompt cache.  OpenCode's own docs list DeepSeek Harness as a
             "Known Problematic Client" for exactly this header.
  user-agent must identify the client, not a generic SDK name.
  pricing    $0.15 / $0.60 per 1M in/out off-peak; $0.30 / $1.20 peak.
             Peak = 01:00-04:00 and 06:00-10:00 UTC, Mon-Fri.
  limits     DeepSeek V4.1 Flash: $15/month, $3 per rolling 5 hours, $7.50 per week.

Notes that cost real time to learn:
  * Reasoning tokens are billed and count against ``max_tokens``.  A 16-token budget returns
    EMPTY content because the reasoning consumed all of it.  Always allow >= 512.
  * Every request spends budget, so the ledger below is not optional: it is written on every
    call so a runaway loop is visible immediately rather than at the monthly cap.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "results" / "rebuild" / "llm_ledger.jsonl"

BASE_URL = "https://opencode.ai/zen/go/v1"
MODEL = "deepseek-v4.1-flash"
USER_AGENT = "agentstall-research/1.0"

# Route chain, tried in order.  This machine is behind a VPN whose international path is
# INTERMITTENT (measured: huggingface.co failed 3/3 probes at ~9.4 s; opencode.ai failed 1/3
# at 12 s) while domestic endpoints are solid (99-363 ms).  Same model is served both ways:
# DSH's own session logs record the mapping ``deepseek-flash -> deepseek-v4.1-flash``, and the
# domestic route is ~11x faster to first token.
#
#   domestic   api.deepseek.com  model=deepseek-flash        median TTFT 0.10 s, total 1.04 s
#   intl       opencode.ai       model=deepseek-v4.1-flash   median TTFT 1.12 s, total 2.39 s
#
# Domestic is tried first because it is both faster and more reliable; the international route
# stays as a fallback so an outage on either side degrades rather than stops the work.
ROUTES = [
    {"name": "opencode-go", "base": "https://opencode.ai/zen/go/v1",
     "model": "deepseek-v4.1-flash", "key_env": "OCV41_API_KEY", "session_header": True},
    {"name": "deepseek-domestic", "base": "https://api.deepseek.com/v1",
     "model": "deepseek-flash", "key_env": "DEEPSEEK_API_KEY", "session_header": False},
]

# $ per 1M tokens, off-peak / peak
PRICE = {"off": (0.15, 0.60), "peak": (0.30, 1.20)}
# rolling-window caps for this model, from the Go pricing table
CAPS = {"per_5h": 3.0, "per_week": 7.50, "per_month": 15.0}


def _api_key(env_name: str) -> str:
    """Key from the environment or DSH's credential store.  Never logged."""
    env = os.environ.get(env_name)
    if env:
        return env
    cred = Path(os.path.expanduser("~/.dsh/.credentials.yaml"))
    if cred.exists():
        data = yaml.safe_load(cred.read_text(encoding="utf-8")) or {}
        key = (data.get("refs") or {}).get(env_name)
        if key:
            return key
    raise RuntimeError(f"no {env_name} found; set the env var or check ~/.dsh/.credentials.yaml")


def is_peak(ts: Optional[float] = None) -> bool:
    """Peak = 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday."""
    t = time.gmtime(ts)
    if t.tm_wday >= 5:  # Sat/Sun
        return False
    hour = t.tm_hour
    return (1 <= hour < 4) or (6 <= hour < 10)


def cost_usd(prompt_tokens: int, completion_tokens: int,
             cached_tokens: int = 0, ts: Optional[float] = None) -> float:
    pin, pout = PRICE["peak" if is_peak(ts) else "off"]
    fresh = max(prompt_tokens - cached_tokens, 0)
    return (fresh * pin + cached_tokens * pin * 0.02 + completion_tokens * pout) / 1e6


@dataclass
class Spend:
    usd: float = 0.0
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    errors: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)


class Gateway:
    """Chat client with a required session id, retries, and a spend ledger.

    One ``session`` is one conversation: the gateway caches the prompt against it, so keep
    the same id across the turns of a single agent episode and use a fresh one per episode.
    """

    def __init__(self, session: Optional[str] = None, tag: str = "",
                 temperature: float = 0.0, max_retries: int = 4,
                 timeout: int = 180, ledger: Optional[Path] = LEDGER,
                 routes: Optional[List[Dict[str, Any]]] = None) -> None:
        self.session = session or f"agentstall-{uuid.uuid4()}"
        self.tag = tag
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        self.ledger = ledger
        self.spend = Spend()
        self.routes = routes or ROUTES
        self._keys = {}
        for rt in self.routes:
            try:
                self._keys[rt["name"]] = _api_key(rt["key_env"])
            except Exception as e:
                print(f"  [gateway] route {rt['name']} unusable: {e}")
        if not self._keys:
            raise RuntimeError("no usable gateway route")
        # health tracking so a dead route is deprioritised within this client's lifetime
        self._route_fail = {name: 0 for name in self._keys}

    def _ordered_routes(self) -> List[Dict[str, Any]]:
        avail = [r for r in self.routes if r["name"] in self._keys]
        return sorted(avail, key=lambda r: self._route_fail[r["name"]])

    # -- internals ---------------------------------------------------------------
    def _record(self, rec: Dict[str, Any]) -> None:
        self.spend.usd += rec.get("usd", 0.0)
        self.spend.calls += 1
        self.spend.prompt_tokens += rec.get("prompt_tokens", 0)
        self.spend.completion_tokens += rec.get("completion_tokens", 0)
        self.spend.reasoning_tokens += rec.get("reasoning_tokens", 0)
        if self.ledger is not None:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # -- public ------------------------------------------------------------------
    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 1400,
             temperature: Optional[float] = None, stop: Optional[List[str]] = None,
             seed: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None,
             tool_choice: Optional[str] = None) -> Dict[str, Any]:
        """One completion.  Returns {text, reasoning, tool_calls, usage, usd, raw, elapsed}.

        ``tools`` enables native function calling.  This matters: an ad-hoc text protocol
        ("reply with: read <path>") lost 65% of the model's turns, because the model emits its
        own XML tool-call format (``<tool_calls><invoke name="write">``) regardless.  Parsing the
        model's native channel instead of fighting it is the difference between measuring
        debugging ability and measuring protocol compliance.
        """
        body: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if stop:
            body["stop"] = stop
        if seed is not None:
            body["seed"] = seed
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"

        last: str = ""
        # Walk the route chain; within a route, retry transient failures.  A route that keeps
        # failing is deprioritised for the rest of this client's life rather than abandoned,
        # so a temporary outage does not permanently disable a working path.
        for rt in self._ordered_routes():
            body["model"] = rt["model"]
            headers = {
                "Authorization": f"Bearer {self._keys[rt['name']]}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
            if rt.get("session_header"):
                headers["x-opencode-session"] = self.session
            for attempt in range(self.max_retries):
                t0 = time.time()
                try:
                    r = requests.post(
                        f"{rt['base']}/chat/completions",
                        headers=headers,
                        json=body,
                        timeout=self.timeout,
                    )
                    if r.status_code == 200:
                        j = r.json()
                        ch = (j.get("choices") or [{}])[0]
                        msg = ch.get("message") or {}
                        usage = j.get("usage") or {}
                        detail = usage.get("completion_tokens_details") or {}
                        rec = {
                            "ts": time.strftime("%F %T"), "tag": self.tag,
                            "session": self.session, "route": rt["name"],
                            "model": j.get("model", rt["model"]), "peak": is_peak(t0),
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
                                "cached_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "reasoning_tokens": detail.get("reasoning_tokens", 0),
                            "usd": cost_usd(usage.get("prompt_tokens", 0),
                                            usage.get("completion_tokens", 0),
                                            (usage.get("prompt_tokens_details") or {}).get(
                                                "cached_tokens", 0), t0),
                            "elapsed": round(time.time() - t0, 2),
                            "ok": True,
                        }
                        self._record(rec)
                        tcs = msg.get("tool_calls") or []
                        return {
                            "text": msg.get("content") or "",
                            "reasoning": msg.get("reasoning_content") or "",
                            "tool_calls": tcs,
                            "usage": usage, "usd": rec["usd"], "raw": j,
                            "elapsed": rec["elapsed"], "route": rt["name"],
                        }
                    last = f"[{rt['name']}] HTTP {r.status_code}: {r.text[:300]}"
                    # 4xx other than 429 is a real error; do not burn retries on it
                    if r.status_code not in (408, 409, 429, 500, 502, 503, 504):
                        break
                except Exception as e:  # network hiccup
                    last = f"[{rt['name']}] {type(e).__name__}: {str(e)[:200]}"
                self.spend.errors += 1
                self._route_fail[rt["name"]] += 1
                time.sleep(min(2 ** attempt, 12))

        self._record({"ts": time.strftime("%F %T"), "tag": self.tag, "session": self.session,
                      "ok": False, "error": last, "usd": 0.0, "prompt_tokens": 0,
                      "completion_tokens": 0, "reasoning_tokens": 0})
        raise RuntimeError(
            f"all {len(self._ordered_routes())} gateway route(s) failed "
            f"({self.max_retries} attempts each): {last}")

    def chat_text(self, prompt: str, system: Optional[str] = None, **kw) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        return self.chat(msgs, **kw)["text"]

    def budget_state(self) -> Dict[str, float]:
        return {"spent_usd": round(self.spend.usd, 4), "calls": self.spend.calls,
                "errors": self.spend.errors, "route_failures": dict(self._route_fail),
                "routes_available": list(self._keys), "caps": CAPS,
                "headroom_5h_usd": round(CAPS["per_5h"] - self.spend.usd, 4)}


if __name__ == "__main__":  # smoke test: python -m agentstall.llm
    g = Gateway(tag="smoke")
    out = g.chat_text("Reply with exactly the word OK and nothing else.", max_tokens=600)
    print("reply:", repr(out.strip()[:80]))
    print("state:", g.budget_state())

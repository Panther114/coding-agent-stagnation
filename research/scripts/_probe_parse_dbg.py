"""Throwaway: show parse internals for the failing fixtures."""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:\Gavania\Academic\Competitions\Agent_Correction\research\src")
sys.path.insert(0, r"D:\Gavania\Academic\Competitions\Agent_Correction\research\scripts")

import test_verify_parser as T  # noqa: E402
from agentstall import verify as V  # noqa: E402

for name in ("UNITTEST_OK_SKIP", "UNITTEST_FAILED_ERRORS", "UNITTEST_MIXED", "PYTEST_PARAM", "NOSE2_FAILEDTEST"):
    obs = getattr(T, name)
    print("=" * 100)
    print("FIXTURE", name)
    up = V._read_unittest(obs)
    print("  _read_unittest ->", None if up is None else
          (up.exit_signal, up.n_tests_passed, up.n_tests_failed, up.n_tests_errored,
           up.n_tests_skipped, up.n_collected, up.raw_matches))
    ep = V._read_errors_only(obs)
    print("  _read_errors_only ->", None if ep is None else
          (ep.exit_signal, ep.n_tests_passed, ep.n_tests_failed, ep.n_tests_errored,
           ep.n_tests_skipped, ep.n_collected, ep.raw_matches))
    pp = V._read_pytest(obs)
    print("  _read_pytest ->", None if pp is None else (pp.exit_signal, pp.raw_matches))
    print("  ids ->", V.extract_failure_ids(obs))
    p = V.parse_observation(obs)
    print("  FINAL ->", p.exit_signal, p.n_tests_passed, p.n_tests_failed, p.n_tests_errored,
          p.n_tests_skipped, p.n_collected)
    for mm in V._UNITTEST_OK.finditer(obs):
        print("   OK body:", repr(mm.group("body")))
    for mm in V._UNITTEST_FAILED.finditer(obs):
        print("   FAILED body:", repr(mm.group("body")))
        for kv in V._UNITTEST_KV.finditer(mm.group("body") or ""):
            print("      kv ->", kv.group("n"), "|", kv.group("kind"))
    for mm in V._NOSE2_FAILEDTEST.finditer(obs):
        print("   nose2:", mm.group("what"), "|", mm.group("cls"))

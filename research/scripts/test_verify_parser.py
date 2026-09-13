"""Unit tests for ``src/agentstall/verify.py``.

Every fixture below is a **literal string captured from the corpus**, taken from
``data/raw/nebius/train-*.parquet`` (see ``docs/VERIFY_PARSER_EVIDENCE.md`` for the
provenance of each).  Nothing here is invented: if a case looks odd, it is because
that is what the corpus actually contains.

Run::

    python -m pytest scripts/test_verify_parser.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agentstall.verify import (  # noqa: E402
    EXIT_ALL_PASS,
    EXIT_COLLECTION_ERROR,
    EXIT_ERROR,
    EXIT_NO_TESTS,
    EXIT_SOME_FAIL,
    EXIT_UNKNOWN,
    RunVerificationTracker,
    canonical_test_id,
    extract_failure_ids,
    parse_observation,
)

# ======================================================================================
# 1. pytest terminal summary with failures and passes  (AnalogJ__lexicon-336 family)
# ======================================================================================

PYTEST_FAIL_PASS = """============================= test session starts ==============================
platform linux -- Python 3.9.19, pytest-8.3.2, pluggy-1.5.0
rootdir: /cognitive_complexity
plugins: mock-3.14.0, bdd-7.2.0, asyncio-0.23.8, hypothesis-6.111.1
asyncio: mode=strict
collected 20 items

tests/test_cognitive_complexity.py .......F........F...                  [100%]

=================================== FAILURES ===================================
______________________________ test_real_function ______________________________

    def test_real_function():
>       assert get_code_snippet_compexity(\"\"\"
E       AssertionError: assert 9 == 11
=========================== short test summary info ============================
FAILED tests/test_cognitive_complexity.py::test_real_function - AssertionError...
FAILED tests/test_cognitive_complexity.py::test_nested_functions - AssertionError:
========================= 2 failed, 18 passed in 0.74s ==========================
(Open file: /cognitive_complexity/tests/test_cognitive_complexity.py)
(Current directory: /cognitive_complexity)
bash-$
"""


def test_pytest_fail_pass_counts_and_signal():
    p = parse_observation(PYTEST_FAIL_PASS)
    assert p.n_tests_failed == 2
    assert p.n_tests_passed == 18
    assert p.n_collected == 20
    assert p.exit_signal == EXIT_SOME_FAIL
    assert p.has_failure is True
    assert p.has_pass is True
    assert "========================= 2 failed, 18 passed in 0.74s ==========================" in p.raw_matches


def test_pytest_fail_pass_failure_ids():
    assert extract_failure_ids(PYTEST_FAIL_PASS) == [
        "tests/test_cognitive_complexity.py::test_real_function",
        "tests/test_cognitive_complexity.py::test_nested_functions",
    ]


# ======================================================================================
# 2. all-pass pytest  (verbatim, same repo)
# ======================================================================================

PYTEST_ALL_PASS = """============================= test session starts ==============================
platform linux -- Python 3.9.19, pytest-8.3.2, pluggy-1.5.0
rootdir: /cognitive_complexity
asyncio: mode=strict
collected 20 items

tests/test_cognitive_complexity.py ....................                  [100%]

============================== 20 passed in 0.18s ==============================

(Open file: /cognitive_complexity/tests/test_cognitive_complexity.py)
(Current directory: /cognitive_complexity)
bash-$
"""


def test_pytest_all_pass():
    p = parse_observation(PYTEST_ALL_PASS)
    assert p.n_tests_passed == 20
    assert p.n_tests_failed is None
    assert p.n_collected == 20
    assert p.exit_signal == EXIT_ALL_PASS
    assert p.has_failure is False
    assert p.has_pass is True
    assert extract_failure_ids(PYTEST_ALL_PASS) == []


# ======================================================================================
# 3. collection error: `collected 0 items / 1 error` + `Interrupted`
#    (AnalogJ__lexicon-336, verbatim)
# ======================================================================================

PYTEST_COLLECTION_ERROR = """============================= test session starts ==============================
platform linux -- Python 3.9.19, pytest-8.3.2, pluggy-1.5.0
rootdir: /lexicon
plugins: mock-3.14.0, bdd-7.2.0, asyncio-0.23.8, hypothesis-6.111.1
asyncio: mode=strict
collected 0 items / 1 error

==================================== ERRORS ====================================
_______________ ERROR collecting tests/providers/test_memset.py ________________
ImportError while importing test module '/lexicon/tests/providers/test_memset.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/providers/integration_tests.py:8: in <module>
    import vcr
E   ModuleNotFoundError: No module named 'vcr'
=========================== short test summary info ============================
ERROR tests/providers/test_memset.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.64s ===============================
(Open file: /lexicon/tests/test_output.py)
(Current directory: /lexicon)
bash-$
"""


def test_pytest_collection_error():
    p = parse_observation(PYTEST_COLLECTION_ERROR)
    assert p.exit_signal == EXIT_COLLECTION_ERROR
    assert p.n_collected == 0
    assert p.has_failure is True
    assert extract_failure_ids(PYTEST_COLLECTION_ERROR) == ["tests/providers/test_memset.py"]


def test_collection_error_counts_are_not_a_pass():
    """`1 error in 0.64s` must never be read as a pass."""
    p = parse_observation(PYTEST_COLLECTION_ERROR)
    assert p.n_tests_passed is None
    assert p.has_pass is False


# ======================================================================================
# 4. unittest: OK with skips  (Azure__azure-functions-python-worker-890, verbatim)
# ======================================================================================

UNITTEST_OK_SKIP = """...Switched to console logging due to exception.
.sSwitched to console logging due to exception.
.s...Switched to console logging due to exception.
.......
....
----------------------------------------------------------------------
Ran 54 tests in 1.038s

OK (skipped=6)

(Open file: /azure-functions-python-worker/azure_functions_worker/constants.py)
(Current directory: /azure-functions-python-worker)
bash-$
"""


def test_unittest_ok_with_skips():
    p = parse_observation(UNITTEST_OK_SKIP)
    assert p.exit_signal == EXIT_ALL_PASS
    assert p.n_collected == 54
    assert p.n_tests_failed == 0
    assert p.n_tests_errored == 0
    assert p.n_tests_skipped == 6
    assert p.n_tests_passed == 48
    assert p.has_pass is True
    assert p.has_failure is False


# ======================================================================================
# 5. unittest: FAILED (errors=1)  (verbatim from the same run family)
# ======================================================================================

UNITTEST_FAILED_ERRORS = """----------------------------------------------------------------------
Traceback (most recent call last):
  File "/azure-functions-python-worker/tests/unittests/test_dispatcher.py", line 357, in _assert_workers_threadpool
    self.assertEqual(ctrl._worker.get_sync_tp_workers_set(),
AssertionError: 1 != 100000

======================================================================
FAIL: test_dispatcher_sync_threadpool (tests.unittests.test_dispatcher.TestThreadPoolSettingsPython37)
Test if the sync threadpool will pick up app setting in placeholder
----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
"""


def test_unittest_failed_errors():
    p = parse_observation(UNITTEST_FAILED_ERRORS)
    assert p.exit_signal == EXIT_SOME_FAIL
    assert p.n_tests_errored == 1
    assert p.n_collected == 1
    assert p.has_failure is True
    assert extract_failure_ids(UNITTEST_FAILED_ERRORS) == [
        "tests/unittests/test_dispatcher.py::TestThreadPoolSettingsPython37::test_dispatcher_sync_threadpool"
    ]


# ======================================================================================
# 6. unittest: the heavy mixed form  `FAILED (failures=4, errors=9, skipped=3, ...)`
# ======================================================================================

UNITTEST_MIXED = """======================================================================
ERROR: test_alpha (tests.test_core.TestCore)
----------------------------------------------------------------------
Ran 40 tests in 2.510s

FAILED (failures=4, errors=9, skipped=3, expected failures=1)
"""


def test_unittest_mixed_counts():
    p = parse_observation(UNITTEST_MIXED)
    assert p.n_tests_failed == 4
    assert p.n_tests_errored == 9
    assert p.n_tests_skipped == 3
    assert p.n_collected == 40
    assert p.exit_signal == EXIT_SOME_FAIL


# ======================================================================================
# 7. `Ran 0 tests` + OK -- not a pass
# ======================================================================================

UNITTEST_RAN_ZERO = """----------------------------------------------------------------------
Ran 0 tests in 0.000s

OK
"""


def test_unittest_ran_zero_is_no_tests():
    p = parse_observation(UNITTEST_RAN_ZERO)
    assert p.exit_signal == EXIT_NO_TESTS
    assert p.n_collected == 0
    assert p.has_pass is False


# ======================================================================================
# 8. parametrised node ids  (asottile__pyupgrade / hypothesis plugin family)
# ======================================================================================

PYTEST_PARAM = """=================================== FAILURES ===================================
=========================== short test summary info ============================
FAILED tests/func/test_add.py::test_should_protect_on_repeated_add[add_repeated] - AssertionError
FAILED tests/test_hypothesis_plugin.py::test_can_construct_models_with_all_fields[1-2-X] - TypeError: ...
FAILED tests/set_literals_test.py::test_x[with spaces-in id] - SystemExit: 1
FAILED tests/api_test.py::test_missing_args[-x-y] - Failed: DID NOT RAISE
========================= 4 failed, 615 passed in 3.03s =========================
"""


def test_parametrised_ids_are_preserved_verbatim():
    ids = extract_failure_ids(PYTEST_PARAM)
    assert ids == [
        "tests/func/test_add.py::test_should_protect_on_repeated_add[add_repeated]",
        "tests/test_hypothesis_plugin.py::test_can_construct_models_with_all_fields[1-2-X]",
        "tests/set_literals_test.py::test_x[with spaces-in id]",
        "tests/api_test.py::test_missing_args[-x-y]",
    ]


def test_parametrised_counts():
    p = parse_observation(PYTEST_PARAM)
    assert p.n_tests_failed == 4
    assert p.n_tests_passed == 615


# ======================================================================================
# 9. warnings interleaved between progress and summary
# ======================================================================================

PYTEST_WARNINGS_INTERLEAVED = """============================= test session starts ==============================
collected 3 items

tests/test_a.py ...
tests/test_b.py s
tests/test_c.py x

=============================== warnings summary ===============================
tests/test_mem.py:96
  /x/tests/test_mem.py:96: DeprecationWarning: TestClass.__init__ is deprecated
    return super().__init__(*args, **kwargs)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 1 passed, 4 warnings in 0.15s ========================
"""


def test_warnings_interleaved():
    p = parse_observation(PYTEST_WARNINGS_INTERLEAVED)
    assert p.exit_signal == EXIT_ALL_PASS
    assert p.n_tests_passed == 1
    assert p.n_collected == 3
    # `4 warnings` must not become a failure or a pass count
    assert p.n_tests_failed is None
    assert p.n_tests_errored is None


def test_warning_word_not_read_as_failure():
    """`4 warnings` in the summary body must not be mistaken for `4 errors`."""
    p = parse_observation(PYTEST_WARNINGS_INTERLEAVED)
    assert p.has_failure is False


# ======================================================================================
# 10. deselected tests
# ======================================================================================

PYTEST_DESELECTED = """============================= test session starts ==============================
collected 55 items / 54 deselected / 1 selected

tests/test_x.py .
================= 1 passed, 54 deselected, 4 warnings in 0.64s =================
"""


def test_deselected_not_counted_as_tests():
    p = parse_observation(PYTEST_DESELECTED)
    assert p.n_tests_passed == 1
    assert p.n_tests_failed is None
    assert p.exit_signal == EXIT_ALL_PASS


# ======================================================================================
# 11. truncated output: summary cut off, progress survives  (asottile__pyupgrade-208)
# ======================================================================================

PYTEST_TRUNCATED = """============================= test session starts ==============================
platform linux -- Python 3.9.19, pytest-8.3.2, pluggy-1.5.0
rootdir: /pyupgrade
collected 619 items

tests/set_literals_test.py .x.x..........................                [  4%]
tests/binary_literals_test.py ..................F                        [  7%]
tests/long_literals_test.py FFF                                          [  8%]
tests/identity_equality_test.py ..................                       [ 11%]
tests/misc_test.py ...........                                           [ 13%]
tests/format_literals_test.py ...............................            [ 18%]
tests/escape_sequences_test.py ...........................               [ 22%]
tests/versioned_branches_test.py ...............................         [ 27%]
tests/main_test.py .................                                     [ 30%]
tests/encoding_cookie_test.py .....                                      [ 31%]
tests/future_imports_test.py .................                           [ 33%]
tests/default_encoding_test.py .........                                 [ 35%]
tests/super_test.py ................                                     [ 37%]
tests/native_literals_test.py ..........                                 [ 39%]
tests/io_open_test.py ..                                                 [ 39%]
tests/percent_format_test.py ..................
tests/octal_literals_test.py ..FF....                                    [ 51%]
tests/unicode_literals_test.py .............                             [ 53%]
tests/raw_unicode_literals_test.py FFFFFF                                [ 54%]
tests/dict_literals_test.py ..................                           [ 57%]
tests/fstrings_test.py ........................                          [ 61%]
tests/new_style_classes_test.py ................                         [ 64%]
tests/yield_from_test.py .....................                           [ 67%]
tests/six_test.py ...................................................... [ 76%]
............                                                             [ 78%]
tests/oserror_aliases_test.py .......................................... [ 85%]
........................................................................ [ 96%]
........                                                                 [ 98%]
tests/extra_parens_test.py ............                                  [100%]

=================================== FA
"""


def test_truncated_pytest_reports_unknown_but_flags_progress():
    """The honest answer: tests clearly ran, the verdict is not in the observation."""
    p = parse_observation(PYTEST_TRUNCATED)
    assert p.exit_signal == EXIT_UNKNOWN
    assert p.n_tests_passed is None
    assert p.n_tests_failed is None
    assert p.n_tests_errored is None
    assert p.has_progress is True
    assert p.has_test_evidence is True
    assert p.n_collected == 619


def test_truncated_pytest_is_not_counted_as_covered():
    assert parse_observation(PYTEST_TRUNCATED).resolved is False


def test_truncated_pytest_not_misread_as_all_pass():
    """Regression guard: `... [100%]` and no failure text must not become all_pass."""
    assert parse_observation(PYTEST_TRUNCATED).exit_signal != EXIT_ALL_PASS


def test_truncated_flag_detects_the_cut():
    """The tail ends mid-word (`=============== FA`), so the observation was cut."""
    assert parse_observation(PYTEST_TRUNCATED).truncated is True
    assert parse_observation(PYTEST_ALL_PASS).truncated is False


def test_truncated_flag_on_elided_failure_message():
    """`- RuntimeError: ...` is the harness eliding, not pytest's own `:::` short form."""
    assert parse_observation(PYTEST_TRUNCATED_SUMMARY).truncated is True


# ======================================================================================
# 12. genuinely truncated short summary: `FAILED <id> - RuntimeError: ...`
# ======================================================================================

PYTEST_TRUNCATED_SUMMARY = """============================= test session starts ==============================
collected 28 items

tests/test_setup_profile.py FFFFFFFFFFFFFFFFFFFF                      [ 64%]

=================================== FAILURES ===================================
_______________________ test_no_keypair_provided _______________________________
=========================== short test summary info ============================
FAILED tests/test_setup_profile.py::test_no_keypair_provided - RuntimeError: ...
FAILED tests/test_setup_profile.py::test_validate_orcid_id - TypeError: valid...
"""


def test_truncated_short_summary_still_yields_ids():
    ids = extract_failure_ids(PYTEST_TRUNCATED_SUMMARY)
    assert ids == [
        "tests/test_setup_profile.py::test_no_keypair_provided",
        "tests/test_setup_profile.py::test_validate_orcid_id",
    ]
    p = parse_observation(PYTEST_TRUNCATED_SUMMARY)
    assert p.has_failure is True
    assert p.has_progress is True


# ======================================================================================
# 13. no tests collected at all
# ======================================================================================

PYTEST_NO_TESTS = """============================= test session starts ==============================
collected 0 items

============================ no tests ran in 0.01s =============================
"""


def test_no_tests_ran():
    p = parse_observation(PYTEST_NO_TESTS)
    assert p.exit_signal == EXIT_NO_TESTS
    assert p.n_collected == 0
    assert p.has_pass is False
    assert p.has_failure is False


# ======================================================================================
# 14. timeout / killed suite -- no verdict recoverable
# ======================================================================================

PYTEST_TIMEOUT = """============================= test session starts ==============================
collected 400 items

tests/test_slow.py ...................
Command timed out after 180 seconds
"""


def test_timeout_is_unknown_not_pass():
    p = parse_observation(PYTEST_TIMEOUT)
    assert p.exit_signal == EXIT_UNKNOWN
    assert p.has_pass is False
    assert p.has_failure is False
    assert p.n_collected == 400


# ======================================================================================
# 15. non-test output that merely mentions "error" must stay unknown
# ======================================================================================

NOT_A_TEST = """Traceback (most recent call last):
  File "setup.py", line 3, in <module>
ModuleNotFoundError: No module named 'foo'
ERROR: Could not find a version that satisfies the requirement astarte (from versions: none)
ERROR: No matching distribution found for astarte
"""


def test_dependency_error_is_not_a_test_outcome():
    p = parse_observation(NOT_A_TEST)
    assert p.exit_signal == EXIT_UNKNOWN
    assert p.n_tests_failed is None
    assert p.resolved is False
    assert extract_failure_ids(NOT_A_TEST) == []


def test_empty_observation():
    p = parse_observation("")
    assert p.exit_signal == EXIT_UNKNOWN
    assert p.resolved is False
    assert parse_observation("bash-$").resolved is False


# ======================================================================================
# 16. node-id canonicalisation across reporters
# ======================================================================================


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("tests/test_aggregations.py::TestBooleanAggregation::test_all",
         "tests/test_aggregations.py::TestBooleanAggregation::test_all"),
        ("test_all (tests.test_aggregations.TestBooleanAggregation)",
         "tests/test_aggregations.py::TestBooleanAggregation::test_all"),
        ("test_save_configs (tests.save_configs_test.TestSaveConfigs)",
         "tests/save_configs_test.py::TestSaveConfigs::test_save_configs"),
        ("test_trim_end (tests.test_vector.VectorTestCase)",
         "tests/test_vector.py::VectorTestCase::test_trim_end"),
        ("tests/unit/test_load.py::TestLoad::test_load_terraform", "tests/unit/test_load.py::TestLoad::test_load_terraform"),
        ("tests/test_cli.py::test_cli_run_file_array", "tests/test_cli.py::test_cli_run_file_array"),
        ("not a test id at all", None),
        ("", None),
        ("error", None),
    ],
)
def test_canonical_test_id(raw, expect):
    assert canonical_test_id(raw) == expect


def test_canonicalisation_makes_reporters_comparable():
    """The same test read from pytest and from unittest must collapse to one id."""
    a = extract_failure_ids("FAILED tests/test_aggregations.py::TestBooleanAggregation::test_all - AssertionError")
    b = extract_failure_ids("FAIL: test_all (tests.test_aggregations.TestBooleanAggregation)")
    assert a == b == ["tests/test_aggregations.py::TestBooleanAggregation::test_all"]


# ======================================================================================
# 17. standalone unittest banner without a summary
# ======================================================================================

UNITTEST_BANNER_ONLY = """----------------------------------------------------------------------
FAIL: test_all (tests.test_aggregations.TestBooleanAggregation)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/x/tests/test_aggregations.py", line 40, in test_all
    self.assertTrue(agg.evaluate(...))
AssertionError: False is not true
"""


def test_unittest_banner_without_summary():
    assert extract_failure_ids(UNITTEST_BANNER_ONLY) == [
        "tests/test_aggregations.py::TestBooleanAggregation::test_all"
    ]
    p = parse_observation(UNITTEST_BANNER_ONLY)
    assert p.has_failure is True
    assert p.exit_signal == EXIT_SOME_FAIL


# ======================================================================================
# 18. nose2 loader failure
# ======================================================================================

NOSE2_FAILEDTEST = """ERROR: test_mock.TestMock.test_foo (nose2.loader.LoadTestsFailure)
ERROR: tests (unittest.loader._FailedTest)
"""


def test_nose2_loader_failure_is_an_error():
    p = parse_observation(NOSE2_FAILEDTEST)
    assert p.exit_signal == EXIT_ERROR
    assert p.has_failure is True


# ======================================================================================
# 19. sequence tracking: the key quantity
# ======================================================================================

STEP_ALREADY_FAILING = """=========================== short test summary info ============================
FAILED tests/test_a.py::test_one - AssertionError
FAILED tests/test_a.py::test_two - AssertionError
========================= 2 failed, 8 passed in 0.30s ==========================
"""

STEP_STILL_FAILING = """=========================== short test summary info ============================
FAILED tests/test_a.py::test_one - AssertionError
FAILED tests/test_a.py::test_three - AssertionError
========================= 2 failed, 8 passed in 0.31s ==========================
"""

STEP_FIXED = """============================== 10 passed in 0.29s ==============================
"""


def test_new_failure_ids_separates_pre_existing_from_caused():
    t = RunVerificationTracker()
    r0 = t.add(0, STEP_ALREADY_FAILING)
    r1 = t.add(1, STEP_STILL_FAILING)
    # test_one was already failing -> NOT new; test_three is genuinely new
    assert r0.new_failure_ids == ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]
    assert r1.new_failure_ids == ["tests/test_a.py::test_three"]
    assert r1.prev_failure_ids == ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]


def test_new_failure_ids_not_reset_by_unknown_steps():
    """An unparseable step in between must not make old failures look new again."""
    t = RunVerificationTracker()
    t.add(0, STEP_ALREADY_FAILING)
    t.add(1, "some unrelated output, no test verdict here")
    r = t.add(2, STEP_STILL_FAILING)
    assert r.new_failure_ids == ["tests/test_a.py::test_three"]


def test_new_failure_ids_empty_when_all_pass():
    t = RunVerificationTracker()
    t.add(0, STEP_ALREADY_FAILING)
    r = t.add(1, STEP_FIXED)
    assert r.new_failure_ids == []
    assert r.test_exit_signal == EXIT_ALL_PASS


def test_regression_after_a_green_step_counts_as_new():
    """test_one passed at step 1, so failing again at step 2 IS new information."""
    t = RunVerificationTracker()
    t.add(0, STEP_ALREADY_FAILING)
    t.add(1, STEP_FIXED)
    r = t.add(2, STEP_ALREADY_FAILING)
    assert r.new_failure_ids == ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]


def test_tracker_records_every_step():
    t = RunVerificationTracker()
    recs = t.add_many([STEP_ALREADY_FAILING, "no verdict", STEP_FIXED])
    assert [r.step for r in recs] == [0, 1, 2]
    assert [r.test_exit_signal for r in recs] == [EXIT_SOME_FAIL, EXIT_UNKNOWN, EXIT_ALL_PASS]
    assert sum(r.has_test_obs for r in recs) == 2


def test_tracker_reset_between_runs():
    t = RunVerificationTracker()
    t.add(0, STEP_ALREADY_FAILING)
    t.reset()
    r = t.add(0, STEP_STILL_FAILING)
    assert r.new_failure_ids == ["tests/test_a.py::test_one", "tests/test_a.py::test_three"]


def test_unittest_error_count_still_yields_an_id():
    """`FAILED (errors=1)` names no test; the ERROR banner is the only source of the id.

    Captured from Melevir__cognitive_complexity-15, where the agent runs a single test
    and unittest reports `FAILED (errors=1)` with the failing banner above it.
    """
    obs = (
        "============================= test session starts ==============================\n"
        "collected 1 item\n\n"
        "tests/test_cognitive_complexity.py F                                     [100%]\n\n"
        "======================================================================\n"
        "ERROR: test_real_function (tests.test_cognitive_complexity.TestComplexity)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        "  File \"/cognitive_complexity/tests/test_cognitive_complexity.py\", line 40\n"
        "    assert get_code_snippet_compexity(x) == 11\n"
        "AssertionError: assert 9 == 11\n\n"
        "----------------------------------------------------------------------\n"
        "Ran 1 test in 0.012s\n\n"
        "FAILED (errors=1)\n"
    )
    p = parse_observation(obs)
    assert p.exit_signal == EXIT_SOME_FAIL
    assert p.n_tests_errored == 1
    assert p.failure_ids == ["tests/test_cognitive_complexity.py::TestComplexity::test_real_function"]
    assert p.has_failure is True


def test_pytest_error_line_does_not_leak_into_unittest_ids():
    """pytest writes `ERROR tests/x.py` (no colon); that is a module, not `test_`-named."""
    assert extract_failure_ids("ERROR tests/providers/test_memset.py\n") == [
        "tests/providers/test_memset.py"
    ]


# ======================================================================================
# 21. a verdict reporting failures with no named ids is still a failure
# ======================================================================================

FAILED_WITHOUT_IDS = """----------------------------------------------------------------------
Ran 12 tests in 0.400s

FAILED (failures=2)
"""


def test_failure_count_present_ids_absent():
    p = parse_observation(FAILED_WITHOUT_IDS)
    assert p.exit_signal == EXIT_SOME_FAIL
    assert p.n_tests_failed == 2
    assert p.has_failure is True
    assert p.failure_ids == []


# ======================================================================================
# 22. tracker bookkeeping across a run
# ======================================================================================

def test_prev_failure_ids_empty_on_first_observation():
    t = RunVerificationTracker()
    r = t.add(0, STEP_STILL_FAILING)
    assert r.prev_failure_ids == []
    assert r.new_failure_ids == ["tests/test_a.py::test_one", "tests/test_a.py::test_three"]


def test_new_failure_ids_is_empty_when_nothing_fails():
    t = RunVerificationTracker()
    r = t.add(0, "no test output at all")
    assert r.new_failure_ids == []
    assert r.prev_failure_ids == []


def test_named_ids_without_a_verdict_still_update_the_tracker():
    """A step that names failing tests but has no summary must still advance the set.

    Otherwise the next step's identical failures would be reported as brand new.
    """
    t = RunVerificationTracker()
    r0 = t.add(0, "FAILED tests/test_a.py::test_one - AssertionError\n")
    assert r0.test_exit_signal == EXIT_SOME_FAIL
    assert r0.new_failure_ids == ["tests/test_a.py::test_one"]
    r1 = t.add(1, "FAILED tests/test_a.py::test_one - AssertionError\n")
    assert r1.new_failure_ids == []
    assert r1.prev_failure_ids == ["tests/test_a.py::test_one"]


# ======================================================================================
# 20. `1 error in 0.64s` inside a session is a collection error, not a test failure
# ======================================================================================

PYTEST_MODULE_ERROR = """============================= test session starts ==============================
collected 12 items / 1 error

==================================== ERRORS ====================================
___________ ERROR collecting tests/test_broken.py ___________
E   SyntaxError: invalid syntax
=============================== 1 error in 0.31s ===============================
"""


def test_module_level_error_classified_as_collection_error():
    p = parse_observation(PYTEST_MODULE_ERROR)
    assert p.exit_signal == EXIT_COLLECTION_ERROR
    assert p.n_collected == 12
    assert p.has_failure is True

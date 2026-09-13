# Live task suite — localisation-vs-fix experiment

A runnable, offline, pure-Python task suite for the causal experiment on **whether
localisation or the fix is the bottleneck** in LLM coding agents.

Each task is a real PyPI project with exactly one injected defect in one function and
the project's own test suite as the verifier. The same defect instance can be presented
in two conditions that differ *only in the task statement*:

* **lost** — no location hint: the agent sees the whole repo tree and must find the defect;
* **directed** — the exact file and function are named in the statement.

The repository, the defect, and the verifier are byte-identical across conditions, so the
only manipulated variable is localisation difficulty.

---

## 1. What ships

| Artifact | Purpose |
| --- | --- |
| `data/live/tasks.jsonl` | **48 tasks**, one JSON object per line (schema in §4) |
| `data/live/prepare_workspace.py` | materialise one task's workspace from a `task_id` |
| `data/live/verify_suite.py` | re-verify every task end-to-end (fails-before / passes-after) |
| `data/live/verify_report.json` | output of the last full verification run (per-task evidence) |
| `data/live/prepare_environment.txt` | pinned runtime dependencies for the venv |
| `data/live/project_pins.txt` | the eight project archives, ready to `pip install` |
| `data/live/packages/<pkg>-<ver>.zip` | pinned source trees, LF-normalised, fixed mtimes |

Nothing here needs Docker, a compiler, or network access at run time.

## 2. Packages chosen

**8 packages, 6 tasks each — 48 tasks total.**

| package | version | tasks | `.py` source files | test files | tests passing after fix | pre-existing failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `boltons` | 26.2.0 | 6 | 30 | 31 | 518 | 1 |
| `furl` | 2.1.4 | 6 | 13 | 2 | 77 | 0 |
| `humanize` | 4.16.0 | 6 | 7 | 7 | 784 | 0 |
| `inflect` | 7.5.0 | 6 | 7 | 14 | 207 | 0 |
| `more-itertools` | 11.1.0 | 6 | 5 | 3 | 548 | 0 |
| `tabulate` | 0.10.0 | 6 | 3 | 8 | 280 | 0 |
| `toolz` | 1.1.0 | 6 | 34 | 32 | 180 | 0 |
| `validators` | 0.35.0 | 6 | 65 | 28 | 878 | 17 |

`n_source_files` counts every `.py` file in the extracted project that is not a test file;
it is the size of the search space an agent faces in the **lost** condition, and it ranges
from 3 (`tabulate`) to 65 (`validators`).

Totals: **48 tasks, 3,472 tests green after the fix, 29 distinct source files, 33 distinct functions.**

### Verifier scope notes (all deliberate, all recorded per task)

* `more-itertools` — `tests/test_recipes.py` is excluded from the test command. It is a
  single 15-minute module of generative property tests; every task's signature comes from
  `tests/test_more.py`, which runs in ~40 s. This keeps a task round-trip under 90 s.
* `toolz` — `toolz/tests/test_curried_doctests.py` is excluded; it walks
  `toolz/tests/*.py` and re-runs their docstrings as doctests, which duplicates the suite.
* `boltons` — `tests/test_jsonutils.py::test_reverse_iter_lines` fails on this machine
  before any injection (a pre-existing upstream/environment failure). It is recorded in
  `pre_existing_failures` for every boltons task and ignored by the verifier.
* `validators` — 17 `tests/crypto_addresses/test_eth_address.py` tests fail before any
  injection because the optional `eth-hash[pycryptodome]` extra is not installed. They are
  recorded in `pre_existing_failures` and ignored by the verifier.

Correctness definition used throughout (and enforced by `verify_suite.py`): with the mutant
in place the suite must fail with at least one test **outside** `pre_existing_failures`;
with the original source restored the suite must fail with **no** test outside
`pre_existing_failures`.

## 3. Mutation strategy

A build-time AST mutator rewrites **one expression inside one function**, SWE-smith style.
Mutations are applied by exact `(line, column-span)` replacement, so applying a mutation
can never hit an ambiguous match elsewhere in the file; the manifest additionally stores
the full before/after file text, so the runner never needs to re-derive anything.

Seven families were generated:

| family | example |
| --- | --- |
| `swap_comparison` | `if size == 0:` → `if size != 0:` |
| `swap_boolean` | `if a and b:` → `if a or b:` |
| `invert_predicate` | `return n <= 0` → `return n > 0` |
| `invert_boolean` | `use_float = False` → `use_float = True` |
| `off_by_one` | `parts[1]` → `parts[2]`, `if n == 1:` → `if n == 2:` |
| `swap_operator` | `(width - len(line))` → `(width + len(line))` |
| `wrong_variable` / `wrap_return` | `self[key] = value` → `self[key] = val`; `return self` → `return len(self)` |

Candidate selection was **test-driven**, not random: the mutator mines the vendor's own
test files for the function names they call, ranks candidates so that mutations landing in
functions the suite actually exercises come first, and a sweep then applies candidates to
the pristine tree one at a time and keeps only those for which the vendor suite genuinely
goes red. Candidates that no test detects are discarded, not shipped.

**Yield: 95 mutations were executed to obtain the 48 shipped tasks (≈ 51 % kept).** The
rejected ones were dropped because the suite did not fail (`no-effect`) or because the
mutation produced a collection-level crash rather than a test failure.

Every shipped task is a single-line diff: `injected_edit` gives `line`, `col_start`,
`col_end`, the replaced expression and its replacement, plus the full original and mutated
lines.

## 4. `tasks.jsonl` schema

Required fields (all present on all 48 records):

| field | meaning |
| --- | --- |
| `task_id` | stable id, `live__<pkg>__<ver>__<kind>__<file>_L<line>` |
| `package`, `package_version` | PyPI project and exact version |
| `repo_root` | `"."` — repo root is the workspace root |
| `gold_file` | defective file, path relative to the workspace root |
| `gold_function` | function containing the defect |
| `mutated_source` | **entire** buggy file contents |
| `original_source` | **entire** fixed file contents |
| `test_command` | human-readable verifier command, run from the workspace root |
| `n_source_files` | `.py` files in the project that are not tests |
| `n_test_files` | `.py` files in the project's test tree |
| `failure_signature` | first failing pytest node id with the bug present |
| `expected_pass_after_fix` | `true` on every shipped task |

Extra fields a runner may want: `test_args` (argv array for pytest), `test_target`,
`test_extra_args`, `python_bin`, `env_pythonpath` (`"src"` for src-layout packages, else
`null`), `bug_kind`, `bug_description`, `injected_edit`, `failing_tests` (all node ids),
`n_failing_tests`, `pre_existing_failures`, `n_passing_after_fix`, `gold_function_lineno`,
`source_url`, `source_archive_sha256` (pinned `.zip`), `upstream_sha256` (original sdist).

## 5. Reproducing

### 5.1 Environment

Python 3.10.9. The suite was built and verified with this environment (Windows, venv):

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r data\live\prepare_environment.txt
```

Then install the eight projects themselves so that `importlib.metadata` sees their
metadata (the `toolz` suite asserts its own version). PowerShell does **not** expand
`packages\*.zip` for a native command like pip, so spell the eight names out (they are
listed in `data\live\project_pins.txt`):

```powershell
cd research\data\live
.venv\Scripts\python -m pip install --no-deps packages\boltons-26.2.0.zip packages\furl-2.1.4.zip packages\humanize-4.16.0.zip packages\inflect-7.5.0.zip packages\more-itertools-11.1.0.zip packages\tabulate-0.10.0.zip packages\toolz-1.1.0.zip packages\validators-0.35.0.zip
```

`python_bin` in every record points at the interpreter used for verification; replace it
with the interpreter of your environment (the runner only needs `python -m pytest`), e.g.
`verify_suite.py --python-bin .venv\Scripts\python.exe`.

### 5.2 Materialise one workspace

```bat
python research\data\live\prepare_workspace.py ^
    --task-id live__toolz__1.1.0__swap_comparison__dicttoolz_L33 ^
    --target-dir C:\tmp\ws ^
    --condition directed
```

The target directory is fully rebuilt on every call, so it is safe to call repeatedly
(idempotent). Layout produced:

```
C:\tmp\ws\
  toolz\ ...  (repo root contents, gold_file mutated)
  .task\task.json           # metadata, no sources
  .task\objective.md        # the task statement for the chosen condition
  .task\run_tests.cmd/.sh   # the exact verifier command
```

`--condition lost` writes a statement with no location hint; `--condition directed` names
`gold_file` and `gold_function`. The repository is identical in both cases — the
manipulation lives only in `.task/objective.md`, which is the text you hand to the agent.

`--original` writes the pristine file instead (useful for a "fix already applied" control);
`--list` prints all task ids.

Because the manifest carries the complete before/after text of the gold file, preparation
never parses, patches, or diffs anything: it extracts the pinned archive, asserts the file
on disk equals `original_source`, and overwrites it with `mutated_source`. That assertion
is what makes a manifest/archive mismatch loud instead of silent.

### 5.3 Run the verifier of one task

```bat
cd C:\tmp\ws
python -m pytest toolz/tests -q --no-header -p no:cacheprovider ^
    --ignore toolz/tests/test_curried_doctests.py
```

For src-layout packages (`humanize`, `validators`) set the path first:

```bat
set PYTHONPATH=C:\tmp\ws\src
python -m pytest tests -q --no-header -p no:cacheprovider
```

### 5.4 Re-verify the whole suite (the honest gate)

```bat
cd research\data\live
python verify_suite.py --json-report verify_report.json
```

This rebuilds each workspace twice through `prepare_workspace.py` (mutated, then restored)
and runs the real vendor suite on both. It is the same check that produced §6, and it was
run twice: once in the build environment, and once again in a **freshly created venv built
only from the commands in §5.1** (`--python-bin` pointed at it) to prove the suite does not
depend on the build session's state.

## 6. Verification result

All 48 tasks were re-verified from the shipped manifest and pinned archives, not from the
build session's memory. The check was run **twice**:

| run | environment | result |
| --- | --- | --- |
| 1 | build venv | `48/48 ok, 0 bad, 1252.5s` |
| 2 | fresh venv created only from §5.1 (`--python-bin` pointed at it) | `48/48 ok, 0 bad, 1830.9s` |

Run 2 is the shipped `verify_report.json`. Every task failed before the fix with at least
one **non-pre-existing** test, and every task's suite was fully green (modulo
`pre_existing_failures`) after restoring `original_source`.

Additional invariants checked mechanically on the shipped manifest (all 48 records, 0
errors): all required fields present, unique `task_id`, `expected_pass_after_fix is true`,
`repo_root == "."`, `gold_file` relative and free of `..`, `n_source_files`/`n_test_files`
positive integers, `failure_signature` a pytest node id and present in `failing_tests` and
absent from `pre_existing_failures`, both sources parse with `ast.parse`, exactly one line
differs between them, `injected_edit` slices that differing line exactly, and
`source_archive_sha256` matches the shipped `.zip`.

`prepare_workspace.py` was confirmed **idempotent**: two consecutive identical calls for
`live__humanize__4.16.0__swap_comparison__i18n_L75` produced 127 files with byte-identical
SHA-256 hashes (0 differing files).

| task_id | gold file | function | bug kind | tests failing | first failing node id | pass after fix | s |
| --- | --- | --- | --- | ---: | --- | ---: | ---: |
| live__boltons__26.2.0__swap_comparison__cacheutils_L711 | boltons/cacheutils.py | add | swap_comparison | 4 | tests/test_cacheutils.py::test_threshold_counter | 518 | 7 |
| live__boltons__26.2.0__swap_comparison__ioutils_L309 | boltons/ioutils.py | write | swap_comparison | 3 | tests/test_ioutils.py::TestSpooledBytesIO::test_auto_rollover | 518 | 9 |
| live__boltons__26.2.0__swap_comparison__queueutils_L133 | boltons/queueutils.py | add | swap_comparison | 3 | tests/test_queueutils.py::test_heap_queue | 518 | 10 |
| live__boltons__26.2.0__swap_comparison__socketutils_L673 | boltons/socketutils.py | read_ns | swap_comparison | 3 | tests/test_socketutils.py::test_socketutils_netstring | 518 | 9 |
| live__boltons__26.2.0__swap_comparison__strutils_L1323 | boltons/strutils.py | human_readable_list | swap_comparison | 3 | tests/test_strutils.py::test_human_readable_list | 518 | 10 |
| live__boltons__26.2.0__swap_comparison__urlutils_L673 | boltons/urlutils.py | navigate | swap_comparison | 2 | tests/test_urlutils.py::test_navigate | 518 | 7 |
| live__furl__2.1.4__swap_comparison__furl_L309 | furl/furl.py | urlsplit | swap_comparison | 3 | tests/test_furl.py::TestFurl::test_basics | 77 | 12 |
| live__furl__2.1.4__invert_boolean__furl_L598 | furl/furl.py | isabsolute | invert_boolean | 14 | tests/test_furl.py::TestPath::test_add | 77 | 13 |
| live__furl__2.1.4__swap_comparison__furl_L620 | furl/furl.py | isdir | swap_comparison | 4 | tests/test_furl.py::TestPath::test_asdict | 77 | 19 |
| live__furl__2.1.4__wrong_variable__omdict1D_L50 | furl/omdict1D.py | add | wrong_variable | 41 | tests/test_furl.py::TestQuery::test_add | 77 | 14 |
| live__furl__2.1.4__wrong_variable__omdict1D_L54 | furl/omdict1D.py | add | wrong_variable | 41 | tests/test_furl.py::TestQuery::test_add | 77 | 13 |
| live__furl__2.1.4__wrap_return__omdict1D_L60 | furl/omdict1D.py | add | wrap_return | 2 | tests/test_furl.py::TestQuery::test_params | 77 | 16 |
| live__humanize__4.16.0__swap_comparison__filesize_L95 | src/humanize/filesize.py | naturalsize | swap_comparison | 63 | tests/test_filesize.py::test_naturalsize[test_args0-300 Bytes] | 784 | 14 |
| live__humanize__4.16.0__swap_comparison__i18n_L75 | src/humanize/i18n.py | activate | swap_comparison | 69 | tests/test_i18n.py::test_i18n | 784 | 14 |
| live__humanize__4.16.0__swap_comparison__lists_L33 | src/humanize/lists.py | natural_list | swap_comparison | 7 | tests/test_lists.py::test_natural_list[test_args0-1, 2 and 3] | 784 | 15 |
| live__humanize__4.16.0__swap_comparison__number_L159 | src/humanize/number.py | intcomma | swap_comparison | 10 | tests/test_i18n.py::test_intcomma | 784 | 12 |
| live__humanize__4.16.0__swap_comparison__time_L287 | src/humanize/time.py | naturaltime | swap_comparison | 171 | tests/test_i18n.py::test_i18n | 784 | 13 |
| live__humanize__4.16.0__swap_comparison__time_L291 | src/humanize/time.py | naturaltime | swap_comparison | 149 | tests/test_i18n.py::test_i18n | 784 | 12 |
| live__inflect__7.5.0__swap_comparison____init___L2182 | inflect/__init__.py | ud_match | swap_comparison | 3 | tests/test_inflections.py::test_def | 207 | 13 |
| live__inflect__7.5.0__swap_comparison____init___L2212 | inflect/__init__.py | classical | swap_comparison | 12 | tests/test_classical_all.py::Test::test_classical | 207 | 11 |
| live__inflect__7.5.0__swap_comparison____init___L2219 | inflect/__init__.py | classical | swap_comparison | 17 | tests/test_classical_all.py::Test::test_classical | 207 | 11 |
| live__inflect__7.5.0__swap_comparison____init___L2592 | inflect/__init__.py | singular_noun | swap_comparison | 12 | tests/test_compounds.py::test_compound_1 | 207 | 8 |
| live__inflect__7.5.0__invert_boolean____init___L2595 | inflect/__init__.py | singular_noun | invert_boolean | 1 | tests/test_pwd.py::Test::test_sinoun | 207 | 8 |
| live__inflect__7.5.0__swap_comparison____init___L3659 | inflect/__init__.py | ordinal | swap_comparison | 1 | tests/test_inflections.py::test_ordinal | 207 | 7 |
| live__more_itertools__11.1.0__invert_boolean__more_L3148 | more_itertools/more.py | exactly_n | invert_boolean | 1 | tests/test_more.py::ExactlyNTests::test_false | 548 | 40 |
| live__more_itertools__11.1.0__invert_boolean__more_L3150 | more_itertools/more.py | exactly_n | invert_boolean | 1 | tests/test_more.py::ExactlyNTests::test_false | 548 | 35 |
| live__more_itertools__11.1.0__invert_boolean__more_L3151 | more_itertools/more.py | exactly_n | invert_boolean | 2 | tests/test_more.py::ExactlyNTests::test_empty | 548 | 36 |
| live__more_itertools__11.1.0__invert_boolean__more_L3156 | more_itertools/more.py | exactly_n | invert_boolean | 1 | tests/test_more.py::ExactlyNTests::test_false | 548 | 33 |
| live__more_itertools__11.1.0__invert_boolean__recipes_L237 | more_itertools/recipes.py | all_equal | invert_boolean | 3 | tests/test_more.py::IequalsTests::test_basic | 548 | 41 |
| live__more_itertools__11.1.0__invert_boolean__recipes_L238 | more_itertools/recipes.py | all_equal | invert_boolean | 9 | tests/test_more.py::LongestCommonPrefixTests::test_basic | 548 | 31 |
| live__tabulate__0.10.0__swap_operator____init___L2589 | tabulate/__init__.py | _align_cell_veritically | swap_operator | 8 | test/test_internal.py::test_align_cell_veritically_one_line_only | 280 | 12 |
| live__tabulate__0.10.0__swap_operator____init___L2590 | tabulate/__init__.py | _align_cell_veritically | swap_operator | 82 | test/test_internal.py::test_align_cell_veritically_one_line_only | 280 | 4 |
| live__tabulate__0.10.0__swap_comparison____init___L2591 | tabulate/__init__.py | _align_cell_veritically | swap_comparison | 76 | test/test_internal.py::test_align_cell_veritically_top_single_text_multiple_pad | 280 | 3 |
| live__tabulate__0.10.0__swap_operator____init___L2592 | tabulate/__init__.py | _align_cell_veritically | swap_operator | 4 | test/test_internal.py::test_align_cell_veritically_one_line_only | 280 | 3 |
| live__tabulate__0.10.0__swap_comparison____init___L2593 | tabulate/__init__.py | _align_cell_veritically | swap_comparison | 22 | test/test_internal.py::test_align_cell_veritically_top_single_text_multiple_pad | 280 | 8 |
| live__tabulate__0.10.0__off_by_one____init___L2594 | tabulate/__init__.py | _align_cell_veritically | off_by_one | 2 | test/test_internal.py::test_align_cell_veritically_center_single_text_multiple_pad | 280 | 2 |
| live__toolz__1.1.0__invert_boolean___signatures_L675 | toolz/_signatures.py | check_valid | invert_boolean | 2 | toolz/tests/test_curried.py::test_reduce | 180 | 1 |
| live__toolz__1.1.0__swap_comparison__dicttoolz_L33 | toolz/dicttoolz.py | merge | swap_comparison | 4 | toolz/tests/test_dicttoolz.py::TestDict::test_merge_iterable_arg | 180 | 2 |
| live__toolz__1.1.0__swap_comparison__functoolz_L880 | toolz/functoolz.py | has_varargs | swap_comparison | 9 | toolz/tests/test_functoolz.py::test_memoize_key_signature | 180 | 2 |
| live__toolz__1.1.0__swap_comparison__itertoolz_L309 | toolz/itertoolz.py | isdistinct | swap_comparison | 1 | toolz/tests/test_itertoolz.py::test_isdistinct | 180 | 2 |
| live__toolz__1.1.0__off_by_one__recipes_L46 | toolz/recipes.py | partitionby | off_by_one | 1 | toolz/tests/test_recipes.py::test_partitionby | 180 | 1 |
| live__toolz__1.1.0__invert_boolean__utils_L4 | toolz/utils.py | raises | invert_boolean | 1 | toolz/tests/test_utils.py::test_raises | 180 | 2 |
| live__validators__0.35.0__swap_comparison__between_L79 | src/validators/between.py | between | swap_comparison | 34 | tests/test_between.py::test_returns_true_on_valid_range[12-11-13] | 878 | 2 |
| live__validators__0.35.0__swap_comparison__card_L38 | src/validators/card.py | card_number | swap_comparison | 47 | tests/test_card.py::test_returns_true_on_valid_card_number[4242424242424242] | 878 | 3 |
| live__validators__0.35.0__swap_comparison__country_L263 | src/validators/country.py | calling_code | swap_comparison | 22 | tests/test_country.py::test_returns_true_on_valid_calling_code[+1] | 878 | 2 |
| live__validators__0.35.0__swap_boolean__domain_L86 | src/validators/domain.py | domain | swap_boolean | 84 | tests/test_domain.py::test_returns_failed_validation_on_invalid_domain[example.com/.-True-False] | 878 | 3 |
| live__validators__0.35.0__swap_comparison__fi_L63 | src/validators/i18n/fi.py | fi_business_id | swap_comparison | 22 | tests/i18n/test_fi.py::test_returns_true_on_valid_business_id[2336509-6] | 878 | 4 |
| live__validators__0.35.0__swap_boolean__ip_address_L91 | src/validators/ip_address.py | ipv4 | swap_boolean | 25 | tests/test_ip_address.py::test_returns_failed_validation_on_invalid_private_ipv4_address[1.1.1.1-True] | 878 | 3 |

## 7. Packages tried and dropped — reported honestly

Ten candidates were downloaded and inspected. Two were dropped before any task was built:

| package | version | why it was dropped |
| --- | --- | --- |
| `sortedcontainers` | 2.4.0 | **Ships no test suite at all.** The sdist contains only the package plus `setup.py`/`setup.cfg`/`README.rst`; there is no `tests/` directory. The brief prefers the vendor's own suite over hand-written tests as the primary verifier, so this package cannot provide a verifier and was dropped. (Its sources sit in `.zip`-form only for the record; no tasks reference it.) |
| `python-slugify` | 9.0.0 | **No pytest suite.** The sdist ships a single `test.py` script (unittest-style module run directly) plus `test_release.py`, which shells out to release tooling. Driving it would have meant writing the verifier myself, which the brief rules out as a primary verifier. |

Two further caveats about the packages that *were* kept, because they affect how many
independent localisation instances the suite really has:

* `tabulate` has a **single implementation module** (`tabulate/__init__.py`, 2 600+ lines).
  All six of its tasks therefore sit in the same file. They differ in mutation kind and in
  line (2589–2594, all inside `_align_cell_veritically`), but they are **not** six
  independent file-localisation problems — for a per-task file-level localisation measure
  they should be treated as one file, and they are best used as fix-difficulty variants.
* `inflect` (1 file used out of 7) is a single-module case for the same reason.
  `more-itertools` uses 2 files, `furl` 2, `humanize` 5, `toolz` 6, `boltons` 6 and
  `validators` 6 — those provide genuinely spread-out file localisation. Across the whole
  suite, **29 distinct source files** carry the 48 tasks.

## 8. Known limitations

1. **One pre-existing boltons failure** (`tests/test_jsonutils.py::test_reverse_iter_lines`)
   is environment-specific and unrelated to any injected bug; it is recorded and ignored.
   A run harness that requires a fully green baseline must either pin a different boltons
   version or accept the same exclusion.
2. **17 pre-existing validators failures** in `crypto_addresses/test_eth_address.py` are due
   to a deliberately uninstalled optional extra. Installing `eth-hash[pycryptodome]` would
   clear them; the suite was built without it so the environment stays pure-Python and fast.
3. **Mutation families are not uniformly represented.** The shipped 48 are dominated by
   `swap_comparison` (28), then `invert_boolean` (10), `swap_operator` (3),
   `wrong_variable`/`swap_boolean`/`off_by_one` (2 each) and `wrap_return` (1). This is a
   property of the data, not of the generator: mutations that vendor test suites actually
   detect are overwhelmingly predicate flips. `wrong_variable` in particular is usually
   caught only when the substitute name is behaviourally different, and it frequently
   raises `NameError` instead of failing an assertion — such candidates were rejected.
4. **`python_bin` is machine-specific.** It records the interpreter used here
   (`D:\Devs\temp\live_build\venv\Scripts\python.exe`) so the evidence is reproducible on
   this machine; a runner should substitute its own environment's interpreter, which is
   exactly what `test_command` invites.
5. **Timings are wall-clock on this machine** (median buggy run ≈ 8.8 s; slowest
   `more-itertools` task ≈ 42 s). They are indicative, not contractual.
6. **The `lost` condition removes the hint, not the test file.** The vendor suite is the
   verifier, so the failing test's node id is visible to the agent in both conditions.
   The manipulation is the *statement*, i.e. whether the agent is told the file and
   function up front. Condition strength can be increased by also trimming
   `n_source_files` or hiding the test tree, but that would change the repo and break the
   "same repo in both conditions" invariant.
7. **The failing test's file is not always the buggy module.** In 21 of 48 tasks the first
   failing node id names a different module from `gold_file` (e.g.
   `humanize` `src/humanize/number.py` → `tests/test_i18n.py::test_intcomma`;
   `furl` `furl/omdict1D.py` → `tests/test_furl.py::TestQuery::test_add`). This is a
   property of the projects' test layout, and it matters for the study: a traceback
   pointed at `tests/test_*.py` localises the *symptom*, not the defect, so a monitor that
   measures "edits aimed at the file in the final patch" must not treat the failing test
   file as the gold localisation target.
8. **`wrong_variable` and `wrap_return` tasks can fail loudly rather than subtly.** Some
   substitutions raise `TypeError`/`NameError` in the first calling test instead of
   tripping an assertion (e.g. `toolz` `merge` → 4 `TypeError`s). They are genuine
   fail-before/pass-after instances and the failure class is recorded in `bug_description`
   and `failing_tests`, but they are not a subtle mis-computation.

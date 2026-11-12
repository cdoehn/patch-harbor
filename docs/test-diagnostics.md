# Local measurements and Actions summaries

`python tools/profile_tests.py run --modes baseline -- tests/test_selected.py`
explicitly starts local collection; no test selection is inferred. Add
`--modes baseline,cprofile,memory,strace` only for diagnostics you want to collect.
The default worker policy is `auto`. Use `report --phase setup`, `report --phase
call` and `report --phase teardown` to inspect preparation, test execution and
cleanup independently. `--format json`, `text` and `markdown` select local
output. Data and raw artifacts stay beside the local SQLite file; `report` and
`compare` are read-only. See the [measurement contract](../planning/2.0.0/test-profiling.md).

## Full-suite profiling and capacity

From a checkout with the development dependencies installed, run all tests and
the explicitly selected profilers locally:

```bash
python tools/profile_tests.py run --modes baseline,cprofile,memory,strace -- tests
```

`strace` requires Linux and a separately installed strace with `--kill-on-exit`.
Omit that mode on other systems. The worker policy remains `auto`, without an
additional worker cap. Baseline defaults to five repetitions; instrumented
modes use one each, plus one warmup per mode. Each measurement has its own
budget; warmups and repetitions do not share one total allowance.

The defaults include **at least ten times the estimated full-run demand**. The
planning envelope is 5,000 tests with three phases, up to 256 worker startups
for sizing only, and subprocess-heavy profiling. This is a conservative capacity
estimate, not a completed Elitedesk profiling measurement. The last accepted
unprofiled run had 3,968 collected tests, 11,890 phase events, 20,121 fixture
events and a 32,385,431-byte report. A cProfile phase adds both JSON and raw
pstats files, so the former 4,096-file allowance could not fit that full suite.

| Capacity per measurement | Estimated demand | Default limit |
| --- | ---: | ---: |
| Instrumented child runtime | 12 hours | 120 hours |
| Raw artifacts in total | 32 GiB | 320 GiB |
| Artifact files, including subprocess traces | 150,000 | 1,500,000 |
| Test report | 64 MiB | 640 MiB |
| Collector phase/startup records | 20,000 | 200,000 |
| One collector record | 4 MiB | 40 MiB |
| Functions in one record | 10,000 | 100,000 |
| Callers for one function | 10,000 | 100,000 |
| Python function and caller rows combined | 15,000,000 | 150,000,000 |
| Raw strace events | 100,000,000 | 1,000,000,000 |
| Normalized strace/process rows | 1,000,000 | 10,000,000 |

These limits do not reserve RAM or disk space. Raw files and the SQLite database
still require actual free disk space; the artifact allowance does not include
the database. Python records import one at a time within a transaction, and
strace phase lookup uses an index built once per measurement. Existing identity,
schema, path, completeness and parser validations remain in force. Source-file
inventory and test/fixture telemetry limits already exceed tenfold demand for
this envelope. Display rankings and explicitly truncated memory differences
are presentation choices, not limits that abort collection.

Increase all default capacities together, including importer limits:

```bash
python tools/profile_tests.py run --budget-scale 2 --modes baseline,cprofile,memory,strace -- tests
```

`--timeout SECONDS`, `--max-bytes BYTES` and `--max-files COUNT` override their
individual values and are not multiplied by `--budget-scale`. The old 4 GiB
maximum for `--max-bytes` is removed. Explicit small limits remain available for
short investigations. Effective budgets are stored in local run metadata and
measurement details. Budget failures include the observed value, the limit and
the option that raises it; the measurement remains partial and keeps its actual
test exit code. Inspect details with:

```bash
python tools/profile_tests.py report --run latest --format json
```

## Actions summaries

Actions summaries read only the JSON reports already produced by each existing
acceptance lane. They run after its artifact upload, even after test failure
when the runner can still execute the summary step. A renderer failure is
reported but cannot override the test, artifact or release gates. The strict
validators remain authoritative. There is no profiling job or profiling upload.

The workflow uses the summary command with `--best-effort`. Recognized report
and output errors are logged by that command without altering previous step
results or report files. Direct calls without the option retain a nonzero
error status, and invalid arguments remain errors in either mode. No workflow
job or step uses `continue-on-error`.

Counts refer to one test execution per suite, including setup/teardown failures;
they are not three successes for three phases. Subtest failures affect their
parent case. Collection failures, xfail/xpass, actual pytest skips, unexecuted
cases and incomplete evidence remain distinct. Suite selections can overlap;
suites are never summed into a misleading unique-test total.

Each summary shows the full dispatch commit, run/attempt, catalog lane, observed
Python/platform, shell and artifact link if upload succeeded. A test report is
commit-bound only when its binding matches the audited build report for the
same full commit. Missing or foreign evidence cannot produce a bound success.

Timing uses the existing controller observation, not a sum of parallel workers.
The entire job duration is unmeasured. The ten slowest call phases retain
separate setup and teardown columns. Missing timing stays unknown, and startup
and collection hints describe only their actual measurement scope.

The renderer uses the standard library and limits input bytes, event counts and
output size. Normal test reports remain the downloadable evidence.
Implementation references: [GitHub job summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary)
and [artifact outputs](https://github.com/actions/upload-artifact#outputs).

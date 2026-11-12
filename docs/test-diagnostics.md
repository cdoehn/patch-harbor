# Local measurements and Actions summaries

`python tools/profile_tests.py run --modes baseline -- tests/test_selected.py`
explicitly starts local collection; no test selection is inferred. Add
`--modes baseline,cprofile,memory,strace` only for diagnostics you want to collect.
The default worker policy is `auto`. Use `report --phase setup`, `report --phase
call` and `report --phase teardown` to inspect preparation, test execution and
cleanup independently. `--format json`, `text` and `markdown` select local
output. Data and raw artifacts stay beside the local SQLite file; `report` and
`compare` are read-only. See the [measurement contract](../planning/2.0.0/test-profiling.md).

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

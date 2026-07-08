# PatchHarbor.05 patch-script linting acceptance

PatchHarbor.05 establishes a generic patch-script linting foundation in the target repository.

The phase is intentionally limited to reusable linting pieces. It does not integrate linting into the download patch runner, local shell aliases, automatic patch execution, or source-repository compatibility wrappers.

## Accepted scope

PatchHarbor.05 is accepted when the target repository contains:

- patch-linting migration inventory documentation
- a generic patch-lint finding and result model
- focused tests for the model
- a heredoc-aware shell text scanner
- focused tests for the scanner
- first generic patch-lint rules
- focused tests for those rules
- a public text and file lint API
- focused tests for that API
- a small CLI subcommand for explicit manual linting
- focused tests for the CLI behavior

## Current target components

| Component | Path |
| --- | --- |
| migration inventory | `docs/patch-linting-migration.md` |
| finding/result model | `src/patchharbor/patch_lint.py` |
| model tests | `tests/test_patch_lint.py` |
| shell scanner | `src/patchharbor/shell_scan.py` |
| scanner tests | `tests/test_shell_scan.py` |
| generic lint rules | `src/patchharbor/patch_lint_rules.py` |
| rule tests | `tests/test_patch_lint_rules.py` |
| public lint API | `src/patchharbor/patch_lint_api.py` |
| API tests | `tests/test_patch_lint_api.py` |
| CLI entry | `src/patchharbor/cli.py` |
| CLI tests | `tests/test_cli_patch_lint.py` |

## Accepted behavior

The lint foundation can detect plain pager-prone git diff and git log commands while ignoring safe git --no-pager and GIT_PAGER=cat usage.

The git pager rule handles simple shell command forms after control words and separators, and it checks multiple commands on the same line independently.

The lint foundation can detect missing patch footer contracts, missing syntax or test execution markers, and literal Markdown fence sequences.

The shell scanner skips heredoc payload text so generated file contents do not create self-referential false positives.

The public API can lint patch text, single files, and multiple files. It returns structured findings and stable rendered status lines.

The CLI command `patchharbor lint-script <file>` is available for explicit manual checks. It exits with 0 when no findings are present, 1 when findings are present, and 2 when the file cannot be read or linting cannot run.

## Explicit non-goals

PatchHarbor.05 does not integrate linting into:

- the download patch runner
- the `c` workflow
- automatic patch execution
- source-repository wrappers
- compatibility aliases
- source-repository commits

Those belong to later phases after compatibility boundaries are planned.

## Boundary

RepoDossier remains unchanged during this phase.

PatchHarbor now owns the reusable linting foundation. Source-repository integration must be introduced later through explicit wrapper or runner migration patches, not by silently changing the source repository here.

# PatchHarbor patch-script linting migration inventory

PatchHarbor.05 starts the migration of patch-script linting from source-repository-specific development tooling into generic PatchHarbor components.

This step is inventory-only.

No linter source code, rule implementation, CLI command, runner behavior, or source-repository wrapper is copied in this patch.

## Source-side candidates

| Source file | Future PatchHarbor role | Migration note |
| --- | --- | --- |
| `scripts/dev/lint_patch_script.py` | linter source | Extract generic finding model, heredoc-aware shell scanning, and repository-agnostic rules incrementally. |
| `tests/test_lint_patch_script.py` | regression tests | Rebuild as target-side tests with neutral fixtures and no source-repository assumptions. |
| `scripts/dev/patch-rules.md` | human contract | Use as behavioral reference only; do not copy project-specific wording blindly. |
| `scripts/dev/run_latest_download_patch.sh` | linter consumer | Keep runner integration later; it depends on stable metadata, workflow rules, and lint APIs. |
| `scripts/dev/repo_patch_helper.py` | helper source | Reuse only generic concepts after they are isolated and tested. |

## Current source behavior to preserve carefully

The migration should preserve the useful generic checks without importing source-project assumptions:

- warn about plain `git diff` or `git log` commands that can open a pager
- warn when a patch script lacks an explicit footer/status summary
- warn when a patch script appears to omit syntax or test execution
- warn about literal Markdown fence sequences inside generated patch scripts
- scan shell code outside heredocs without being confused by heredoc payload text

## Target-side phases

1. Inventory and boundary documentation.
2. Generic patch-lint finding model.
3. Heredoc-aware shell text scanner.
4. First generic lint rules.
5. Patch lint API for text and files.
6. Small CLI subcommand.
7. Acceptance documentation after the linter foundation is proven.

## Boundaries

PatchHarbor patch linting must stay repository-agnostic.

RepoDossier-specific file names may appear only as source inventory references during migration. Generic lint APIs must not require local shell aliases, private paths, private email addresses, workstation names, or a specific contributor environment.

The existing source runner should remain unchanged until PatchHarbor linting is tested and compatibility wrappers are planned.

## Non-goals for this step

- no linter code copy
- no lint rule implementation
- no shell scanner implementation
- no CLI command
- no runner integration
- no source repository changes

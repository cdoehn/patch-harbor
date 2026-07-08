# PatchHarbor runner and compatibility migration inventory

PatchHarbor.06 starts the migration of runner behavior and source-repository compatibility boundaries.

This step is inventory-only.

No runner source code, alias behavior, automatic patch execution, download-folder mutation, source-repository wrapper, or source-repository commit is introduced in this patch.

## Source-side candidates

| Source file | Future PatchHarbor role | Migration note |
| --- | --- | --- |
| `scripts/dev/run_latest_download_patch.sh` | runner workflow reference | Extract generic preflight, freshness, repeat detection, execution, logging, and done/failed lifecycle in later patches. |
| `scripts/dev/repo_patch_helper.py` | helper behavior reference | Identify reusable runner/status concepts before copying implementation details. |
| `scripts/dev/install_aliases.sh` | compatibility and alias reference | Keep source-repository alias wiring out of the generic runner until wrappers are explicit. |
| `scripts/dev/show_progress_context.py` | context and milestone display source | Treat context, milestone, progress, and footer display as PatchHarbor functionality to migrate. |
| `scripts/dev/validate_patch_metadata.py` | metadata preflight source | Reconcile with the target metadata parser before runner integration. |
| `scripts/dev/validate_patch_workflow_rules.py` | workflow-rules preflight source | Reconcile with target workflow-rules API before runner integration. |
| `scripts/dev/lint_patch_script.py` | linter preflight source | Replace with the target patch-lint API when runner migration reaches lint integration. |
| `scripts/dev/patch-rules.md` | human workflow contract | Use as behavior reference without copying source-specific wording blindly. |

## Runner behavior to inventory before extraction

The current runner workflow contains several responsibilities that must be split before migration:

- selecting the newest downloaded patch script
- validating patch metadata comments
- detecting repeated successful patch application
- checking script freshness
- running Bash syntax checks
- invoking the patch script
- writing a persistent log
- moving successful scripts to a done folder
- moving failed scripts to a failed folder
- reporting exit code and status
- keeping destructive behavior out of generic APIs until lifecycle rules are explicit

## Context and milestone display belongs to PatchHarbor

The context display is not just a source-repository convenience. PatchHarbor must own the generic form of:

- patch footer status sections
- current and next-step display
- done/current/next/problem colors
- milestone and roadmap labels from patch metadata
- side-by-side or contextual display hints
- concise failure guidance that says to repair the current patch before continuing
- progress context used by the patch runner output

The future generic runner should therefore separate execution status from display rendering, but both belong inside PatchHarbor.

## Compatibility boundary

PatchHarbor should provide generic runner and display primitives.

Source repositories should later keep only thin wrappers or configuration for:

- local command aliases
- repository-specific paths
- compatibility command names
- migration-era defaults
- source-specific safety policy additions

The source repository must not be silently changed during this inventory step.

## Proposed target-side phases

1. Runner and compatibility migration inventory.
2. Generic runner result and status model.
3. Preflight APIs for metadata, freshness, and repeat checks.
4. Download-file discovery and lifecycle planning.
5. Runner core that can execute an explicit script path.
6. Context and milestone display renderer.
7. Optional CLI command for explicit runner use.
8. Acceptance documentation before source-repository wrappers are touched.

## Non-goals for this step

- no runner code copy
- no download-folder mutation
- no alias installation
- no automatic script execution
- no source-repository wrapper changes
- no replacement of the current source runner

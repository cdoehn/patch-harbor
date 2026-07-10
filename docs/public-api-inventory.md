# PATCHHARBOR.15c1 – Public API inventory

This document records the PatchHarbor public API surface before PATCHHARBOR.15c2 adds stability tests.

The inventory is target-only. It does not edit RepoDossier, source wrappers, aliases, shell rc files, or PatchHarbor runtime code.

## API categories

PatchHarbor has two supported public API categories:

| Category | Surface | Stability level |
| --- | --- | --- |
| command-line API | `patchharbor` console command and subcommands | public contract |
| Python API | documented functions and dataclasses in selected modules | public or compatibility contract |

Internal modules and helper functions may exist, but they are not stable public API unless they are listed in this inventory.

## Command-line public API

The public command-line API is:

| Command | API status | Purpose |
| --- | --- | --- |
| `patchharbor --help` | public | show top-level help |
| `patchharbor --version` | public | show package version |
| `patchharbor doctor --repo` | public | check repository and environment assumptions |
| `patchharbor lint-script` | public | lint a patch script without executing it |
| `patchharbor run-script` | public | run a patch script through PatchHarbor runner behavior |
| `patchharbor audit-public` | public | audit files for private/local values |
| `patchharbor check-env` | public | check local development environment assumptions |

The command-line API is documented in:

    docs/cli.md

## Python public API: CLI

Module:

    patchharbor.cli

Public objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `build_parser` | public | create the CLI argument parser |
| `main` | public | command-line entry point callable |

## Python public API: patch linting

Module:

    patchharbor.patch_lint_api

Public objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `default_patch_lint_rules` | public | return default lint rules |
| `lint_patch_text` | public | lint script text |
| `lint_patch_file` | public | lint one patch script file |
| `lint_patch_files` | public | lint multiple patch script files |
| `render_patch_lint_result` | public | render lint result for CLI/user output |
| `patch_lint_rule_names` | public | list known patch-lint rule names |

## Python public API: runner core

Module:

    patchharbor.runner_core

Public objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `RunnerCoreError` | public | runner exception type |
| `RunnerExecutionConfig` | public | runner execution configuration |
| `check_bash_syntax` | public | check Bash syntax for a script |
| `lint_script_for_runner` | public | run lint preflight for runner usage |
| `execute_patch_script` | public | execute a patch script |
| `run_patch_script` | public | run the full patch-script lifecycle |

Runner behavior is documented in:

    docs/runner.md

## Python public API: workflow rules

Module:

    patchharbor.workflow_rules

Public objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `WorkflowRulesError` | public | workflow-rule parsing exception |
| `WorkflowRule` | public | workflow-rule model |
| `WorkflowRuleSet` | public | workflow-rule collection model |
| `load_rules_from_text` | public | parse workflow rules from text |
| `rules_by_category` | public | group rules by category |

Module:

    patchharbor.workflow_validation

Public objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `WorkflowRuleIssue` | public | workflow-rule validation issue |
| `WorkflowRulesValidationResult` | public | workflow-rule validation result |
| `validate_workflow_rules_text` | public | validate workflow rules from text |
| `validate_workflow_rules_mapping` | public | validate workflow rules from a mapping |
| `validate_workflow_rules_file` | public | validate workflow rules from a file |
| `summarize_validation_result` | public | summarize validation results |
| `issues_with_severity` | public | filter issues by severity |

## Python compatibility API

These modules are public compatibility surfaces because source-adoption and public-readiness docs refer to them.

Module:

    patchharbor.compat_config

Public compatibility objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `CompatibilityConfigError` | compatibility public | compatibility config exception |
| `AliasSpec` | compatibility public | alias compatibility model |
| `WrapperSpec` | compatibility public | wrapper compatibility model |
| `LifecycleDefaults` | compatibility public | lifecycle defaults model |
| `CompatibilityConfig` | compatibility public | compatibility config model |
| `compatibility_config_from_mapping` | compatibility public | parse config from mapping |
| `compatibility_config_from_text` | compatibility public | parse config from text |
| `minimal_compatibility_config` | compatibility public | build minimal config |

Module:

    patchharbor.public_audit

Public compatibility objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `PublicAuditModelError` | compatibility public | public-audit model exception |
| `PublicAuditPattern` | compatibility public | audit pattern model |
| `PublicAuditTarget` | compatibility public | audit target model |
| `PublicAuditFinding` | compatibility public | audit finding model |
| `PublicAuditResult` | compatibility public | audit result model |
| `public_audit_pattern_from_mapping` | compatibility public | parse one pattern |
| `public_audit_patterns_from_mappings` | compatibility public | parse many patterns |
| `public_audit_pattern_index` | compatibility public | index patterns by name |

Module:

    patchharbor.environment_check

Public compatibility objects:

| Object | API status | Purpose |
| --- | --- | --- |
| `EnvironmentCheckError` | compatibility public | environment-check exception |
| `EnvironmentCheck` | compatibility public | one check result |
| `EnvironmentCheckSpec` | compatibility public | one check specification |
| `EnvironmentCheckResult` | compatibility public | full check result |
| `environment_check_from_mapping` | compatibility public | parse one check from mapping |
| `environment_check_spec_from_mapping` | compatibility public | parse one spec from mapping |
| `environment_check_result_from_mappings` | compatibility public | parse a full result |

Compatibility behavior is documented in:

    docs/compatibility.md

## Non-public implementation modules

The following modules are implementation details unless a later patch explicitly promotes them into this inventory:

- `patchharbor.console`
- `patchharbor.download_plan`
- `patchharbor.download_selection`
- `patchharbor.export_display`
- `patchharbor.export_model`
- `patchharbor.export_planning`
- `patchharbor.metadata`
- `patchharbor.patch_lint`
- `patchharbor.patch_lint_rules`
- `patchharbor.public_audit_checks`
- `patchharbor.runner_display`
- `patchharbor.runner_lifecycle`
- `patchharbor.runner_preflight`
- `patchharbor.runner_status`
- `patchharbor.shell_scan`

These modules can still be tested internally. They are just not promised as stable public API by PATCHHARBOR.15c1.

## Stability rules for PATCHHARBOR.15c2

The next patch should add stability tests that prove:

1. all listed public modules import successfully
2. all listed public objects exist
3. public dataclasses remain dataclasses where documented as models
4. command-line public commands remain present in help output
5. public lint API functions remain callable
6. public runner API configuration remains constructible
7. public compatibility models remain constructible
8. target-only public API tests leave RepoDossier unchanged
9. private/local values are not introduced into public docs
10. literal Markdown fences are not introduced into new public API docs

## Non-goals

PATCHHARBOR.15c1 does not:

- change runtime code
- add stability tests beyond this inventory test
- change CLI behavior
- change runner behavior
- change compatibility behavior
- edit RepoDossier
- edit source wrappers
- edit aliases
- change package metadata

PATCHHARBOR.15c2 adds public API stability tests.

PATCHHARBOR.15c3 adds final public readiness acceptance.


## PATCHHARBOR.15c2 applied

- Public API stability tests now live in `tests/test_public_api_stability.py`.
- The tests import every public module listed in this inventory.
- The tests assert every listed public object exists.
- The tests assert documented public dataclass models remain dataclasses.
- The tests assert public CLI commands remain available in parser and help output.
- The tests exercise representative lint, runner, workflow, and compatibility public APIs.


## PATCHHARBOR.15c3 applied

- Public readiness acceptance now lives in `docs/public-readiness-acceptance.md` and closes the 15c public API/readiness series.


## PATCHHARBOR.16a1 applied

- Dual repo discovery smoke now lives in `docs/dual-repo-discovery-smoke.md` and is tested by `tests/test_dual_repo_discovery_smoke.py`; public API stability remains covered by `tests/test_public_api_stability.py`.


## PATCHHARBOR.16a2 applied

- Dual repo patch-runner smoke now lives in `docs/dual-repo-patch-runner-smoke.md` and is tested by `tests/test_dual_repo_patch_runner_smoke.py`; public API stability remains covered by `tests/test_public_api_stability.py`.

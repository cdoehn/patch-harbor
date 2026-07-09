# PatchHarbor.07 source-wrapper compatibility acceptance

PatchHarbor.07 establishes the generic source-wrapper compatibility foundation in the target repository.

This phase is intentionally limited to configuration, planning, rendering, documentation, and tests. It does not adopt wrappers into any source repository and it does not install local shell aliases.

## Accepted scope

PatchHarbor.07 is accepted when the target repository contains:

- source-wrapper compatibility migration inventory documentation
- a generic compatibility configuration model
- a compatibility wrapper planning API
- a compatibility wrapper rendering API
- acceptance documentation and tests for the wrapper compatibility boundary

## Current target components

| Component | Path |
| --- | --- |
| migration inventory | `docs/source-wrapper-compatibility-migration.md` |
| configuration model | `src/patchharbor/compat_config.py` |
| planning API | `src/patchharbor/compat_planning.py` |
| rendering API | `src/patchharbor/compat_rendering.py` |
| configuration tests | `tests/test_compat_config.py` |
| planning tests | `tests/test_compat_planning.py` |
| rendering tests | `tests/test_compat_rendering.py` |
| acceptance tests | `tests/test_source_wrapper_compatibility_acceptance.py` |

## Accepted behavior

The configuration model can represent source-specific wrapper specs, aliases, lifecycle directory names, environment values, and metadata as plain data.

The planning API can produce actions such as lifecycle checks, wrapper creation plans, wrapper update plans, disabled-wrapper skips, alias creation plans, and alias update plans. Planning does not write files, create directories, install aliases, or mutate a source repository.

The rendering API can render wrapper script text, alias lines, plan previews, action previews, and compatibility summaries. Rendering returns strings and plain data only. It does not create wrapper files or edit shell configuration.

The acceptance tests prove that the model, planner, and renderer work together while keeping all source-repository adoption out of scope.

## Explicit non-goals

PatchHarbor.07 does not introduce:

- source-repository wrapper file writes
- automatic wrapper adoption
- alias installation
- shell rc-file edits
- download-folder mutation
- export runner migration
- replacement of existing source runners
- source-repository commits
- local machine path defaults
- private contributor assumptions

Those belong to later adoption phases after the generic target-side contracts are stable.

## Compatibility boundary

PatchHarbor now owns generic wrapper configuration, planning, and rendering primitives.

Source repositories can later decide which rendered wrappers they want to adopt. That adoption must be explicit, tested, and scoped to the source repository.

The generic target modules should continue to avoid source-specific runner names, contributor home directories, workstation names, private addresses, and local alias assumptions.

## Acceptance checks

The phase is accepted when the target repository passes:

    python3 -m compileall src tests
    PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
    PYTHONPATH=src python3 -m patchharbor doctor --repo .

Manual smoke checks can create a compatibility configuration in memory, plan actions, and render wrapper text. These checks should not write source wrapper files.

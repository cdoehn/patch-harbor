from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from patchharbor.resource_policy import (
    DEFAULT_RESOURCE_POLICY,
    ResourcePolicy,
)


def test_default_resource_policy_contains_the_version_one_budgets() -> None:
    assert DEFAULT_RESOURCE_POLICY == ResourcePolicy(
        warning_bytes=10 * 1024 * 1024,
        max_input_artifact_bytes=256 * 1024 * 1024,
        max_content_bytes=256 * 1024 * 1024,
        max_zip_total_bytes=512 * 1024 * 1024,
        max_zip_entries=1_000,
    )


def test_resource_policy_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        DEFAULT_RESOURCE_POLICY.warning_bytes = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"warning_bytes": 0},
        {"max_input_artifact_bytes": -1},
        {"max_content_bytes": -1},
        {"max_zip_total_bytes": 0},
        {"max_zip_entries": False},
        {"warning_bytes": 3, "max_input_artifact_bytes": 2},
        {"warning_bytes": 3, "max_content_bytes": 2},
    ],
)
def test_resource_policy_rejects_invalid_limits(
    overrides: dict[str, int | bool],
) -> None:
    values: dict[str, int | bool] = {
        "warning_bytes": 1,
        "max_input_artifact_bytes": 10,
        "max_content_bytes": 10,
        "max_zip_total_bytes": 20,
        "max_zip_entries": 4,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        ResourcePolicy(**values)  # type: ignore[arg-type]

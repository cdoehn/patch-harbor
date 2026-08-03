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
        read_chunk_bytes=64 * 1024,
    )


def test_resource_policy_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        DEFAULT_RESOURCE_POLICY.warning_bytes = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("warning_bytes", 0),
        ("max_input_artifact_bytes", -1),
        ("max_content_bytes", -1),
        ("max_zip_total_bytes", 0),
        ("max_zip_entries", 0),
        ("read_chunk_bytes", False),
    ],
)
def test_resource_policy_rejects_non_positive_values(
    field: str,
    value: int | bool,
) -> None:
    values = {
        "warning_bytes": 1,
        "max_input_artifact_bytes": 2,
        "max_content_bytes": 2,
        "max_zip_total_bytes": 3,
        "max_zip_entries": 4,
        "read_chunk_bytes": 5,
    }
    values[field] = value

    with pytest.raises(ValueError, match=f"{field} must be a positive integer"):
        ResourcePolicy(**values)


def test_resource_policy_rejects_warning_above_input_artifact_limit() -> None:
    with pytest.raises(
        ValueError,
        match="warning_bytes must not exceed max_input_artifact_bytes",
    ):
        ResourcePolicy(
            warning_bytes=3,
            max_input_artifact_bytes=2,
            max_content_bytes=10,
            max_zip_total_bytes=20,
        )


def test_resource_policy_rejects_warning_above_single_content_limit() -> None:
    with pytest.raises(
        ValueError,
        match="warning_bytes must not exceed max_content_bytes",
    ):
        ResourcePolicy(
            warning_bytes=3,
            max_content_bytes=2,
            max_zip_total_bytes=10,
        )


def test_resource_policy_returns_only_needed_warning_metric() -> None:
    policy = ResourcePolicy(
        warning_bytes=3,
        max_content_bytes=10,
        max_zip_total_bytes=20,
    )

    assert policy.large_content_warning("payload", 3) is None
    assert policy.large_content_warning("payload", 4) == (
        "payload is large (4 bytes)"
    )

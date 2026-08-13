from __future__ import annotations

import pytest

from patchharbor.bundle_paths import (
    BundlePathError,
    is_safe_bundle_path,
    normalize_bundle_path,
    validate_bundle_member_paths,
)


@pytest.mark.parametrize(
    "path",
    (
        "payload.bin",
        "assets/payload.bin",
        "A-1/.config_2/file.data",
    ),
)
def test_safe_bundle_paths_are_portable(path: str) -> None:
    assert is_safe_bundle_path(path)
    assert normalize_bundle_path(path) == path


@pytest.mark.parametrize(
    "path",
    (
        "",
        "/absolute.bin",
        "../escape.bin",
        "folder/../escape.bin",
        "folder/./payload.bin",
        r"folder\payload.bin",
        "C:/payload.bin",
        "CON/payload.bin",
        "folder/NUL.txt",
        "folder//payload.bin",
        ".git/config",
        "files/.PATCHHARBOR/id",
        f"{'a' * 129}/payload.bin",
        "a/" + "b" * 511,
    ),
)
def test_unsafe_bundle_paths_are_rejected(path: str) -> None:
    assert not is_safe_bundle_path(path)
    with pytest.raises(BundlePathError):
        normalize_bundle_path(path)


def test_explicit_directory_and_children_form_one_valid_tree() -> None:
    assert validate_bundle_member_paths(
        (
            ("assets/", True),
            ("assets/one.bin", False),
            ("assets/nested/two.bin", False),
        )
    ) == (
        "assets",
        "assets/one.bin",
        "assets/nested/two.bin",
    )


@pytest.mark.parametrize(
    "members",
    (
        (("same.bin", False), ("same.bin", False)),
        (("Same.bin", False), ("same.bin", False)),
        (("Assets/one.bin", False), ("assets/two.bin", False)),
        (("assets", False), ("assets/two.bin", False)),
        (("assets/", True), ("assets", False)),
    ),
)
def test_duplicate_case_colliding_and_conflicting_trees_are_rejected(
    members: tuple[tuple[str, bool], tuple[str, bool]],
) -> None:
    with pytest.raises(BundlePathError):
        validate_bundle_member_paths(members)


@pytest.mark.parametrize(
    "reserved_name",
    (
        "CON",
        "PRN.txt",
        "AUX.log",
        "NUL.data",
        *(f"COM{number}.bin" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    ),
)
def test_windows_reserved_names_are_rejected_in_every_path_segment(
    reserved_name: str,
) -> None:
    for candidate in (reserved_name, f"assets/{reserved_name}"):
        assert not is_safe_bundle_path(candidate)
        with pytest.raises(BundlePathError):
            normalize_bundle_path(candidate)


@pytest.mark.parametrize(
    "path",
    (
        "C:/payload.bin",
        "C:payload.bin",
        "//server/share/payload.bin",
        r"\\server\share\payload.bin",
        "folder/name:stream",
    ),
)
def test_windows_drive_unc_and_stream_path_forms_are_rejected(path: str) -> None:
    assert not is_safe_bundle_path(path)
    with pytest.raises(BundlePathError):
        normalize_bundle_path(path)

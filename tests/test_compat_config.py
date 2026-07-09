from __future__ import annotations

import json
from pathlib import Path
import unittest

from patchharbor.compat_config import (
    AliasSpec,
    CompatibilityConfig,
    CompatibilityConfigError,
    LifecycleDefaults,
    WrapperSpec,
    compatibility_config_from_mapping,
    compatibility_config_from_text,
    minimal_compatibility_config,
)


class PatchHarborCompatibilityConfigTests(unittest.TestCase):
    def test_alias_spec_renders_and_round_trips(self) -> None:
        alias = AliasSpec("run-patch", ("patchharbor", "run-script", "patch.sh"), description="Run a patch")
        self.assertEqual(alias.render_command(), "patchharbor run-script patch.sh")
        self.assertEqual(alias.to_mapping()["command"], ["patchharbor", "run-script", "patch.sh"])
        loaded = AliasSpec.from_mapping(alias.to_mapping())
        self.assertEqual(loaded, alias)

    def test_alias_spec_rejects_invalid_values(self) -> None:
        with self.assertRaises(CompatibilityConfigError):
            AliasSpec("", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            AliasSpec("x", "patchharbor")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityConfigError):
            AliasSpec("x", ())
        with self.assertRaises(CompatibilityConfigError):
            AliasSpec.from_mapping({"name": "x", "command": "patchharbor"})

    def test_wrapper_spec_validates_relative_path_kind_and_command(self) -> None:
        wrapper = WrapperSpec(
            name="patch-runner",
            kind="runner",
            relative_path="scripts/dev/run_patch.sh",
            command=("patchharbor", "run-script"),
            description="Explicit runner wrapper",
        )
        self.assertEqual(wrapper.render_command(), "patchharbor run-script")
        self.assertEqual(wrapper.to_mapping()["relative_path"], "scripts/dev/run_patch.sh")
        self.assertEqual(WrapperSpec.from_mapping(wrapper.to_mapping()), wrapper)

    def test_wrapper_spec_rejects_invalid_values(self) -> None:
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec("x", "unknown", "scripts/x.sh", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec("x", "runner", "/absolute.sh", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec("x", "runner", "../escape.sh", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec("x", "runner", ".git/hooks/x", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec("x", "runner", "scripts/x.sh", "patchharbor")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityConfigError):
            WrapperSpec.from_mapping({"name": "x", "kind": "runner", "relative_path": "scripts/x.sh"})

    def test_lifecycle_defaults_are_stable_and_validate_names(self) -> None:
        lifecycle = LifecycleDefaults()
        self.assertEqual(lifecycle.to_mapping(), {"downloads_dirname": "downloads", "done_dirname": "done", "failed_dirname": "failed"})
        self.assertEqual(LifecycleDefaults.from_mapping({}), lifecycle)
        with self.assertRaises(CompatibilityConfigError):
            LifecycleDefaults(done_dirname="same", failed_dirname="same")
        with self.assertRaises(CompatibilityConfigError):
            LifecycleDefaults(downloads_dirname="../downloads")
        with self.assertRaises(CompatibilityConfigError):
            LifecycleDefaults(done_dirname=".git")

    def test_compatibility_config_groups_wrappers_aliases_lifecycle_and_environment(self) -> None:
        wrapper = WrapperSpec("patch-runner", "runner", "scripts/dev/run_patch.sh", ("patchharbor", "run-script"))
        disabled = WrapperSpec("legacy-export", "export", "scripts/dev/export.sh", ("patchharbor", "export"), enabled=False)
        alias = AliasSpec("run-patch", ("scripts/dev/run_patch.sh",))
        config = CompatibilityConfig(
            source_name="example-project",
            wrappers=(wrapper, disabled),
            aliases=(alias,),
            lifecycle=LifecycleDefaults(downloads_dirname="downloads", done_dirname="done", failed_dirname="failed"),
            environment={"PATCHHARBOR_MODE": "safe"},
            metadata={"owner": "tools"},
        )

        self.assertEqual(config.enabled_wrappers(), (wrapper,))
        self.assertEqual(config.wrappers_by_kind("runner"), (wrapper,))
        self.assertEqual(config.wrapper_by_name("patch-runner"), wrapper)
        self.assertEqual(config.alias_by_name("run-patch"), alias)
        self.assertEqual(config.to_mapping()["source_name"], "example-project")

    def test_compatibility_config_rejects_duplicates_and_bad_collections(self) -> None:
        wrapper = WrapperSpec("same", "runner", "scripts/a.sh", ("patchharbor",))
        duplicate_name = WrapperSpec("same", "export", "scripts/b.sh", ("patchharbor",))
        duplicate_path = WrapperSpec("other", "export", "scripts/a.sh", ("patchharbor",))
        alias = AliasSpec("same", ("patchharbor",))
        with self.assertRaises(CompatibilityConfigError):
            CompatibilityConfig("example-project", wrappers=(wrapper, duplicate_name))
        with self.assertRaises(CompatibilityConfigError):
            CompatibilityConfig("example-project", wrappers=(wrapper, duplicate_path))
        with self.assertRaises(CompatibilityConfigError):
            CompatibilityConfig("example-project", aliases=(alias, alias))
        with self.assertRaises(CompatibilityConfigError):
            CompatibilityConfig("example-project", wrappers=("bad",))  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityConfigError):
            CompatibilityConfig("example-project", environment={"KEY": 1})  # type: ignore[dict-item]

    def test_config_from_mapping_and_text_round_trip(self) -> None:
        mapping = {
            "source_name": "example-project",
            "wrappers": [
                {
                    "name": "patch-runner",
                    "kind": "runner",
                    "relative_path": "scripts/dev/run_patch.sh",
                    "command": ["patchharbor", "run-script"],
                }
            ],
            "aliases": [
                {
                    "name": "run-patch",
                    "command": ["scripts/dev/run_patch.sh"],
                    "description": "Run patch wrapper",
                }
            ],
            "lifecycle": {
                "downloads_dirname": "downloads",
                "done_dirname": "done",
                "failed_dirname": "failed",
            },
            "environment": {"PATCHHARBOR_MODE": "safe"},
            "metadata": {"phase": "compatibility"},
        }
        config = compatibility_config_from_mapping(mapping)
        self.assertEqual(config.source_name, "example-project")
        self.assertEqual(config.wrapper_by_name("patch-runner").kind, "runner")  # type: ignore[union-attr]
        text_config = compatibility_config_from_text(json.dumps(mapping))
        self.assertEqual(text_config.to_mapping(), config.to_mapping())

    def test_config_from_text_rejects_invalid_json_or_non_object(self) -> None:
        with self.assertRaises(CompatibilityConfigError):
            compatibility_config_from_text("{")
        with self.assertRaises(CompatibilityConfigError):
            compatibility_config_from_text("[]")
        with self.assertRaises(CompatibilityConfigError):
            compatibility_config_from_text(123)  # type: ignore[arg-type]

    def test_minimal_config(self) -> None:
        config = minimal_compatibility_config("example-project")
        self.assertEqual(config.source_name, "example-project")
        self.assertEqual(config.wrappers, ())
        self.assertEqual(config.aliases, ())
        self.assertEqual(config.lifecycle, LifecycleDefaults())

    def test_lookup_helpers_validate_names_and_kinds(self) -> None:
        config = minimal_compatibility_config("example-project")
        with self.assertRaises(CompatibilityConfigError):
            config.wrapper_by_name("")
        with self.assertRaises(CompatibilityConfigError):
            config.alias_by_name("")
        with self.assertRaises(CompatibilityConfigError):
            config.wrappers_by_kind("bad")

    def test_compat_config_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/compat_config.py",
            root / "tests/test_compat_config.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
            "run_latest_" + "download_patch",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)

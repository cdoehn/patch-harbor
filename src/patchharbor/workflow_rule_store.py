from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from patchharbor.workflow_rules import (
    DEFAULT_RULESET_VERSION,
    WorkflowRulesError,
    WorkflowRuleSet,
    load_rules_from_text,
)


DEFAULT_WORKFLOW_RULES_PATH = Path("patch-workflow-rules.json")


def load_workflow_rules_file(path: str | Path, *, missing_ok: bool = False) -> WorkflowRuleSet:
    file_path = Path(path).expanduser()
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if missing_ok:
            return WorkflowRuleSet(version=DEFAULT_RULESET_VERSION, source=str(file_path))
        raise WorkflowRulesError(f"workflow rules file does not exist: {file_path}")
    except OSError as exc:
        raise WorkflowRulesError(f"workflow rules file could not be read: {file_path}: {exc}") from exc

    return load_rules_from_text(text, source=str(file_path))


def write_workflow_rules_file(path: str | Path, ruleset: WorkflowRuleSet) -> None:
    file_path = Path(path).expanduser()
    parent = file_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowRulesError(f"workflow rules directory could not be created: {parent}: {exc}") from exc

    text = json.dumps(ruleset.to_mapping(), indent=2, ensure_ascii=False) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, file_path)
    except OSError as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise WorkflowRulesError(f"workflow rules file could not be written: {file_path}: {exc}") from exc

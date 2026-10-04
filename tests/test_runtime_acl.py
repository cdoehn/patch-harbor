"""Windows ACL evidence: accept OS normalization, reject changed permissions."""
from copy import deepcopy
import itertools
import json
import os
import subprocess

import pytest

from tests import runtime_permissions as permissions
from tests.runtime_acl import restored_dacl_matches, verify_restored_dacls

pytestmark = pytest.mark.packaging

DIRECTORY = "(A;OICIID;FA;;;SY)(A;OICIID;FA;;;BA)(A;OICIID;FA;;;OW)"
FILE = "(A;ID;FA;;;SY)(A;ID;FA;;;BA)(A;ID;FA;;;OW)"
PROBE = "(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
REORDERED_FILE = "(A;ID;FA;;;OW)(A;ID;FA;;;SY)(A;ID;FA;;;BA)"


@pytest.mark.parametrize(("expected", "actual"), [
    ("D:" + DIRECTORY, "D:AI" + DIRECTORY),
    ("D:" + FILE, "D:AI" + FILE),
    ("D:P" + PROBE, "D:PAI" + PROBE),
    ("D:" + FILE, "D:AI" + REORDERED_FILE),
])
def test_exact_ci_readbacks_preserve_permissions(expected, actual):
    # Actual pairs from run 37191971893, job 111405903594. The old literal
    # comparison rejected these after successful Set-Acl restoration.
    assert expected != actual
    assert restored_dacl_matches(expected, actual)


@pytest.mark.parametrize(("expected", "actual"), [
    ("D:P" + FILE, "D:AI" + FILE),  # protection lost
    ("D:" + FILE, "D:PAI" + FILE),  # protection unexpectedly added
    ("D:AR" + FILE, "D:AI" + FILE),  # request flag lost
    ("D:" + FILE, "D:ARAI" + FILE),  # request flag added
    ("D:AI" + FILE, "D:" + FILE),  # AI may be added, not lost
    ("D:" + FILE, "D:AI" + FILE.replace(";;;OW)", ";;;WD)")),
    ("D:" + FILE, "D:AI" + FILE.replace(";FA;", ";FR;", 1)),
    ("D:" + FILE, "D:AI" + FILE.replace(";ID;", ";;", 1)),
    ("D:" + FILE, "D:AI" + FILE.replace("(A;ID;FA;;;SY)", "")),
    ("D:" + FILE, "D:AI" + FILE + "(A;ID;FA;;;WD)"),
    ("D:" + FILE, "D:AI" + FILE + "(A;ID;FA;;;SY)"),
    ("D:" + FILE, "D:AI(D;;FW;;;OW)" + FILE),
    ("D:(D;;FW;;;WD)(A;;FA;;;OW)", "D:AI(A;;FA;;;OW)(D;;FW;;;WD)"),
    ("D:(A;ID;FA;;;SY)(A;;FA;;;BA)", "D:AI(A;;FA;;;BA)(A;ID;FA;;;SY)"),
    ("D:(A;;FA;;;SY)(XA;;FR;;;BA)(A;;FA;;;OW)",
     "D:AI(A;;FA;;;OW)(XA;;FR;;;BA)(A;;FA;;;SY)"),
    ("D:", "D:NO_ACCESS_CONTROL"),
    ("D:" + FILE, "D:AIAI" + FILE),
    ("D:" + FILE, "D:AI" + FILE + "unparsed"),
])
def test_changed_acl_state_is_never_normalized_away(expected, actual):
    assert not restored_dacl_matches(expected, actual)


def test_allow_permutations_do_not_change_access_decisions():
    # Independent access-check oracle for simple ACEs: evaluate requested bits
    # against every token subset. Include deny barriers and partial grants.
    aces = [("A", "SY", 1), ("A", "BA", 2), ("D", "SY", 2), ("A", "OW", 3)]
    def sddl(sequence):
        return "D:" + "".join(f"({kind};;0x{mask:x};;;{sid})" for kind, sid, mask in sequence)
    def allowed(sequence, token, requested):
        remaining = requested
        for kind, sid, mask in sequence:
            if sid not in token:
                continue
            if kind == "D" and mask & remaining:
                return False
            if kind == "A":
                remaining &= ~mask
                if not remaining:
                    return True
        return False
    permutations = list(itertools.permutations(aces))
    for original in permutations:
        for candidate in permutations:
            if restored_dacl_matches(sddl(original), sddl(candidate)):
                for bits in range(8):
                    token = {sid for i, sid in enumerate(("SY", "BA", "OW")) if bits & (1 << i)}
                    for requested in (1, 2, 3):
                        assert allowed(original, token, requested) == allowed(candidate, token, requested)


def _document(root):
    return {"root": str(root), "entries": [
        {"path": str(root), "sddl": "D:P" + PROBE},
        {"path": str(root / "module.py"), "sddl": "D:" + FILE},
    ]}


@pytest.mark.parametrize("kind", ["success", "rights", "missing", "extra", "duplicate", "root",
                                      "empty", "shape", "invalid_json", "duplicate_key"])
def test_native_restore_readback_is_complete_and_controls_journal_cleanup(tmp_path, monkeypatch, kind):
    # Exercise the actual subprocess adapter and context-manager cleanup on all
    # platforms. Only the native OS call is replaced, not verification logic.
    root = tmp_path / "owned [tree] Gr\u00fc\u00dfe ' quote"
    root.mkdir()
    expected = _document(root)
    actual = deepcopy(expected)
    actual["entries"][0]["sddl"] = "D:PAI" + PROBE
    actual["entries"][1]["sddl"] = "D:AI" + REORDERED_FILE
    if kind == "rights":
        actual["entries"][1]["sddl"] = "D:AI" + REORDERED_FILE.replace(";FA;", ";FR;", 1)
    elif kind == "missing":
        actual["entries"].pop()
    elif kind == "extra":
        actual["entries"].append({"path": str(root / "extra"), "sddl": "D:"})
    elif kind == "duplicate":
        actual["entries"].append(deepcopy(actual["entries"][0]))
    elif kind == "root":
        actual["root"] = str(tmp_path / "different")
    elif kind == "empty":
        actual["entries"] = []
    elif kind == "shape":
        actual["entries"][0]["sddl"] = None
    readback = json.dumps(actual, ensure_ascii=False)
    if kind == "invalid_json":
        readback = ""
    elif kind == "duplicate_key":
        readback = '{"root":"wrong",' + readback[1:]
    monkeypatch.setattr(permissions.shutil, "which", lambda *args, **kwargs: "native-powershell")
    calls = []
    def run(command, **options):
        action = command[command.index("-Action") + 1]
        calls.append(action)
        if action == "deny":
            from pathlib import Path
            Path(command[-1]).write_text(json.dumps(expected), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, readback if action == "restore" else "", "")
    monkeypatch.setattr(permissions.subprocess, "run", run)
    environment = {**os.environ, "PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE": "powershell.exe"}
    if kind == "success":
        with permissions._windows_readonly(root, environment):
            pass
        assert not list(tmp_path.glob("runtime-acl-*"))
    else:
        with pytest.raises(RuntimeError):
            with permissions._windows_readonly(root, environment):
                pass
        journals = list(tmp_path.glob("runtime-acl-*/original-dacls.json"))
        assert len(journals) == 1 and json.loads(journals[0].read_text()) == expected
    assert calls == ["deny", "restore"]


def test_saved_inventory_cannot_be_ambiguous(tmp_path):
    root = tmp_path / "root"
    saved = _document(root)
    saved["entries"].append({**saved["entries"][0], "path": str(root).upper()})
    journal = tmp_path / "saved.json"
    journal.write_text(json.dumps(saved))
    with pytest.raises(RuntimeError):
        verify_restored_dacls(journal, json.dumps(saved))

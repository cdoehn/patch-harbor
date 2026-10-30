"""Shared recovery fixtures and behavior probes."""
from __future__ import annotations

from hashlib import sha256
import json
import subprocess
import sys

from tests.platform_support import project_environment
from tests.registration_support import exchange_state_path
from tests.archive_support import _committing_patch, _world
from tests.exchange_support import _identity_record


_CRASH = r'''
import os, sys
import patchharbor.application_apply as app
import patchharbor.application_exchange as exchange_app
import patchharbor.result_bundle_publication as publication
from patchharbor.cli import main
point = sys.argv[1]
def crash(*args, **kwargs):
    os._exit(86)
if point == "before_entrypoint":
    app.execute_prepared_script_with_log = crash
elif point == "after_commit":
    app._complete_entrypoint_execution = crash
elif point == "before_publish":
    publication.replace_path = crash
elif point == "after_publish":
    exchange_app.mark_exchange_apply_finished = crash
elif point == "persistence_error":
    from patchharbor.errors import patch_package_error
    def fail(*args, **kwargs):
        raise patch_package_error("simulated ledger write failure")
    exchange_app.mark_exchange_apply_finished = fail
else:
    raise AssertionError(point)
raise SystemExit(main(["apply", "--json", *sys.argv[2:]]))
'''


def _crash(repo, env, point="after_publish", *args):
    result = subprocess.run([sys.executable, "-c", _CRASH, point, *args], cwd=repo,
                            env=project_environment(env), capture_output=True, text=True)
    assert result.returncode == (10 if point == "persistence_error" else 86), result.stdout + result.stderr
    return result


def _pending(tmp_path, *, point="after_publish", explicit=False):
    env, exchange, repo, context = _world(tmp_path)
    patch = exchange / "patch.zip.txt"
    _committing_patch(patch, context)
    _crash(repo, env, point, *([str(patch)] if explicit else []))
    record = _identity_record(env, patch)
    assert record["apply_status"] == "attempted"
    assert record["completed_commit"] is None
    assert record["attempt_run_id"]
    return env, exchange, repo, context, patch, record


def _result(exchange, record):
    for path in exchange.iterdir():
        if path.is_file() and sha256(path.read_bytes()).hexdigest() == record["result_sha256"]:
            return path
    raise AssertionError("pinned result not found")


def _edit_record(env, patch, mutate):
    path = exchange_state_path(env)
    document = json.loads(path.read_bytes())
    for record in document["entries"]:
        if record["path"] == str(patch.resolve()):
            mutate(record)
    path.write_text(json.dumps(document), encoding="utf-8")

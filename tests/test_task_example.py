"""Executable documentation uses only the current public preparation boundary."""
from hashlib import sha256
from io import StringIO
import json

import pytest

from docs.examples.prepare_task import prepare_task
from patchharbor import api
from patchharbor.cli import main
from tests import execute_support
from tests.platform_support import native_python_script, native_value
from tests.registration_support import git


repository = execute_support.repository


@pytest.mark.e2e
@pytest.mark.parametrize('command', ['execute','apply'])
def test_documented_prepare_and_explicit_execute_with_suffix(repository, tmp_path, command):
    root, _ = repository
    api.configure_bundle_suffix('.txt', repository=root)
    reference = api.bundle(root)
    assert reference.path.name.endswith('.zip.txt')
    contents, output = tmp_path/'contents', tmp_path/'private-output'
    contents.mkdir(); output.mkdir()
    entrypoint = native_value('run.sh','run.ps1')
    (contents/entrypoint).write_text(native_python_script("from pathlib import Path\nPath('example.txt').write_text('executed')\n"))
    before = git(root,'rev-parse','HEAD').stdout
    task = prepare_task(contents,reference=reference.path,
                        expected_result_sha256=sha256(reference.path.read_bytes()).hexdigest(),
                        entrypoint=entrypoint,output_directory=output)
    assert not (root/'example.txt').exists() and git(root,'rev-parse','HEAD').stdout==before
    stdout, stderr = StringIO(), StringIO()
    assert main([command,str(task.path),'--json'],stdout=stdout,stderr=stderr)==0
    document = json.loads(stdout.getvalue())
    assert document['command']=='execute' and document['output_version']==2
    assert (root/'example.txt').read_text()=='executed'
    assert git(root,'rev-parse','HEAD').stdout==before
    if command=='apply':
        assert stderr.getvalue()


def test_example_rejects_untrusted_reference_before_output(repository, tmp_path):
    root, _ = repository
    reference = api.bundle(root)
    output = tmp_path/'must-not-exist'
    with pytest.raises(api.ResultSnapshotError):
        prepare_task(tmp_path/'missing-contents',reference=reference.path,
                     expected_result_sha256='0'*64,entrypoint='run.sh',output_directory=output)
    assert not output.exists()

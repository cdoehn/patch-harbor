"""Synthetic Result-3 fixtures; no production writer activation is implied."""
import pytest
from patchharbor import runtime_pyz as pyz
from patchharbor.pyz_artifact import PyzArtifact
from tests.reference_support import reference_entries
from tests.result_runtime_support import attach_pyz
from tests.runtime_pyz_support import inputs, prepared


@pytest.fixture(scope='module')
def canonical():
    payloads = inputs()
    payloads['patchharbor/api.py'] = b'raise AssertionError("Result reader executed described API")\n'
    return prepared(payloads)[2]


def format3(raw, **options):
    files,binding = reference_entries(handoff=True,**options)
    return attach_pyz(files,raw), binding


@pytest.fixture(scope="module")
def artifact():
    fixture_inputs = inputs()
    # Keep the runtime above the explicit 128-KiB publication-test budget.
    fixture_inputs["patchharbor/budget_fixture.py"] = b"# Runtime budget fixture\n" * 10000
    recipe,payloads,raw=prepared(fixture_inputs)
    return PyzArtifact(recipe,raw,pyz.sha256(raw),payloads[pyz.CHAT_PATH],
                       payloads[pyz.DOC_PATH],payloads[pyz.LICENSE_PATH])

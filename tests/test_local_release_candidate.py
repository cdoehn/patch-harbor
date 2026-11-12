"""A local candidate cannot imply publication or accept unbound source inputs."""
import pytest

from scripts import prepare_local_release as candidate


@pytest.mark.parametrize('version,commit', [('2.0.0.dev0','a'*40),('2.0.0','short'),('2.0.0','A'*40)])
def test_invalid_candidate_identity_stops_before_processes_and_writes(tmp_path, monkeypatch, version, commit):
    monkeypatch.setattr(candidate.subprocess,'check_output',lambda *a,**k:pytest.fail('invalid identity reached Git'))
    with pytest.raises(ValueError):
        candidate.prepare(version,commit,tmp_path/'assets',tmp_path/'evidence')
    assert not list(tmp_path.iterdir())


def test_failed_candidate_build_preserves_evidence_without_success_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate,'source_checkout',lambda *a:None)
    def failed(output):
        (output/'incomplete.txt').write_bytes(b'partial build')
        raise RuntimeError('build failed')
    monkeypatch.setattr(candidate,'build_release',failed)
    with pytest.raises(RuntimeError):
        candidate.prepare('2.0.0','a'*40,tmp_path/'assets',tmp_path/'evidence')
    assert (tmp_path/'assets/incomplete.txt').read_bytes()==b'partial build'
    assert not (tmp_path/'evidence/local-candidate.json').exists()


def test_existing_assets_are_never_rebuilt_or_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate,'source_checkout',lambda *a:None)
    monkeypatch.setattr(candidate,'build_release',lambda *a:pytest.fail('existing candidate rebuilt'))
    assets=tmp_path/'assets';assets.mkdir();(assets/'keep').write_bytes(b'original')
    with pytest.raises(FileExistsError):
        candidate.prepare('2.0.0','a'*40,assets,tmp_path/'evidence')
    assert (assets/'keep').read_bytes()==b'original'
    assert not (tmp_path/'evidence').exists()

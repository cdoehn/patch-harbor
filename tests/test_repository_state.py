from patchharbor.repository_state import empty_state_fingerprint_digest


def test_empty_state_matches_the_normative_reference_vector() -> None:
    assert empty_state_fingerprint_digest() == (
        "7c9d2a24e397e0e58d8caf4c14abf8f76879b256ef7f843655981fb751c7b309"
    )

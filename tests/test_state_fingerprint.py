from patchharbor.state_fingerprint import (
    encode_staged_record,
    state_fingerprint_digest,
)


def test_empty_state_matches_the_normative_reference_vector() -> None:
    assert state_fingerprint_digest() == (
        "7c9d2a24e397e0e58d8caf4c14abf8f76879b256ef7f843655981fb751c7b309"
    )


def test_staged_addition_matches_the_normative_reference_vector() -> None:
    staged = encode_staged_record(
        path=b"app.txt",
        head_mode=b"",
        head_object=b"",
        index_mode=b"100644",
        index_object=b"0123456789abcdef0123456789abcdef01234567",
    )

    assert state_fingerprint_digest(staged_records=(staged,)) == (
        "b56f3f6610db992f53139dc53d1decdccb9fd510260dafa1a29473c47a257008"
    )


def test_staged_deletion_keeps_the_missing_index_side_in_the_digest() -> None:
    staged = encode_staged_record(
        path=b"old.txt",
        head_mode=b"100755",
        head_object=b"2" * 40,
        index_mode=b"",
        index_object=b"",
    )

    assert state_fingerprint_digest(staged_records=(staged,)) == (
        "e0f1cdf0726728171ccb63d77e21f1cad0221dccfcdeed7e6e045adee237ab69"
    )

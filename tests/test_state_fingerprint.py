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


def _decode_fields(encoded: bytes) -> tuple[tuple[bytes, bytes], ...]:
    fields: list[tuple[bytes, bytes]] = []
    offset = 0
    while offset < len(encoded):
        name_end = encoded.index(b"\0", offset)
        name = encoded[offset:name_end]
        length_start = name_end + 1
        length_end = length_start + 8
        payload_length = int.from_bytes(
            encoded[length_start:length_end],
            "big",
        )
        payload_end = length_end + payload_length
        fields.append((name, encoded[length_end:payload_end]))
        offset = payload_end
    return tuple(fields)


def test_staged_missing_sides_remain_present_as_empty_fields() -> None:
    addition = encode_staged_record(
        path=b"new.txt",
        head_mode=b"",
        head_object=b"",
        index_mode=b"100644",
        index_object=b"1" * 40,
    )
    deletion = encode_staged_record(
        path=b"old.txt",
        head_mode=b"100755",
        head_object=b"2" * 40,
        index_mode=b"",
        index_object=b"",
    )

    assert _decode_fields(addition) == (
        (b"staged-path", b"new.txt"),
        (b"staged-head-mode", b""),
        (b"staged-head-object", b""),
        (b"staged-index-mode", b"100644"),
        (b"staged-index-object", b"1" * 40),
    )
    assert _decode_fields(deletion) == (
        (b"staged-path", b"old.txt"),
        (b"staged-head-mode", b"100755"),
        (b"staged-head-object", b"2" * 40),
        (b"staged-index-mode", b""),
        (b"staged-index-object", b""),
    )

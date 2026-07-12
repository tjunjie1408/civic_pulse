import json

from hypothesis import given, strategies as st

from civicpulse.normalize import normalize_text


def test_common_malaysian_abbreviations_are_normalized():
    assert normalize_text("Jln dpn skolah ada longkang sumbat") == "jalan depan sekolah ada longkang tersumbat"
    assert normalize_text("Lampu jln rosak") == "lampu jalan rosak"


def test_normalization_preserves_landmarks_and_numbers():
    result = normalize_text("Blok C, Jalan Kenanga 18")

    assert "blok c" in result
    assert "jalan kenanga 18" in result


@given(st.text(max_size=1000))
def test_normalization_is_idempotent(text):
    assert normalize_text(normalize_text(text)) == normalize_text(text)


def test_alias_file_is_valid_json():
    aliases = json.loads(open("config/normalization_aliases.json", encoding="utf-8").read())

    assert aliases["version"] == "normalization-v1"
    assert aliases["aliases"]["jln"] == "jalan"

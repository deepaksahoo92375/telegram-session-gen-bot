import pytest

from src.validation.validators import (
    ValidationError,
    validate_api_hash,
    validate_api_id,
    validate_code,
    validate_output_choice,
    validate_password,
    validate_phone,
)


def test_validate_api_id_accepts_valid():
    assert validate_api_id("123456") == 123456


def test_validate_api_id_rejects_non_digit():
    with pytest.raises(ValidationError):
        validate_api_id("abc123")


def test_validate_api_id_rejects_out_of_range():
    with pytest.raises(ValidationError):
        validate_api_id("99999999999999999")


def test_validate_api_hash_accepts_valid():
    h = "a" * 32
    assert validate_api_hash(h) == h


@pytest.mark.parametrize("bad", ["short", "z" * 32, "a" * 31, "a" * 33])
def test_validate_api_hash_rejects_invalid(bad):
    with pytest.raises(ValidationError):
        validate_api_hash(bad)


@pytest.mark.parametrize("phone", ["+15551234567", "+442071838750"])
def test_validate_phone_accepts_valid(phone):
    assert validate_phone(phone) == phone


@pytest.mark.parametrize("phone", ["5551234567", "+0123456", "notaphone", "+1"])
def test_validate_phone_rejects_invalid(phone):
    with pytest.raises(ValidationError):
        validate_phone(phone)


@pytest.mark.parametrize(
    "raw,expected", [("12345", "12345"), ("1 2 3 4 5", "12345"), ("12-345", "12345")]
)
def test_validate_code_normalizes_separators(raw, expected):
    assert validate_code(raw) == expected


@pytest.mark.parametrize("raw", ["123", "1234567", "abcde", ""])
def test_validate_code_rejects_invalid(raw):
    with pytest.raises(ValidationError):
        validate_code(raw)


def test_validate_password_rejects_empty():
    with pytest.raises(ValidationError):
        validate_password("")


def test_validate_output_choice():
    assert validate_output_choice("String") == "string"
    with pytest.raises(ValidationError):
        validate_output_choice("zip")

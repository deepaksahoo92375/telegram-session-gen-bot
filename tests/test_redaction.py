from src.security.redaction import redact_exception, redact_mapping, redact_text


def test_redact_text_hides_phone_number():
    text = "Failed for phone +15551234567 during login"
    assert "5551234567" not in redact_text(text)


def test_redact_text_hides_api_hash_like_token():
    api_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    text = f"invalid hash {api_hash}"
    assert api_hash not in redact_text(text)


def test_redact_text_hides_long_token():
    token = "x" * 60
    assert token not in redact_text(f"session={token}")


def test_redact_mapping_hides_sensitive_keys():
    data = {"api_hash": "secretvalue", "note": "public info"}
    out = redact_mapping(data)
    assert out["api_hash"] == "[REDACTED]"
    assert out["note"] == "public info"


def test_redact_exception_never_leaks_message_verbatim():
    exc = ValueError("phone +15559998888 invalid")
    result = redact_exception(exc)
    assert "5559998888" not in result
    assert result.startswith("ValueError:")

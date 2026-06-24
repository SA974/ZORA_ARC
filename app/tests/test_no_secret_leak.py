from app.config import mask_secret, sanitize_mapping
from app.logging_config import redact


def test_redact_masks_known_secret_patterns():
    text = "NVIDIA_API_KEY=" + "nva" + "pi-abcdefghijklmnopqrstuvwxyz token=" + "sk" + "-proj-abcdefghijklmnopqrstuvwxyz"
    redacted = redact(text)
    assert "nvapi-" not in redacted
    assert "sk-proj-" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted


def test_sanitize_mapping_masks_sensitive_keys():
    fake_key = "nva" + "pi-secret-value"
    data = sanitize_mapping({"LLM_API_KEY": fake_key, "POSTGRES_PASSWORD": "password123", "ARC_MEM_ENV": "local"})
    assert data["ARC_MEM_ENV"] == "local"
    assert data["LLM_API_KEY"] != fake_key
    assert data["POSTGRES_PASSWORD"] != "password123"


def test_mask_secret_keeps_only_edges():
    assert mask_secret("1234567890") == "1234...7890"

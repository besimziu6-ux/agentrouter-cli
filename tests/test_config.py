"""Config fallback order: env > file > default."""

import json

import agentrouter.config as cfg_mod
from agentrouter.config import (
    DEFAULT_BASE_URL,
    load_config,
    save_config,
    validate_base_url,
)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_env_key_takes_precedence(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"api_key": "file-key"})
    monkeypatch.setenv("AGENTROUTER_API_KEY", "env-key")
    c = load_config(p)
    assert c.api_key == "env-key"


def test_file_key_used_when_no_env(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"api_key": "file-key"})
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    c = load_config(p)
    assert c.api_key == "file-key"


def test_missing_key_is_none(tmp_path, monkeypatch):
    p = tmp_path / "missing.json"
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    c = load_config(p)
    assert c.api_key is None


def test_blank_env_key_falls_back_to_file(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"api_key": "file-key"})
    monkeypatch.setenv("AGENTROUTER_API_KEY", "   ")
    assert load_config(p).api_key == "file-key"


def test_default_model_env_over_file(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"default_model": "file-model"})
    monkeypatch.setenv("AGENTROUTER_DEFAULT_MODEL", "env-model")
    assert load_config(p).default_model == "env-model"


def test_default_model_file_fallback(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"default_model": "file-model"})
    monkeypatch.delenv("AGENTROUTER_DEFAULT_MODEL", raising=False)
    assert load_config(p).default_model == "file-model"


def test_rejects_non_agentrouter_base_url(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {"base_url": "https://evil.example.com/v1"})
    monkeypatch.delenv("AGENTROUTER_BASE_URL", raising=False)
    try:
        load_config(p)
    except ValueError as exc:
        assert "only https://agentrouter.org/v1" in str(exc)
    else:
        raise AssertionError("expected ValueError for foreign base_url")


def test_env_base_url_rejected(tmp_path, monkeypatch):
    p = _write(tmp_path / "config.json", {})
    monkeypatch.setenv("AGENTROUTER_BASE_URL", "https://evil.example.com/v1")
    try:
        load_config(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for env base_url")
    finally:
        monkeypatch.delenv("AGENTROUTER_BASE_URL", raising=False)


def test_validate_base_url_accepts_official():
    assert validate_base_url(DEFAULT_BASE_URL) == DEFAULT_BASE_URL
    assert validate_base_url(DEFAULT_BASE_URL + "/") == DEFAULT_BASE_URL


def test_save_and_reload_roundtrip(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTROUTER_DEFAULT_MODEL", raising=False)
    saved = save_config(api_key="k1", default_model="m1", config_path=p)
    assert saved.api_key == "k1"
    assert load_config(p).default_model == "m1"


def test_require_api_key_raises(tmp_path, monkeypatch):
    p = tmp_path / "missing.json"
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    c = load_config(p)
    try:
        c.require_api_key()
    except ValueError as exc:
        assert "agentrouter config set-key" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_invalid_json_raises(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    try:
        load_config(p)
    except ValueError as exc:
        assert "Invalid JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")

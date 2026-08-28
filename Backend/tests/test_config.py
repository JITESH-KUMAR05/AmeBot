import importlib

import pytest


def test_config_imports_with_stubbed_env():
    import config
    assert config.TOP_K == 4
    assert config.MIN_SIMILARITY_SCORE == 0.75


def test_missing_api_key_names_the_real_var(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    import config as config_mod
    with pytest.raises(EnvironmentError) as excinfo:
        importlib.reload(config_mod)
    assert "AZURE_OPENAI_API_KEY" in str(excinfo.value)
    # restore for other tests
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    importlib.reload(config_mod)

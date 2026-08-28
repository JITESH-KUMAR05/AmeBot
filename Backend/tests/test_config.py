def test_config_imports_with_stubbed_env():
    import config
    assert config.TOP_K == 4
    assert config.MIN_SIMILARITY_SCORE == 0.70

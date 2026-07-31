import pytest

from app.config import Settings


def valid_env() -> dict[str, str]:
    return {
        "YM30_PROVIDER_KEY_ID": "cp_test",
        "YM30_PROVIDER_SECRET": "test-secret",
        "DOUBAO_API_KEY": "test-doubao",
        "DOUBAO_MODEL": "ep-test",
        "DEEPSEEK_API_KEY": "test-deepseek",
    }


def test_settings_defaults_are_portable() -> None:
    settings = Settings.from_env(valid_env())
    assert settings.doubao_base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.nonce_ttl_seconds == 600


def test_missing_doubao_model_is_rejected() -> None:
    env = valid_env()
    env.pop("DOUBAO_MODEL")
    with pytest.raises(ValueError, match="DOUBAO_MODEL"):
        Settings.from_env(env).validate_runtime()


def test_secret_values_are_redacted_from_repr() -> None:
    settings = Settings.from_env(valid_env())
    rendered = repr(settings)
    assert "test-secret" not in rendered
    assert "test-doubao" not in rendered
    assert "test-deepseek" not in rendered

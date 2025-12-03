import uuid

from app.models import Provider, ProviderAPIKey, ProviderModel
from app.provider.config import get_provider_config, load_provider_configs
from app.services.encryption import encrypt_secret


def _build_provider(
    *, slug: str = "openai", status: str = "active", provider_type: str = "native"
) -> Provider:
    provider = Provider(
        provider_id=slug,
        name="OpenAI",
        base_url="https://api.openai.com",
        transport="http",
        provider_type=provider_type,
        models_path="/v1/models",
        messages_path="/v1/messages",
        custom_headers={"X-Test": "1"},
        retryable_status_codes=[429, "500"],
    )
    provider.id = uuid.uuid4()

    provider.api_keys = [
        ProviderAPIKey(
            provider_uuid=provider.id,
            encrypted_key=encrypt_secret("sk-test"),
            weight=2.0,
            max_qps=10,
            label="primary",
            status=status,
        )
    ]
    provider.models = [
        ProviderModel(
            provider_id=provider.id,
            model_id="gpt-4o",
            family="gpt-4",
            display_name="GPT-4 Omni",
            context_length=128000,
            capabilities=["chat"],
            pricing={"input": 0.01},
        )
    ]
    return provider


def test_load_provider_configs_reads_from_db(monkeypatch):
    provider = _build_provider()

    def _fake_loader(session):
        assert session == "fake-session"
        return [provider]

    monkeypatch.setattr("app.provider.config._load_providers_from_db", _fake_loader)

    configs = load_provider_configs(session="fake-session")
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.id == "openai"
    assert cfg.transport == "http"
    assert cfg.provider_type == "native"
    assert cfg.static_models is not None
    assert cfg.static_models[0]["id"] == "gpt-4o"
    assert cfg.custom_headers == {"X-Test": "1"}
    keys = cfg.get_api_keys()
    assert len(keys) == 1
    assert keys[0].weight == 2.0
    assert keys[0].label == "primary"


def test_aggregator_provider_type_is_preserved(monkeypatch):
    provider = _build_provider(provider_type="aggregator")

    def _fake_loader(session):
        return [provider]

    monkeypatch.setattr("app.provider.config._load_providers_from_db", _fake_loader)

    configs = load_provider_configs(session="fake-session")
    assert configs[0].provider_type == "aggregator"


def test_invalid_provider_type_defaults_to_native(monkeypatch):
    provider = _build_provider()
    provider.provider_type = "invalid"

    def _fake_loader(session):
        return [provider]

    monkeypatch.setattr("app.provider.config._load_providers_from_db", _fake_loader)

    configs = load_provider_configs(session="fake-session")
    assert configs[0].provider_type == "native"


def test_provider_without_active_keys_is_skipped(monkeypatch):
    inactive = _build_provider(status="disabled")

    def _fake_loader(session):
        return [inactive]

    monkeypatch.setattr("app.provider.config._load_providers_from_db", _fake_loader)
    configs = load_provider_configs(session="fake-session")
    assert configs == []


def test_get_provider_config_returns_none_when_missing(monkeypatch):
    class _FakeSession:
        def execute(self, stmt):
            class _Result:
                def scalars(self_inner):
                    class _Scalars:
                        def first(self_innermost):
                            return None

                    return _Scalars()

            return _Result()

    cfg = get_provider_config("missing", session=_FakeSession())
    assert cfg is None


def test_get_provider_config_converts_headers_and_codes(monkeypatch):
    provider = _build_provider()
    provider.static_models = [{"id": "manual"}]
    provider.models = []

    class _FakeSession:
        def execute(self, stmt):
            class _Result:
                def __init__(self, provider_obj):
                    self.provider_obj = provider_obj

                def scalars(self):
                    provider_obj = self.provider_obj

                    class _Scalars:
                        def __init__(self, inner_provider):
                            self.inner_provider = inner_provider

                        def first(self):
                            return self.inner_provider

                    return _Scalars(provider_obj)

            return _Result(provider)

    cfg = get_provider_config("openai", session=_FakeSession())
    assert cfg is not None
    assert cfg.retryable_status_codes == [429, 500]
    assert cfg.custom_headers == {"X-Test": "1"}
    assert cfg.static_models == [{"id": "manual"}]


from app.routing.mapper import (
    ConsistencyIssue,
    build_provider_model_index,
    is_logical_model_consistent,
    select_candidate_upstreams,
    validate_logical_model_consistency,
)
from app.schemas import LogicalModel, Model, ModelCapability, PhysicalModel


def _make_models() -> dict[tuple[str, str], Model]:
    models: list[Model] = [
        Model(
            model_id="gpt-4",
            provider_id="openai",
            family="gpt-4",
            display_name="GPT-4 OpenAI",
            context_length=8192,
            capabilities=[ModelCapability.CHAT],
            meta_hash="hash-123",
        ),
        Model(
            model_id="gpt-4",
            provider_id="azure",
            family="gpt-4",
            display_name="GPT-4 Azure",
            context_length=8192,
            capabilities=[ModelCapability.CHAT],
            meta_hash="hash-123",
        ),
        Model(
            model_id="gpt-4-mini",
            provider_id="other",
            family="gpt-4-mini",
            display_name="GPT-4 Mini",
            context_length=4096,
            capabilities=[ModelCapability.CHAT],
            meta_hash="hash-mini",
        ),
    ]
    return build_provider_model_index(models)


def _make_logical_model(upstreams: list[PhysicalModel]) -> LogicalModel:
    return LogicalModel(
        logical_id="gpt-4",
        display_name="GPT-4",
        description="Test logical model",
        capabilities=[ModelCapability.CHAT],
        upstreams=upstreams,
        enabled=True,
        updated_at=1704067200.0,
    )


def test_validate_logical_model_consistency_ok():
    index = _make_models()
    logical = _make_logical_model(
        [
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash="hash-123",
                updated_at=1704067200.0,
            ),
            PhysicalModel(
                provider_id="azure",
                model_id="gpt-4",
                endpoint="https://azure.example.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash="hash-123",
                updated_at=1704067200.0,
            ),
        ]
    )

    issues: list[ConsistencyIssue] = validate_logical_model_consistency(
        logical, index
    )
    assert issues == []
    assert is_logical_model_consistent(logical, index)


def test_validate_logical_model_consistency_missing_model():
    index = _make_models()
    logical = _make_logical_model(
        [
            PhysicalModel(
                provider_id="unknown",
                model_id="gpt-4",
                endpoint="https://unknown.example.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=1704067200.0,
            )
        ]
    )

    issues = validate_logical_model_consistency(logical, index)
    assert any(i.code == "missing_provider_model" for i in issues)
    assert not is_logical_model_consistent(logical, index)


def test_validate_logical_model_consistency_meta_hash_mismatch():
    index = _make_models()
    logical = _make_logical_model(
        [
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash="hash-123",
                updated_at=1704067200.0,
            ),
            PhysicalModel(
                provider_id="other",
                model_id="gpt-4-mini",
                endpoint="https://other.example.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash="hash-mini",
                updated_at=1704067200.0,
            ),
        ]
    )

    issues = validate_logical_model_consistency(logical, index)
    assert any(i.code == "meta_hash_mismatch" and i.level == "error" for i in issues)
    assert not is_logical_model_consistent(logical, index)


def test_select_candidate_upstreams_filters_by_region_and_excludes():
    logical = _make_logical_model(
        [
            PhysicalModel(
                provider_id="openai",
                model_id="gpt-4",
                endpoint="https://api.openai.com/v1/chat/completions",
                base_weight=1.0,
                region="global",
                max_qps=50,
                meta_hash=None,
                updated_at=1704067200.0,
            ),
            PhysicalModel(
                provider_id="azure",
                model_id="gpt-4",
                endpoint="https://azure.example.com/v1/chat/completions",
                base_weight=1.0,
                region="us-east",
                max_qps=50,
                meta_hash=None,
                updated_at=1704067200.0,
            ),
        ]
    )

    # Preferred region filter
    us_east_only = select_candidate_upstreams(
        logical, preferred_region="us-east"
    )
    assert len(us_east_only) == 1
    assert us_east_only[0].provider_id == "azure"

    # Exclude provider
    without_openai = select_candidate_upstreams(
        logical, exclude_providers=["openai"]
    )
    assert len(without_openai) == 1
    assert without_openai[0].provider_id == "azure"


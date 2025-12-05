"""
Pydantic data models for the multi-provider routing layer.

These models mirror the structures defined in
specs/001-model-routing/data-model.md and can be shared across
provider discovery, logical-model mapping and routing components.
"""

from .api_key import (
    APIKeyAllowedProvidersRequest,
    APIKeyAllowedProvidersResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyExpiry,
    APIKeyResponse,
    APIKeyUpdateRequest,
)
from .auth import LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse
from .credit import (
    CreditAccountResponse,
    CreditTopupRequest,
    CreditTransactionResponse,
)
from .logical_model import (
    LogicalModel,
    LogicalModelUpstreamsResponse,
    LogicalModelsResponse,
    PhysicalModel,
)
from .model import Model, ModelCapability
from .metrics import (
    APIKeyMetricsSummary,
    MetricsBucket,
    MetricsDataPoint,
    MetricsTimeRange,
    ProviderMetricsSummary,
    ProviderMetricsTimeSeries,
    UserMetricsSummary,
)
from .provider import (
    Provider,
    ProviderAPIKey,
    ProviderAPIKeyCreateRequest,
    ProviderAPIKeyResponse,
    ProviderAPIKeyUpdateRequest,
    ProviderConfig,
    ProviderStatus,
)
from .provider_control import (
     AdminProviderResponse,
     AdminProvidersResponse,
     PermissionResponse,
     ProviderReviewRequest,
     ProviderPresetCreateRequest,
     ProviderPresetListResponse,
     ProviderPresetResponse,
     ProviderPresetUpdateRequest,
     ProviderSubmissionRequest,
     ProviderSubmissionResponse,
     ProviderValidationResult,
     ProviderVisibilityUpdateRequest,
     RoleCreateRequest,
     RolePermissionsResponse,
     RolePermissionsUpdateRequest,
     RoleResponse,
     RoleUpdateRequest,
     UserPermissionGrantRequest,
     UserPermissionResponse,
     UserRolesUpdateRequest,
     UserProviderCreateRequest,
     UserProviderResponse,
     UserProviderUpdateRequest,
)
from .provider_routes import (
    ProviderMetricsResponse,
    ProviderModelsResponse,
    ProvidersResponse,
)
from .routing import CandidateInfo, RoutingDecision, RoutingRequest
from .routing_metrics import MetricsHistory, RoutingMetrics
from .registration import (
    RegistrationWindowCreateRequest,
    RegistrationWindowResponse,
    RegistrationWindowStatus,
)
from .scheduling import SchedulingStrategy
from .system import (
    KeyValidationRequest,
    KeyValidationResponse,
    ProviderLimitsResponse,
    ProviderLimitsUpdateRequest,
    SecretKeyGenerationRequest,
    SecretKeyResponse,
    SystemAdminInitRequest,
    SystemAdminInitResponse,
)
from .session import Session
from .user import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)

__all__ = [
    "APIKeyAllowedProvidersRequest",
    "APIKeyAllowedProvidersResponse",
    "APIKeyCreateRequest",
    "APIKeyCreateResponse",
    "APIKeyExpiry",
    "APIKeyResponse",
    "APIKeyUpdateRequest",
    "APIKeyMetricsSummary",
    "CandidateInfo",
    "CreditAccountResponse",
    "CreditTopupRequest",
    "CreditTransactionResponse",
    "LogicalModel",
    "LogicalModelUpstreamsResponse",
    "LogicalModelsResponse",
    "MetricsHistory",
    "MetricsBucket",
    "MetricsDataPoint",
    "MetricsTimeRange",
    "Model",
    "ModelCapability",
    "PhysicalModel",
    "Provider",
    "ProviderAPIKey",
    "ProviderConfig",
    "ProviderStatus",
    "ProviderLimitsResponse",
    "ProviderLimitsUpdateRequest",
    "ProviderMetricsResponse",
    "ProviderMetricsSummary",
    "ProviderMetricsTimeSeries",
    "ProviderModelsResponse",
    "ProvidersResponse",
    "SecretKeyGenerationRequest",
    "SecretKeyResponse",
    "SystemAdminInitRequest",
    "SystemAdminInitResponse",
    "AdminProviderResponse",
    "AdminProvidersResponse",
    "PermissionResponse",
     "ProviderReviewRequest",
    "ProviderPresetCreateRequest",
    "ProviderPresetListResponse",
    "ProviderPresetResponse",
    "ProviderPresetUpdateRequest",
     "ProviderSubmissionRequest",
    "ProviderSubmissionResponse",
    "ProviderValidationResult",
    "ProviderVisibilityUpdateRequest",
    "RoleCreateRequest",
    "RolePermissionsResponse",
    "RolePermissionsUpdateRequest",
    "RoleResponse",
    "RoleUpdateRequest",
    "ProviderAPIKeyCreateRequest",
    "ProviderAPIKeyUpdateRequest",
    "ProviderAPIKeyResponse",
    "RefreshTokenRequest",
    "RegisterRequest",
    "RegistrationWindowCreateRequest",
    "RegistrationWindowResponse",
    "RegistrationWindowStatus",
    "RoutingDecision",
    "RoutingMetrics",
    "RoutingRequest",
    "SchedulingStrategy",
    "Session",
    "TokenResponse",
    "UserPermissionGrantRequest",
    "UserPermissionResponse",
    "UserRolesUpdateRequest",
    "UserProviderCreateRequest",
    "UserProviderResponse",
    "UserProviderUpdateRequest",
    "UserCreateRequest",
    "UserResponse",
    "UserStatusUpdateRequest",
    "UserUpdateRequest",
    "KeyValidationRequest",
    "KeyValidationResponse",
    "LoginRequest",
    "UserMetricsSummary",
]

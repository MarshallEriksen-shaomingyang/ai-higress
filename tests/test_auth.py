import base64

import pytest

from service.auth import require_api_key
from service.settings import settings


@pytest.mark.asyncio
async def test_require_api_key_uses_configured_token(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_token", "custom-secret", raising=False)
    encoded = base64.b64encode(b"custom-secret").decode("ascii")
    authorization = f"Bearer {encoded}"

    token = await require_api_key(authorization=authorization)

    assert token == "custom-secret"

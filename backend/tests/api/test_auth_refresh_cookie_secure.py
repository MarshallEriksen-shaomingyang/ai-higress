from __future__ import annotations


def _find_set_cookie(headers: list[str], prefix: str) -> str | None:
    for value in headers:
        if value.lower().startswith(prefix.lower()):
            return value
    return None


def test_refresh_cookie_not_secure_in_development(client):
    resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "Secret123!"},
    )
    assert resp.status_code == 200, resp.text

    set_cookies = resp.headers.get_list("set-cookie")
    refresh_cookie = _find_set_cookie(set_cookies, "refresh_token=")
    assert refresh_cookie is not None
    assert "httponly" in refresh_cookie.lower()
    assert "secure" not in refresh_cookie.lower()


def test_refresh_cookie_secure_in_production(client, monkeypatch):
    from app.settings import settings

    original_env = settings.environment
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    try:
        resp = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Secret123!"},
        )
        assert resp.status_code == 200, resp.text

        set_cookies = resp.headers.get_list("set-cookie")
        refresh_cookie = _find_set_cookie(set_cookies, "refresh_token=")
        assert refresh_cookie is not None
        assert "httponly" in refresh_cookie.lower()
        assert "secure" in refresh_cookie.lower()
    finally:
        monkeypatch.setattr(settings, "environment", original_env, raising=False)


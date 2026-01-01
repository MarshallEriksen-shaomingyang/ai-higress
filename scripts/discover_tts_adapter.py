#!/usr/bin/env python3
"""
TTS upstream discovery helper: given an upstream audio endpoint URL, try to:
1) discover OpenAPI/Swagger spec and infer required request fields;
2) probe /v1/audio/speech-like endpoint with OpenAI-compatible payload;
3) classify compatibility and print adapter hints.

This does NOT modify gateway config. It is meant to help you decide:
- can this upstream be treated as OpenAI-compatible TTS?
- if not, what extra required fields are hinted by the upstream error?

Examples:
  python scripts/discover_tts_adapter.py --audio-url https://example.com/v1/audio/speech --auth bearer --token-file ~/.config/apiproxy/tts_token --model tts-1
  python scripts/discover_tts_adapter.py --audio-url https://ai.gitee.com/v1/audio/speech --auth bearer --token-file ~/.config/apiproxy/tts_token --model gemini-2.5-flash-preview-tts
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any, Literal


AuthMode = Literal["bearer", "authorization", "x-api-key"]


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    status: int | None
    content_type: str | None
    body: bytes
    error: str | None = None


def _read_first_non_empty_line(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="strict")
    for line in raw.splitlines():
        token = line.strip()
        if token:
            return token
    raise ValueError("token file is empty")


def _build_headers(*, auth: AuthMode, token: str, accept: str) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": accept,
    }
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    elif auth == "authorization":
        headers["Authorization"] = token
    elif auth == "x-api-key":
        headers["X-API-Key"] = token
    else:  # pragma: no cover
        raise ValueError(f"unsupported auth mode: {auth}")
    return headers


def _url_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid url: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _make_ssl_context(*, insecure: bool) -> ssl.SSLContext | None:
    if not insecure:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 15.0,
    context: ssl.SSLContext | None = None,
) -> FetchResult:
    req = urllib.request.Request(url=url, method=method, headers=headers or {}, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            content_type = resp.headers.get("Content-Type")
            data = resp.read()
            return FetchResult(ok=200 <= status < 300, status=status, content_type=content_type, body=data)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        content_type = exc.headers.get("Content-Type") if exc.headers else None
        return FetchResult(
            ok=False,
            status=int(exc.code),
            content_type=content_type,
            body=raw,
            error=str(exc),
        )
    except Exception as exc:
        return FetchResult(ok=False, status=None, content_type=None, body=b"", error=str(exc))


def _try_parse_json_bytes(body: bytes) -> Any | None:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8", errors="strict"))
    except Exception:
        return None


def _extract_error_message(payload: Any) -> str | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), str):
            return payload["error"]
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str):
                return msg
        # Some gateways nest errors under "detail"
        detail = payload.get("detail")
        if isinstance(detail, dict):
            msg = detail.get("message")
            if isinstance(msg, str):
                return msg
        if isinstance(payload.get("message"), str):
            return payload["message"]
    if isinstance(payload, str):
        return payload
    return None


def _looks_like_audio_content_type(value: str | None) -> bool:
    if not value:
        return False
    primary = value.split(";", 1)[0].strip().lower()
    return primary.startswith("audio/")


def _find_openapi_candidates(origin: str) -> list[str]:
    base = origin.rstrip("/")
    return [
        f"{base}/openapi.json",
        f"{base}/swagger.json",
        f"{base}/v1/openapi.json",
        f"{base}/api/openapi.json",
        f"{base}/api-docs",
        f"{base}/v3/api-docs",
    ]


def _infer_openapi_tts_fields(spec: Any, *, path: str) -> dict[str, Any] | None:
    if not isinstance(spec, dict):
        return None
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return None
    node = paths.get(path)
    if not isinstance(node, dict):
        return None
    post = node.get("post")
    if not isinstance(post, dict):
        return None
    request_body = post.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        return None
    schema = app_json.get("schema")
    if not isinstance(schema, dict):
        return None
    required = schema.get("required")
    props = schema.get("properties")
    if not isinstance(props, dict):
        props = {}
    out: dict[str, Any] = {
        "required": required if isinstance(required, list) else [],
        "properties": sorted([str(k) for k in props.keys()]),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover upstream TTS compatibility from a URL.")
    parser.add_argument("--audio-url", required=True, help="full upstream audio endpoint url")
    parser.add_argument("--model", required=True, help="model id to probe")
    parser.add_argument("--text", default="你好，测试。", help="input text to probe")
    parser.add_argument("--voice", default="alloy", help="voice (default: alloy)")
    parser.add_argument(
        "--format",
        default="mp3",
        choices=["mp3", "opus", "aac", "wav", "pcm", "ogg", "flac", "aiff"],
        help="response_format (default: mp3)",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="speed (default: 1.0)")
    parser.add_argument(
        "--auth",
        default="bearer",
        choices=["bearer", "authorization", "x-api-key"],
        help="auth header mode for the upstream (default: bearer)",
    )
    parser.add_argument("--token-file", type=Path, default=None, help="read token from file")
    parser.add_argument("--token", default=None, help="token (discouraged; prefer --token-file)")
    parser.add_argument("--no-prompt", action="store_true", help="fail if token not provided")
    parser.add_argument("--timeout", type=float, default=20.0, help="timeout seconds")
    parser.add_argument("--insecure", action="store_true", help="disable TLS verification (testing only)")
    parser.add_argument(
        "--skip-openapi",
        action="store_true",
        help="skip OpenAPI discovery attempt",
    )
    args = parser.parse_args(argv)

    audio_url = str(args.audio_url).strip()
    if not audio_url.startswith(("http://", "https://")):
        parser.error("--audio-url must start with http:// or https://")
        return 2

    token = ""
    if args.token_file is not None:
        try:
            token = _read_first_non_empty_line(args.token_file.expanduser().resolve())
        except Exception as exc:
            print(f"Failed to read --token-file: {exc}", file=sys.stderr)
            return 2
    else:
        token = str(args.token or "").strip()

    if not token and args.no_prompt:
        print("Missing token: provide --token-file or --token.", file=sys.stderr)
        return 2
    if not token:
        token = getpass("Token (input hidden): ").strip()
    if not token:
        print("Missing token.", file=sys.stderr)
        return 2

    context = _make_ssl_context(insecure=bool(args.insecure))
    origin = _url_origin(audio_url)
    audio_path = urllib.parse.urlsplit(audio_url).path or "/"

    if not args.skip_openapi:
        print("== OpenAPI discovery ==")
        for url in _find_openapi_candidates(origin):
            res = _fetch(url, headers={"Accept": "application/json"}, timeout=float(args.timeout), context=context)
            if not res.ok:
                continue
            spec = _try_parse_json_bytes(res.body)
            if spec is None:
                continue
            fields = _infer_openapi_tts_fields(spec, path=audio_path)
            if fields:
                print(f"Found spec: {url}")
                print(f"Path: {audio_path}")
                print("Required:", ", ".join(fields["required"]) or "(none)")
                print("Properties:", ", ".join(fields["properties"]) or "(none)")
                break
        else:
            print("No OpenAPI JSON found (or spec does not include the given path).")
        print()

    print("== Probe (OpenAI-compatible payload) ==")
    payload = {
        "model": args.model,
        "input": args.text,
        "voice": args.voice,
        "response_format": args.format,
        "speed": float(args.speed),
    }
    headers = _build_headers(auth=args.auth, token=token, accept="audio/*")
    headers["Content-Type"] = "application/json"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    res = _fetch(
        audio_url,
        method="POST",
        headers=headers,
        body=body,
        timeout=float(args.timeout),
        context=context,
    )

    print(f"HTTP: {res.status if res.status is not None else '(no status)'}")
    print(f"Content-Type: {res.content_type or '(missing)'}")
    if res.ok and _looks_like_audio_content_type(res.content_type) and res.body:
        print(f"Result: ✅ looks OpenAI-compatible (received {len(res.body)} bytes audio)")
        print("Hint: in gateway, treat this provider as OpenAI-compatible TTS (/v1/audio/speech).")
        return 0

    payload_json = _try_parse_json_bytes(res.body)
    err_msg = _extract_error_message(payload_json) or (
        res.body.decode("utf-8", errors="replace")[:800] if res.body else None
    )
    if err_msg:
        print("Error excerpt:", err_msg)

    lowered = (err_msg or "").lower()
    if "prompt_audio" in lowered or "prompt audio" in lowered:
        print("Result: ❌ NOT OpenAI-compatible (seems to require reference audio fields like prompt_audio/prompt_audio_url)")
        print("Hint: either exclude this upstream from 'audio' routing, or design an extended gateway API that accepts prompt_audio_url.")
        return 1

    print("Result: ❌ probe failed; upstream likely not OpenAI-compatible or needs different auth/path/fields.")
    print("Hint: provide its OpenAPI spec or docs; then implement a dedicated TTS driver/adapter for this vendor.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


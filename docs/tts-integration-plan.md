# Technical Design Document: TTS/STT Integration (Audio Services)

## 1. Overview

This document outlines the architecture for Text-to-Speech (TTS) and Speech-to-Text (STT) capabilities in the AI Gateway.

**Core Philosophy:** Build general-purpose, OpenAI-compatible backend APIs (`/v1/audio/speech`, `/v1/audio/transcriptions`), and leverage them for "Read Aloud" and voice input features in the frontend chat interface.

> **落地化原则**: 本方案严格对齐现有项目架构，复用 `ProviderSelector`、`key_pool`、鉴权体系等成熟组件。

> **实现状态**: ✅ 已完成核心功能，本文档反映当前实际实现。

## 2. 现有项目架构对齐

### 2.1 后端代码结构
```
backend/app/
├── api/v1/
│   ├── audio_routes.py        # 音频路由 (TTS/STT, API Key鉴权) ✅ 已实现
│   ├── assistant_routes.py    # 助手路由 (JWT鉴权, 含消息朗读) ✅ 已实现
│   └── chat/
│       ├── provider_selector.py  # Provider选择器 (复用)
│       └── routing_state.py      # 路由状态/熔断 (复用)
├── services/
│   ├── tts_app_service.py     # TTS核心服务 (~920行) ✅ 已实现
│   ├── stt_app_service.py     # STT核心服务 ✅ 已实现
│   └── audio_input_service.py # 音频上传/资产服务 ✅ 已实现
├── schemas/
│   ├── audio.py               # TTS Schema ✅ 已实现
│   ├── audio_assets.py        # 音频资产 Schema ✅ 已实现
│   └── audio_uploads.py       # 音频上传 Schema ✅ 已实现
└── models/
    └── audio_asset.py         # 音频资产模型 ✅ 已实现
```

### 2.2 现有鉴权边界
| 入口类型 | 鉴权方式 | 示例路由 | 适用场景 |
|:--------|:--------|:--------|:--------|
| OpenAI兼容网关 | `require_api_key` | `/v1/audio/speech`, `/v1/audio/transcriptions` | 第三方客户端/程序调用 |
| 前端仪表盘/会话 | `require_jwt_token` | `/v1/messages/{id}/speech`, `/v1/conversations/{id}/audio-*` | 浏览器用户操作 |

### 2.3 可复用组件
| 组件 | 位置 | 用途 |
|:-----|:-----|:-----|
| `ProviderSelector` | `api/v1/chat/provider_selector.py` | 多Provider选路、权重、健康检查 |
| `RoutingStateService` | `api/v1/chat/routing_state.py` | 熔断/冷却状态管理 |
| `acquire_provider_key` | `provider/key_pool.py` | 上游API Key轮转获取 |
| `metrics_service` | `services/metrics_service.py` | 指标上报 |
| `credit_service` | `services/credit_service.py` | 额度校验 |

## 3. Security Boundaries

### 3.1 Input Validation
- **Max Input Length:** 4096 characters hard limit (防止DoS和成本失控)
- **Voice Whitelist:** `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`
- **Speed Range:** 0.25 - 4.0 (inclusive)
- **Response Formats:** `mp3`, `opus`, `aac`, `wav`, `pcm`, `ogg`, `flac`, `aiff`
- **Model:** 逻辑模型 ID（不做固定枚举）；需支持 `audio` 能力

### 3.2 Rate Limiting (已实现)
- **Per-User Limit:** 20 requests/minute
- **Global Limit:** 1000 requests/minute across all users
- **实现位置:** `TTSAppService._rate_limit()`

### 3.3 Authentication (双入口)
| 入口 | 鉴权 | 使用场景 |
|:-----|:-----|:--------|
| `POST /v1/audio/speech` | API Key (`require_api_key`) | 第三方客户端、程序调用 |
| `POST /v1/audio/transcriptions` | API Key (`require_api_key`) | 第三方客户端、程序调用 |
| `POST /v1/messages/{id}/speech` | JWT (`require_jwt_token`) | 前端"朗读"按钮 |
| `POST /v1/conversations/{id}/audio-transcriptions` | JWT (`require_jwt_token`) | 前端语音输入 |

## 4. Architecture

### 4.1 Backend (FastAPI) - 已实现

```
┌─────────────────────────────────────────────────────────────────┐
│                         Routes Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  audio_routes.py                 │  assistant_routes.py          │
│  POST /v1/audio/speech           │  POST /v1/messages/{id}/speech│
│  POST /v1/audio/transcriptions   │  POST /v1/conversations/      │
│  [API Key Auth]                  │       {id}/audio-transcriptions│
│                                  │  [JWT Auth]                   │
└──────────────┬───────────────────┴──────────────┬───────────────┘
               │                                   │
               ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TTSAppService (~920行)                         │
├─────────────────────────────────────────────────────────────────┤
│  1. preprocess_text()        - Markdown/HTML清理                 │
│  2. _rate_limit()            - Redis速率限制                     │
│  3. ProviderSelector         - 选路 (ModelCapability.AUDIO)      │
│  4. RoutingStateService      - 熔断/冷却检测                     │
│  5. acquire_provider_key     - 获取上游API Key                   │
│  6. stream_speech()          - 候选循环 + 上游调用               │
│  7. generate_speech_bytes()  - 完整音频生成（避免流式200问题）    │
│  8. Redis缓存 + Lock         - 防重复生成 + 7天TTL               │
│  9. record_metrics()         - 指标上报                          │
├─────────────────────────────────────────────────────────────────┤
│                   Provider Adapters (内嵌)                       │
├─────────────────────────────────────────────────────────────────┤
│  _call_openai_compatible_tts()  │  _call_gemini_tts()            │
│  - 流式 HTTP 调用               │  - generateContent API         │
│  - 支持扩展字段                  │  - Base64 inlineData 解码      │
│  - 自定义 headers               │  - PCM → WAV 封装              │
│                                 │  - Voice 映射                  │
└─────────────────────────────────────────────────────────────────┘
```

**关键设计决策：**

1. **非流式返回 (generate_speech_bytes)**
   - 原因：`StreamingResponse` 会在拉到上游数据前就发送 `200 OK`
   - 若上游随后失败，客户端收到 200 但无音频数据（浏览器播放报 `NotSupportedError`）
   - 采用"先生成再返回"确保失败能正确以 4xx/5xx 响应

2. **参考音频过滤 (_model_requires_reference_audio)**
   - 通过 `provider_models.metadata_json._gateway.tts.requires_reference_audio` 标记
   - 请求无 `reference_audio_url` 时，自动过滤需要参考音频的上游

### 4.2 Frontend (Next.js) - 已实现

```
┌─────────────────────────────────────────────────────────────────┐
│              MessageTtsControl 组件                              │
│  [独立 TTS 控制按钮，支持项目级用户偏好]                          │
└──────────────┬───────────────────────────────────────────────────┘
               │ onClick
               ▼
┌─────────────────────────────────────────────────────────────────┐
│              useMessageSpeechAudio Hook (SWR Mutation)           │
│  - 基于 SWR 的状态管理                                           │
│  - 内存缓存 Map<cacheKey, CachedAudio>                          │
│  - TTL 30分钟 + LRU 32条 + 播放中保护                            │
└──────────────┬───────────────────────────────────────────────────┘
               │ httpClient (JWT)
               ▼
┌─────────────────────────────────────────────────────────────────┐
│              messageService.getMessageSpeechAudio                │
│  POST /v1/messages/{id}/speech → Blob → URL.createObjectURL     │
└─────────────────────────────────────────────────────────────────┘
```

**用户偏好持久化 (useUserPreferencesStore):**
- `preferredTtsModelByProject` - 项目级 TTS 模型
- `preferredTtsFormatByProject` - 项目级音频格式
- `preferredTtsVoiceByProject` - 项目级语音选择
- `preferredTtsSpeedByProject` - 项目级语速
- `selectedVoiceAudioByProject` - 项目级参考音频（语音克隆）
- `speechModeEnabledByProject` - 项目级语音模式开关

### 4.3 文件清单

**后端已实现文件:**
| 文件 | 职责 | 行数 |
|:-----|:-----|:-----|
| `backend/app/api/v1/audio_routes.py` | OpenAI兼容 TTS/STT 路由 | ~90 |
| `backend/app/services/tts_app_service.py` | TTS 核心服务 | ~920 |
| `backend/app/services/stt_app_service.py` | STT 核心服务 | - |
| `backend/app/schemas/audio.py` | TTS Schema | ~75 |
| `backend/app/services/audio_input_service.py` | 音频上传/资产服务 | - |

**前端已实现文件:**
| 文件 | 职责 |
|:-----|:-----|
| `frontend/http/audio.ts` | 音频相关 API 封装 |
| `frontend/http/message.ts` | 消息朗读 API (`getMessageSpeechAudio`) |
| `frontend/lib/swr/use-tts.ts` | TTS Hook (SWR Mutation + 缓存) |
| `frontend/components/chat/message-tts-control.tsx` | TTS 控制组件 |
| `frontend/lib/stores/user-preferences-store.ts` | 用户偏好持久化 |

## 5. API Specification

### 5.1 TTS - OpenAI兼容端点 (API Key)

```http
POST /v1/audio/speech
Authorization: Bearer <api_key>
Content-Type: application/json
```

**Request Body (已实现):**
```json
{
  "model": "string",
  "input": "The text to generate audio for.",
  "voice": "alloy",
  "response_format": "mp3",
  "speed": 1.0,
  "instructions": "Speak cheerfully",
  "input_type": "text",
  "locale": "zh-CN",
  "pitch": 1.0,
  "volume": 1.0,
  "reference_audio_url": "https://..."
}
```

**字段说明:**
| Field | Type | Required | Default | Description |
|:------|:-----|:--------:|:--------|:------------|
| `model` | string | ✅ | - | 逻辑模型 ID（需支持 `audio` 能力） |
| `input` | string | ✅ | - | 要生成语音的文本（最大 4096 字符） |
| `voice` | string | ❌ | `alloy` | 语音选项 |
| `response_format` | string | ❌ | `mp3` | 输出格式 |
| `speed` | float | ❌ | `1.0` | 语速（0.25-4.0） |
| `instructions` | string | ❌ | - | 语气/情感指令（部分上游支持） |
| `input_type` | string | ❌ | `text` | `text` 或 `ssml` |
| `locale` | string | ❌ | - | 语言/地区（如 `zh-CN`） |
| `pitch` | float | ❌ | - | 音高（语义取决于上游） |
| `volume` | float | ❌ | - | 音量（语义取决于上游） |
| `reference_audio_url` | string | ❌ | - | 参考音频 URL（语音克隆） |

**Response:**
- **Success (200 OK):**
  - `Content-Type`: `audio/mpeg` (或对应格式)
  - Body: 完整二进制音频数据

- **Error Responses:**
  - `400 Bad Request`: Invalid input / 模型不支持 audio 能力 / 缺少 reference_audio_url
  - `401 Unauthorized`: Invalid API Key
  - `402 Payment Required`: 额度不足
  - `403 Forbidden`: 无可用提供商
  - `413 Request Entity Too Large`: 音频输出过大
  - `429 Too Many Requests`: Rate limit exceeded
  - `503 Service Unavailable`: All providers failed

### 5.2 TTS - 会话内朗读端点 (JWT)

```http
POST /v1/messages/{message_id}/speech
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "model": "logical-model-id",
  "voice": "alloy",
  "response_format": "mp3",
  "speed": 1.0
}
```

| Field | Type | Required | Default | Description |
|:------|:-----|:--------:|:--------|:------------|
| `model` | string | ❌ | 会话默认 | 逻辑模型 ID（为空则跟随会话 assistant 默认） |
| `voice` | string | ❌ | `alloy` | 语音选项 |
| `response_format` | string | ❌ | `mp3` | 输出格式 |
| `speed` | float | ❌ | `1.0` | 语速 |

### 5.3 STT - OpenAI兼容端点 (API Key)

```http
POST /v1/audio/transcriptions
Authorization: Bearer <api_key>
Content-Type: multipart/form-data
```

**Form Fields:**
| Field | Type | Required | Description |
|:------|:-----|:--------:|:------------|
| `file` | binary | ✅ | 音频文件 |
| `model` | string | ✅ | 逻辑模型 ID |
| `language` | string | ❌ | 语言代码 |
| `prompt` | string | ❌ | 上下文提示 |

**Response:**
```json
{
  "text": "Transcribed text content"
}
```

### 5.4 STT - 会话内语音输入 (JWT)

```http
POST /v1/conversations/{conversation_id}/audio-transcriptions
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data
```

## 6. Implementation Details

### 6.1 Provider 适配器

**OpenAI 兼容 (`_call_openai_compatible_tts`):**
- 标准 `/v1/audio/speech` 端点
- 流式 HTTP 响应
- 支持扩展字段（非官方 OpenAI 时）：`locale`, `pitch`, `volume`, `reference_audio_url`

**Gemini (`_call_gemini_tts`):**
- `generateContent` API + `responseModalities: ["AUDIO"]`
- Base64 `inlineData` 解码
- Voice 映射：`alloy` → `Charon`, `echo` → `Enceladus`, etc.
- PCM → WAV 封装（当 `mimeType` 为 `audio/L16` 时）
- 不做转码，格式不匹配时返回 400

```python
_GEMINI_VOICE_MAPPING = {
    "alloy": "Charon",
    "echo": "Enceladus",
    "fable": "Fenrir",
    "onyx": "Orus",
    "nova": "Puck",
    "shimmer": "Zephyr",
}
```

### 6.2 缓存策略 (已实现)

**后端 Redis 缓存:**
- TTL: 7 天 (`_CACHE_TTL_SECONDS = 7 * 24 * 3600`)
- 最大缓存体积: 4MB (`_MAX_CACHE_BYTES = 4 * 1024 * 1024`)
- 可缓存格式: `mp3`, `aac`, `opus`, `wav`, `ogg`, `flac`, `aiff`, `pcm`
- 防重复生成锁: `SET NX` + 60s TTL
- Cache Key 包含: `user_id`, `model`, `voice`, `speed`, `response_format`, `input_type`, `locale`, `pitch`, `volume`, `reference_audio_hash`, `text_hash`

**前端内存缓存 (use-tts.ts):**
- 最大条目: 32 (`AUDIO_CACHE_MAX_ITEMS`)
- TTL: 30 分钟 (`AUDIO_CACHE_TTL_MS`)
- 播放中保护: 当前播放的音频不会被 LRU 淘汰
- Cache Key: `msg:{messageId}|m:{model}|v:{voice}|f:{format}|s:{speed}|pa:{promptAudioId}`

### 6.3 熔断与失败处理

- `RoutingStateService.get_failure_cooldown_status()` 检测冷却状态
- `RoutingStateService.increment_provider_failure()` 记录失败
- `RoutingStateService.clear_provider_failure()` 成功后清除
- `record_key_failure()` / `record_key_success()` API Key 级别追踪

### 6.4 指标上报

每次调用记录:
- `provider_id`, `logical_model`, `transport`
- `is_stream`, `success`, `latency_ms`, `status_code`
- `user_id`, `api_key_id`

## 7. Risks & Mitigation

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| **High Cost** | TTS ~$15/1M chars | Redis 缓存 7 天 TTL；速率限制 20 req/min；最大 4096 字符 |
| **Latency** | 音频生成慢 | 前端 loading 状态；后端缓存复用 |
| **Mobile Auto-play** | iOS 阻止自动播放 | 仅用户点击触发；使用 `<audio>` 元素 |
| **Markdown in Text** | AI 输出含格式 | `preprocess_text()` 多阶段正则清理 |
| **Cache Pollution** | 恶意填充缓存 | `user_id` 隔离；TTL 自动过期；体积上限 |
| **Concurrent Requests** | 重复生成 | Redis `SET NX` 锁 60s |
| **Provider Failure** | 单 provider 故障 | `ProviderSelector` 候选循环；熔断冷却 |
| **Gemini Format** | PCM/WAV 格式差异 | MIME 解析 + PCM→WAV 封装；不做转码 |
| **上游 200 后失败** | 流式已发 200 | `generate_speech_bytes()` 完整生成后再返回 |

## 8. Execution Checklist

| # | Task | Status |
|:-:|:-----|:------:|
| 1 | 标记 TTS 模型 capability=audio | ✅ |
| 2 | `schemas/audio.py` (扩展字段) | ✅ |
| 3 | `TTSAppService` (920行) | ✅ |
| 4 | `audio_routes.py` - TTS (API Key) | ✅ |
| 5 | `audio_routes.py` - STT (API Key) | ✅ |
| 6 | `/v1/messages/{id}/speech` (JWT) | ✅ |
| 7 | 路由注册 `routes.py` | ✅ |
| 8 | 前端 `http/audio.ts` | ✅ |
| 9 | 前端 `use-tts.ts` (SWR + 缓存) | ✅ |
| 10 | 前端 `MessageTtsControl` 组件 | ✅ |
| 11 | 前端用户偏好持久化 | ✅ |
| 12 | 后端 Redis cache + lock | ✅ |
| 13 | Metrics integration | ✅ |
| 14 | OpenAI Provider 适配 | ✅ |
| 15 | Gemini Provider 适配 (PCM→WAV) | ✅ |
| 16 | 参考音频过滤选路 | ✅ |
| 17 | 会话内语音转文字 | ✅ |

## 9. Provider API Reference

### 9.1 OpenAI TTS API

> 官方文档: https://platform.openai.com/docs/api-reference/audio/createSpeech

**Endpoint:**
```http
POST https://api.openai.com/v1/audio/speech
Authorization: Bearer $OPENAI_API_KEY
Content-Type: application/json
```

**Voice Characteristics:**
| Voice | Style |
|:------|:------|
| `alloy` | Neutral |
| `coral` | Warm (推荐) |
| `echo` | Smooth |
| `fable` | Expressive |
| `nova` | Friendly |
| `onyx` | Deep |
| `shimmer` | Clear |

**Pricing:** ~$15 / 1M characters

### 9.2 Google Gemini TTS API

> 官方文档: https://ai.google.dev/gemini-api/docs/speech-generation

**Endpoint:**
```http
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
x-goog-api-key: $GEMINI_API_KEY
Content-Type: application/json
```

**网关 Voice 映射:**
| OpenAI Voice | Gemini Voice |
|:-------------|:-------------|
| `alloy` | `Charon` |
| `echo` | `Enceladus` |
| `fable` | `Fenrir` |
| `onyx` | `Orus` |
| `nova` | `Puck` |
| `shimmer` | `Zephyr` |

**格式处理:**
- `audio/wav` → 直接返回
- `audio/L16;rate=24000` → 封装 WAV 头后返回
- 其他格式 → 要求与 `response_format` 匹配

## 10. Architecture Comparison

### 当前实现 vs 专业级微内核架构

| 维度 | 当前实现 | 专业级 (六边形) |
|:-----|:---------|:----------------|
| **领域模型** | ❌ 直接使用 DTO | ✅ 独立 domain 层 |
| **端口定义** | ❌ 无显式接口 | ✅ `VoiceProvider` 接口 |
| **适配器隔离** | ⚠️ 内嵌于 Service | ✅ 独立 adapter 包 |
| **插件注册** | ❌ 硬编码分支 | ✅ `init()` 自注册 |
| **熔断器** | ✅ `RoutingStateService` | ✅ 独立熔断组件 |
| **合约测试** | ❌ 无 | ✅ Consumer-Driven |

**演进建议:** 当前架构适合 2-3 个 OpenAI 兼容厂商。若需接入阿里云 NLS、腾讯云 TTS 等非 OpenAI 协议厂商，建议提取适配器层。

## 11. Future Expansion

- [ ] **Auto-play**: 设置中的自动朗读新消息开关
- [x] **Speech-to-Text (STT)**: `/v1/audio/transcriptions` + 会话内语音输入
- [ ] **Custom Voices**: OpenAI 自定义语音 API
- [ ] **Multi-Speaker**: Gemini 多人对话场景
- [ ] **Voice Cloning**: 完善参考音频上传流程
- [ ] **实时语音对话**: WebSocket + 流式 TTS/STT

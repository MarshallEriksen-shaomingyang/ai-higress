# TTS 跨厂商参数画像（用于网关统一语义与适配层设计）

目标：在不把厂商 DTO 泄露到业务层的前提下，定义一套“尽可能覆盖多数厂商”的 **统一 TTS 语义参数集合**，并为后续的“配置驱动通用适配器（GenericAdapter）+ 少量手写适配器”提供依据。

本仓库当前已实现的 TTS API（现状）见：
- `docs/api/API_Documentation.md` → 音频（TTS）
- `backend/app/schemas/audio.py`（`SpeechRequest` / `MessageSpeechRequest`）
- `backend/app/services/tts_app_service.py`（上游调用与兼容策略）

---

## 1. 现状：网关当前已支持的统一参数（已落地）

当前网关对外支持的字段（与 OpenAI `/v1/audio/speech` 兼容）：
- `model`：逻辑模型 ID（网关选路）
- `input`：要合成的文本
- `voice`：音色（枚举）
- `response_format`：输出格式（枚举：`mp3|opus|aac|wav|pcm|ogg|flac|aiff`）
- `speed`：语速（0.25-4.0）
- `instructions`：可选语气/情感指令（部分上游可用）

这套参数对“纯文本合成”的厂商覆盖率很高，但对以下场景不够：
- 厂商要求 SSML 作为输入（或 SSML 才能表达 style/prosody）
- 厂商把输出配置放在 header/query（而非 JSON body）
- 厂商需要“参考音频/音色克隆”的必填字段（例如 `prompt_audio_url` 类）
- 厂商支持更细的 prosody/音频配置（pitch/volume/sample_rate/bitrate/音效 profile/词典等）

---

## 2. 跨厂商常见参数分类（建议纳入统一语义的候选集）

说明：下面是“统一语义候选集（未来扩展）”，并不代表当前 API 已支持；是否落地由你们的产品定位决定。

### A. 输入（Input）
- `text`：纯文本
- `ssml`：SSML 文本（XML）
- `input_type`：`text|ssml`（可选，若 `ssml` 非空可推断）
- `locale` / `language`：语言/地区（例如 `zh-CN`）
- `lexicons` / `pronunciation_dictionaries`：发音词典/自定义词典引用
- `context_before` / `previous_text`、`context_after` / `next_text`：跨分段合成时的上下文（用于 prosody 连贯）

### B. 音色（Voice）
- `voice_id`：音色 ID（强推荐：网关内部使用稳定 ID，映射到厂商 voice）
- `voice_name`：音色名称（部分厂商用 name 而非 id）
- `gender`：`male|female|neutral`（当厂商支持按性别筛选 voice）
- `style` / `emotion`：风格/情绪（如 `newscast|cheerful|sad`）

### C. Prosody（语音韵律）
- `rate`：语速（倍率或区间）
- `pitch`：音高（半音或区间）
- `volume`：音量（dB 或 0-100）
- `pause` / `breaks`：停顿控制（更适合用 SSML 表达）

### D. 输出音频（Audio Output）
- `format` / `audio_encoding`：`mp3|wav|pcm|ogg|opus|aac|flac|aiff|…`
- `sample_rate_hz`
- `bitrate_kbps`
- `channels`
- `effects_profile`：音效 profile / 播放设备 profile
- `speech_marks` / `timestamps`：字/词/句时间戳、viseme（口型）等

### E. 确定性/复现与质量（QoS）
- `seed`：可选随机种子（非强保证）
- `latency_optimization_level`：延迟/质量权衡档位（常见于实时语音平台）

### F. 参考音频/音色克隆（Reference Audio / Voice Clone）
这是你们遇到 “`prompt_audio_url` 必填” 的根因：部分厂商的 TTS 并非“纯文本合成”，而是“带参考音频的风格/音色迁移”。

统一语义建议：
- `reference_audio_url`（URL）
- `reference_audio_base64`（base64）
- `speaker_id` / `voice_clone_id`（厂商侧已训练好的 voice id）

网关需要明确策略：
- 如果你们 **不打算** 对外暴露参考音频能力，那么这类厂商只能被标记为“不支持 OpenAI-compatible TTS”，并从 TTS 路由候选中剔除。
- 如果你们 **要覆盖多数厂商**，那就必须在统一语义里纳入 reference audio（哪怕是可选字段），并让路由层在缺参时拒绝选路到该类 driver。

---

## 3. 代表性厂商参数对照（用于统一语义取舍）

这里列出“字段长得不一样，但语义可归一”的典型例子（便于你们确认统一参数集合）。

### OpenAI（`/v1/audio/speech`）
来源：`https://platform.openai.com/docs/guides/text-to-speech`
- 输入：`input`（text）
- 音色：`voice`（内置 voice 或自建 voice id）
- 输出：支持多种 `response_format`（默认 mp3）
- 控制：`instructions`（语气/情感等）、部分实现有 `speed`

### Google Cloud Text-to-Speech（REST）
来源：`https://cloud.google.com/text-to-speech/docs/reference/rest/v1beta1/AudioConfig`
- 输出配置集中在 `audioConfig`：
  - `audioEncoding`
  - `speakingRate`
  - `pitch`
  - `volumeGainDb`
  - `sampleRateHertz`
  - `effectsProfileId[]`

### Azure Speech（REST，SSML 驱动）
来源：`https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech`
- 输入：通常为 `application/ssml+xml`（SSML）
- 输出格式：常通过请求头选择（例如 `X-Microsoft-OutputFormat`）
- 音色/风格：SSML 中 `<voice name="...">` + `mstts:express-as` 等扩展

### AWS Polly（`SynthesizeSpeech`）
来源：`https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html`
- 输入：`Text` + `TextType`（`text|ssml`）
- 音色：`VoiceId`，双语 voice 可配 `LanguageCode`
- 输出：`OutputFormat` + 可选 `SampleRate`
- 词典：`LexiconNames`
- 时间戳/标注：`SpeechMarkTypes`（word/sentence/viseme/…）

### ElevenLabs（`/v1/text-to-speech/{voice_id}`）
来源：`https://elevenlabs-sdk.mintlify.app/api-reference/text-to-speech`
- 输入：`text`
- 音色：`voice_id`（path 参数）
- 控制：
  - `voice_settings`：`stability` / `similarity_boost` / `style` / `use_speaker_boost`
  - `seed`
  - `previous_text` / `next_text` / `previous_request_ids` / `next_request_ids`
  - `pronunciation_dictionary_locators`
- 输出：`output_format`（query 参数，包含采样率/码率组合）

### 国内/多云常见差异点（不逐字列字段，先抽象语义）
这类厂商的“字段名”差异往往比云厂商更大（有的走 WebSocket/二进制协议、有的把输出格式放 header 或 query），但语义通常仍可落到第 2 节的分类里：

- **输入**：`text`/`input`/`prompt`/`ssml`（部分厂商强依赖 SSML 才能表达 style/prosody）
- **音色**：`voice`/`voice_id`/`speaker`/`spk_id`（常见“平台侧音色列表”与“自定义音色/克隆音色 id”并存）
- **输出**：`format`/`encoding`/`sample_rate`/`bitrate`（不少厂商把采样率作为 format 的一部分）
- **韵律/风格**：`speed`/`rate`/`pitch`/`volume`/`emotion`/`style`
- **参考音频/克隆**：`prompt_audio`/`prompt_audio_url`/`ref_audio_url`/`clone_id`

建议把你们实际要接入的国内厂商列为“探针名单”，用 `scripts/discover_tts_adapter.py` 先探测：
1) 是否存在 OpenAPI（能直接推断 required/properties）
2) OpenAI-compatible payload 是否能直接返回音频
3) 错误信息是否提示必填字段（例如 `prompt_audio_url`）

---

## 4. 建议：网关“统一语义”如何定（满足多数厂商，同时保持强合约）

建议把统一语义拆成三层（强合约由内到外递增）：

1) **Core（必须）**：任何厂商都应能落地
   - `text`（或 `input`）
   - `voice_id`（或 `voice`）
   - `format`（至少 `mp3`）

2) **Standard（推荐）**：主流云厂商都有对应语义
   - `input_type`（text/ssml）
   - `locale`
   - `rate`、`pitch`、`volume`
   - `sample_rate_hz`
   - `lexicons/pronunciation_dictionaries`

3) **Advanced（可选）**：覆盖新一代“生成式 TTS/克隆/实时”
   - `style/emotion`
   - `reference_audio_url` / `reference_audio_base64` / `voice_clone_id`
   - `seed`
   - `latency_optimization_level`
   - `speech_marks/timestamps`

落地时建议保留一个 `extensions`（厂商扩展字段容器）来容纳少量不可归一字段，但必须：
- 强约束白名单（不能把它做成“任意透传 JSON”）
- 仅在特定 provider driver 中解析

---

## 5. 本项目参数确认建议（面向“专业聚合网关”的最小可行超集）

你们现在的对外合约已经是 OpenAI-compatible（`SpeechRequest`），建议保持它稳定；要覆盖更多厂商时，优先做“**可选扩展**”而不是破坏性改名。

建议的统一语义演进顺序：
1) **保持现有字段**：`model/input/voice/response_format/speed/instructions`（已覆盖大量“纯文本合成”厂商）
2) **优先补齐 Standard**：`input_type(text|ssml)`、`locale`、`pitch`、`volume`、`sample_rate_hz`（多数云厂商可映射）
3) **再引入 reference audio**（可选但强烈建议纳入统一语义）：`reference_audio_url` / `reference_audio_base64` / `voice_clone_id`  
   - 这一步能解决你们遇到的 `prompt_audio_url` 必填类上游
   - 路由层可基于“能力 + 缺参”做硬拒绝，避免选路到不兼容上游后才 400/503

如果短期不想扩 API 字段，也可以采取折中策略：
- 在 provider 配置里标记该上游 “requires_reference_audio=true”
- 当请求不带 reference audio 时，直接从候选中剔除该上游（避免无意义重试/Failover）

---

## 6. 下一步落地建议（不依赖“手写 50 个 adapter”）

1) 先做 **TTS 协议探针/兼容性爬虫**：对每个 provider 识别是否 OpenAI-compatible、是否需要 reference audio、输出格式如何选（body/header/query），并把结果写到报告（JSON/YAML）。
2) 再做 **GenericAdapter**：读取映射配置生成上游请求；少量“怪厂商”再用手写 adapter。
3) 用 **Golden Dataset 测试**（先比 Pact 更快落地）：只测“请求体/headers 构建正确性”和“缺参时的错误提示一致性”。

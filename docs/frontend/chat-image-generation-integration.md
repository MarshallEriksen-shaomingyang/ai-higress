# Chat 页面文生图接入设计（统一输入框）

## 目标

在不新增独立页面的前提下，把“文生图”能力接入现有 Chat 页面，并满足以下体验要求：

- 统一入口：仍在 Chat 页面的输入框中发起（默认聊天，用户可切换为文生图模式）。
- 过程态反馈：文生图生成中在对话流里展示骨架屏/进度条；完成后直接渲染图片消息。
- 详情与微调：点击图片打开详情 Modal/侧边栏，提供“查看 Prompt 参数/下载/重绘(In-paint)/变体(Variation)”等动作入口（未实现的后端能力先灰置）。

> UI/组件规范：遵循 `ui-prompt.md`；交互组件优先使用 `frontend/components/ui/*`（shadcn 风格组件），避免在页面里直接堆原生标签。

---

## 现状与依赖（后端能力）

### 1) 文生图 API（固定 OpenAI Images 格式）

- 路由：`POST /v1/images/generations`（实现位置：`backend/app/api/v1/image_routes.py`）
- 处理逻辑：`backend/app/services/image_app_service.py`
  - OpenAI lane：调用 OpenAI-compatible Provider 的 images/generations
  - Google lane：调用 Gemini Developer API `v1beta/{model}:generateContent` 并转换为 OpenAI Images 响应

请求/响应 schema（后端源）：`backend/app/schemas/image.py`

补充：当调用方请求 `response_format="url"` 时：
- 若配置了对象存储（`IMAGE_STORAGE_PROVIDER` + `IMAGE_OSS_*`，默认阿里 OSS，也可 S3/R2 兼容），网关会返回 `/media/images/...` 形式的签名短链 URL（无需登录/无需 API Key）；
- 若未配置 OSS，网关会退化为 `data:image/...;base64,...` 的 Data URL（前端可直接渲染）。

### 2) 模型能力（capabilities）

文生图能力以 `image_generation` 表示：

- 后端枚举：`backend/app/schemas/model.py` 的 `ModelCapability.IMAGE_GENERATION`
- 前端类型：`frontend/lib/api-types.ts` 的 `ModelCapability` union

动态逻辑模型能力合并逻辑：`backend/app/services/chat_routing_service.py` 中 `_build_dynamic_logical_model_for_group` 会把 `/models` 缓存中的 `capabilities` 合并进 LogicalModel，以便前端展示/筛选。

---

## 核心交互：同一输入框 + 两种发送意图

### 1) 模式切换

输入框维持一个轻量状态 `composerMode`：

- `chat`（默认）：发送到 `POST /v1/chat/completions`（现有逻辑）
- `image`（文生图）：发送到 `POST /v1/images/generations`

切换入口：

- 输入框右侧 `+` 菜单，包含 `文生图` 选项（显式切换）
- 可选：对“画/生成图片/画一张…”等明显意图文本做轻提示（不自动切换，只提供“一键切到文生图”的提示条）

关键约束：

- 切换的是“本次发送的意图”，不是切换会话的默认聊天模型。
- 退出文生图模式可以保留用户上次选择的图片参数（便于连续出图），但不应影响聊天模式的默认模型选择。

### 2) 文生图模式参数条（输入框上方一行）

参数条只放高频且不扰民的选项，建议最小集合：

- 图片模型（仅展示 `capabilities` 包含 `image_generation` 的模型）
- 尺寸/长宽比（发送到后端 `size` 字段；建议以少量预设保证兼容）
- 数量 `n`

其余高级参数（例如 `output_format/quality/background/moderation` 等）放在“图片详情 Modal -> 参数”里查看与二次生成。

### 3) 发送与对话流呈现

发送文生图时，在对话流插入一条“图片生成中”消息（过程态）：

- 状态：`pending` -> `succeeded` / `failed`
- `pending`：骨架屏 + 文案（例如“生成中…”）+ 取消/重试按钮（取消可先做前端取消请求，后端不支持时仅停止等待）
- `succeeded`：图片卡片（支持多图：网格/轮播），并显示一个最小的元信息（model、size、n，可放在 hover/详情页）
- `failed`：错误提示 + 重试（保持原 prompt 与参数）

> 说明：当前后端 `POST /v1/images/generations` 为非流式响应；前端的“进度条”应视为过程态 UI（可用 indeterminate），不要假设后端会推送真实进度。

---

## 前端数据结构建议（消息级别模型）

为了不影响现有 chat 消息结构，建议新增一种“图片消息”类型（仅前端展示层使用；是否持久化由后续决定）：

```ts
type ChatComposerMode = "chat" | "image";

type ImageGenParams = {
  model: string;
  size?: string;
  n?: number;
  response_format?: "url" | "b64_json";
  // 可选：quality/background/output_format 等
};

type ImageGenMessage = {
  kind: "image_generation";
  id: string;
  createdAt: number;
  status: "pending" | "succeeded" | "failed";
  prompt: string;
  params: ImageGenParams;
  images?: Array<{ url?: string; b64_json?: string; revised_prompt?: string }>;
  error?: string;
};
```

这条消息在 `pending` 时就应进入消息列表，成功后原位更新（避免“先无，再突然出现”的跳动）。

---

## API 调用与 SWR Hook 设计

### 1) 统一走 SWR 封装，不直接裸 fetch

前端应复用 `frontend/lib/swr/hooks.ts` 的 `useApiPost`（避免组件内直接 `fetch/axios`）。

建议新增一个领域 Hook：

- 文件建议：`frontend/lib/swr/use-image-generations.ts`
- 形态：`useApiPost<ImageGenerationResponse, ImageGenerationRequest>("/v1/images/generations")`

类型建议在 `frontend/lib/api-types.ts` 补齐与后端一致的：

- `ImageGenerationRequest` / `ImageGenerationResponse`
- 与后端源对齐：`backend/app/schemas/image.py`

### 2) 模型列表与能力筛选

图片模型列表的来源建议是“逻辑模型列表”，而不是 `/v1/models`（后者只给 id 列表，无能力信息）：

- 现有逻辑模型接口与类型：`frontend/lib/swr/use-logical-models.ts` + `frontend/lib/api-types.ts` 的 `LogicalModel`
- 筛选：`logicalModel.capabilities.includes("image_generation")`

---

## 图片详情 Modal/侧边栏（点击图片触发）

点击图片卡片打开详情容器（`Dialog` 或 `Sheet`），包含：

1) 预览
   - 放大查看、切换多图（如果 `n > 1`）
2) Prompt & 参数
   - 展示本次 `prompt/模型/尺寸/n/其它参数`
   - 支持一键复制（prompt / JSON 参数）
3) 操作
   - 下载（支持 data URL 或 base64 解码下载）
   - 以当前参数“再次生成”（回到生成流程）
   - 重绘(In-paint) / 变体(Variation)
     - MVP：只放入口并灰置（提示“后端暂未启用”）
     - 后续：等后端实现 `images/edits` / `images/variations` 再点通

可选增强（与 chat 联动）：

- 若当前聊天模型支持 `vision`（`capabilities.includes("vision")`），提供“把这张图作为下一条对话输入”的按钮：自动在下一条用户消息插入 `image_url`（data URL）。

---

## MVP 开发清单（建议顺序）

1) 在 Chat 输入区引入 `composerMode` 与 `+` 菜单“文生图”
2) 添加文生图模式参数条（模型/尺寸/n）
3) 新增 `use-image-generations` Hook（`/v1/images/generations`）
4) 对话流插入 `pending` 图片消息 + 成功渲染图片卡片 + 失败重试
5) 图片详情 Modal：预览 + 参数展示 + 下载
6) i18n：新增 chat 文生图相关 key（文件建议：`frontend/lib/i18n/chat.ts`）

---

## 验收标准

- 用户在 Chat 输入框输入 prompt，切到“文生图”后发送，可在对话流中看到生成过程态与最终图片。
- 图片模型仅显示具备 `image_generation` 能力的模型；发送时不会影响聊天模式默认模型。
- 点击图片打开详情 Modal，能查看 prompt/参数并下载图片；未实现的“重绘/变体”有清晰的禁用提示。

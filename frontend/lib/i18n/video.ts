import type { Language } from "../i18n-context";

/**
 * 视频生成页面国际化文案
 */
export const videoTranslations: Record<Language, Record<string, string>> = {
  en: {
    // ===== Page Title =====
    "video.title": "Video Generation",
    "video.subtitle": "Create AI-generated videos from text descriptions",

    // ===== Main Content =====
    "video.placeholder": "Describe your video and click Generate",
    "video.input_placeholder": "Describe the video you want to create...",
    "video.generate": "Generate",
    "video.cancel": "Cancel",
    "video.using_model": "Using {model}",
    "video.keyboard_hint": "Press",
    "video.keyboard_hint_to_generate": "to generate",

    // ===== Progress Status =====
    "video.status.creating": "Creating task...",
    "video.status.queued": "Waiting in queue...",
    "video.status.running": "Generating video...",
    "video.status.complete": "Complete!",
    "video.status.failed": "Failed",

    // ===== Aspect Ratio =====
    "video.aspect_ratio.landscape": "Landscape 16:9",
    "video.aspect_ratio.portrait": "Portrait 9:16",
    "video.aspect_ratio.square": "Square 1:1",

    // ===== Advanced Settings Sheet =====
    "video.settings.title": "Advanced Settings",
    "video.settings.description": "Configure video generation parameters",
    "video.settings.tooltip": "Advanced Settings",

    // Model Selection
    "video.settings.model": "Model",
    "video.settings.model_placeholder": "Select a model",

    // Resolution
    "video.settings.resolution": "Resolution",
    "video.settings.resolution_480p": "480p (SD)",
    "video.settings.resolution_720p": "720p (HD)",
    "video.settings.resolution_1080p": "1080p (FHD)",

    // Duration
    "video.settings.duration": "Duration",
    "video.settings.duration_value": "{seconds}s",

    // Frame Rate
    "video.settings.fps": "Frame Rate",
    "video.settings.fps_value": "{fps} FPS",

    // Seed
    "video.settings.seed": "Seed (optional)",
    "video.settings.seed_placeholder": "Random",
    "video.settings.seed_hint": "Use same seed for reproducible results",
    "video.settings.seed_random": "Generate random seed",

    // Negative Prompt
    "video.settings.negative_prompt": "Negative Prompt",
    "video.settings.negative_prompt_placeholder": "Things to avoid in the video...",

    // Enhance Prompt
    "video.settings.enhance_prompt": "Enhance Prompt",
    "video.settings.enhance_prompt_hint": "AI will improve your prompt for better results",

    // Generate Audio
    "video.settings.generate_audio": "Generate Audio",
    "video.settings.generate_audio_hint": "Add AI-generated sound effects",

    // Reset
    "video.settings.reset": "Reset to Defaults",

    // ===== Filmstrip =====
    "video.filmstrip.empty": "No videos generated yet",
    "video.filmstrip.generating": "Generating...",
    "video.filmstrip.failed": "Failed",
    "video.filmstrip.recent": "Recent",
    "video.filmstrip.clear_all": "Clear all",
    "video.filmstrip.clear_all_tooltip": "Clear all history",
    "video.filmstrip.status_generating": "generating",
    "video.filmstrip.status_failed": "failed",
    "video.filmstrip.status_pending": "pending",

    // ===== Errors =====
    "video.error.no_prompt": "Please enter a description",
    "video.error.no_model": "Please select a model",
    "video.error.generation_failed": "Video generation failed",
    "video.error.cancelled": "Cancelled by user",
  },
  zh: {
    // ===== 页面标题 =====
    "video.title": "视频生成",
    "video.subtitle": "通过文字描述创建 AI 生成视频",

    // ===== 主要内容 =====
    "video.placeholder": "描述您想要的视频并点击生成",
    "video.input_placeholder": "描述您想要创建的视频...",
    "video.generate": "生成",
    "video.cancel": "取消",
    "video.using_model": "使用 {model}",
    "video.keyboard_hint": "按下",
    "video.keyboard_hint_to_generate": "来生成",

    // ===== 进度状态 =====
    "video.status.creating": "创建任务中...",
    "video.status.queued": "排队等待中...",
    "video.status.running": "视频生成中...",
    "video.status.complete": "完成！",
    "video.status.failed": "失败",

    // ===== 宽高比 =====
    "video.aspect_ratio.landscape": "横屏 16:9",
    "video.aspect_ratio.portrait": "竖屏 9:16",
    "video.aspect_ratio.square": "方形 1:1",

    // ===== 高级设置面板 =====
    "video.settings.title": "高级设置",
    "video.settings.description": "配置视频生成参数",
    "video.settings.tooltip": "高级设置",

    // 模型选择
    "video.settings.model": "模型",
    "video.settings.model_placeholder": "选择模型",

    // 分辨率
    "video.settings.resolution": "分辨率",
    "video.settings.resolution_480p": "480p (标清)",
    "video.settings.resolution_720p": "720p (高清)",
    "video.settings.resolution_1080p": "1080p (全高清)",

    // 时长
    "video.settings.duration": "时长",
    "video.settings.duration_value": "{seconds}秒",

    // 帧率
    "video.settings.fps": "帧率",
    "video.settings.fps_value": "{fps} FPS",

    // 种子
    "video.settings.seed": "种子（可选）",
    "video.settings.seed_placeholder": "随机",
    "video.settings.seed_hint": "使用相同种子可获得可复现的结果",
    "video.settings.seed_random": "生成随机种子",

    // 负面提示词
    "video.settings.negative_prompt": "负面提示词",
    "video.settings.negative_prompt_placeholder": "视频中要避免的内容...",

    // 优化提示词
    "video.settings.enhance_prompt": "优化提示词",
    "video.settings.enhance_prompt_hint": "AI 将改善您的提示词以获得更好的效果",

    // 生成音频
    "video.settings.generate_audio": "生成音频",
    "video.settings.generate_audio_hint": "添加 AI 生成的音效",

    // 重置
    "video.settings.reset": "重置为默认值",

    // ===== 胶片条 =====
    "video.filmstrip.empty": "尚未生成视频",
    "video.filmstrip.generating": "生成中...",
    "video.filmstrip.failed": "失败",
    "video.filmstrip.recent": "最近",
    "video.filmstrip.clear_all": "清空全部",
    "video.filmstrip.clear_all_tooltip": "清空所有历史记录",
    "video.filmstrip.status_generating": "生成中",
    "video.filmstrip.status_failed": "失败",
    "video.filmstrip.status_pending": "等待中",

    // ===== 错误 =====
    "video.error.no_prompt": "请输入描述",
    "video.error.no_model": "请选择模型",
    "video.error.generation_failed": "视频生成失败",
    "video.error.cancelled": "用户已取消",
  },
};

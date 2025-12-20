export interface MessageRenderOptions {
  /**
   * 是否启用 Markdown 渲染（用于文档/表格/代码块等）
   * @default true
   */
  enable_markdown: boolean;
  /**
   * 是否启用数学公式渲染（$...$ / $$...$$）
   * @default true
   */
  enable_math: boolean;
  /**
   * 是否将 <think>...</think> 作为“思维链”折叠展示
   * @default true
   */
  collapse_think: boolean;
  /**
   * <think> 默认是否展开
   * @default false
   */
  default_show_think: boolean;
}

export const DEFAULT_MESSAGE_RENDER_OPTIONS: MessageRenderOptions = {
  enable_markdown: true,
  enable_math: true,
  collapse_think: true,
  default_show_think: false,
};


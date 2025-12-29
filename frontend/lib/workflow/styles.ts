/**
 * 数字水墨 (Digital Ink) 视觉基调
 * 工作流自动化专用样式配置
 */

export const workflowStyles = {
  // 背景色 - 宣纸 (Rice Paper)
  background: {
    paper: 'bg-[#F7F9FB]',
    paperDark: 'dark:bg-slate-900',
  },

  // 卡片 - 白瓷 (Porcelain)
  card: {
    base: 'bg-white/80 backdrop-blur-md border border-white/20 shadow-sm rounded-xl',
    baseDark: 'dark:bg-slate-800/80 dark:border-slate-700/20',
    hover: 'hover:-translate-y-1 transition-all duration-300 ease-out',
    collapsed: 'scale-95 opacity-60 grayscale',
  },

  // 墨色 (Ink)
  ink: {
    title: 'text-slate-800 dark:text-slate-100', // 浓墨
    body: 'text-slate-500 dark:text-slate-400', // 淡墨
    border: 'border-slate-100 dark:border-slate-700',
  },

  // 点睛色 (Glow Dots) - 状态指示器
  status: {
    running: {
      bg: 'bg-blue-400',
      glow: 'shadow-[0_0_8px_rgba(96,165,250,0.6)]',
      ring: 'ring-2 ring-blue-100 dark:ring-blue-900/50',
      badge: 'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800',
    },
    paused: {
      bg: 'bg-orange-400',
      glow: 'shadow-[0_0_8px_rgba(251,146,60,0.6)]',
      ring: 'ring-2 ring-orange-100 dark:ring-orange-900/50',
      badge: 'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800',
    },
    completed: {
      bg: 'bg-emerald-500',
      glow: '',
      ring: '',
      badge: 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800',
    },
    failed: {
      bg: 'bg-red-500',
      glow: 'shadow-[0_0_8px_rgba(239,68,68,0.6)]',
      ring: 'ring-2 ring-red-100 dark:ring-red-900/50',
      badge: 'bg-red-50 text-red-600 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800',
    },
    cancelled: {
      bg: 'bg-slate-400',
      glow: '',
      ring: '',
      badge: 'bg-slate-50 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
    },
    pending: {
      bg: 'bg-slate-300',
      glow: '',
      ring: '',
      badge: 'bg-slate-50 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
    },
  },

  // 输入框 - 纸上书写
  input: {
    title: 'bg-transparent border-none text-2xl font-serif text-slate-800 dark:text-slate-100 placeholder:text-slate-300 dark:placeholder:text-slate-600 focus:outline-none',
    search: 'bg-slate-100 dark:bg-slate-800 rounded-full px-4 py-2 text-sm border-none focus:ring-2 focus:ring-slate-300 dark:focus:ring-slate-600',
  },

  // 按钮
  button: {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white shadow-[0_0_12px_rgba(59,130,246,0.5)] hover:shadow-[0_0_16px_rgba(59,130,246,0.7)] transition-all',
    secondary: 'bg-slate-800 dark:bg-slate-700 hover:bg-slate-900 dark:hover:bg-slate-600 text-white',
    ghost: 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800',
  },

  // 动画
  animation: {
    fadeIn: 'animate-fade-in-up',
    breathe: 'animate-pulse',
    spin: 'animate-spin',
  },

  // 终端/日志窗口
  terminal: {
    container: 'bg-slate-900/5 dark:bg-slate-950/50 rounded-lg p-4 font-mono text-xs leading-relaxed max-h-60 overflow-y-auto border border-slate-200/50 dark:border-slate-700/50',
    text: 'text-slate-600 dark:text-slate-300',
    line: 'border-b border-dashed border-slate-200/30 dark:border-slate-700/30 last:border-0 py-0.5',
  },
} as const;

export type WorkflowStatus = 'running' | 'paused' | 'completed' | 'failed' | 'cancelled' | 'pending';

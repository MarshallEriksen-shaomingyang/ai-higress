# AI Higress 前端设计规范 v2.0：新中式数字水墨 (Digital Ink)

## 1. 核心设计愿景：呼吸感与秩序感

“呼吸感与秩序感” 不仅是极简，更要追求通透。设计不再是简单的黑白线条堆砌，而是通过微妙的光影、磨砂质感和留白，在数字界面中重现水墨晕染的意境。让用户在操作复杂网关数据时，感受到如阅读卷轴般的流畅与宁静。界面应该像一块透明玻璃，让内容自然呈现，而不是阻挡视线的障碍。

## 2. 视觉美学 (Visual Identity)

### 2.1 风格定义：流动的秩序
- **Ink & Glass (水墨与琉璃)**：将中国传统水墨的“虚实结合”与现代 UI 的“毛玻璃 (Glassmorphism)”特效融合。
- **Soft Tech (柔性科技)**：摒弃生硬的纯黑线条，使用低饱和度的深灰与柔和的阴影，打造“高冷但不冰冷”科技感。

### 2.2 色彩体系 (Color Palette)
告别纯黑纯白，引入“纸张”的温度。

- **背景层 (Background)**:
  - App Background: `#F7F9FB` (极淡的冷灰蓝，似晨雾) 或 `#FAFAFA` (米宣纸白，更温润)。
  - Surface: `#FFFFFF` (纯白，用于卡片)。
- **墨色系统 (Ink System)** - 用于文字与图标:
  - Ink Strong: `#1F2937` (浓墨，主要标题)
  - Ink Medium: `#4B5563` (淡墨，正文)
  - Ink Light: `#9CA3AF` (水痕，辅助信息)
- **点缀色 (Accent)**:
  - Digital Blue: `#2563EB` (科技蓝，高亮关键操作，需带微渐变)
  - Zen Red: `#EF4444` (朱砂红，仅用于错误或极其重要的强调，如印章般点缀)

### 2.3 质感与深度 (Texture & Depth)
- **弥散阴影 (Diffuse Shadows)**：放弃锐利的黑色阴影，使用带有色彩倾向的弥散光。
  - *CSS示例*: `box-shadow: 0 4px 20px -2px rgba(37, 99, 235, 0.05);` (带一点点蓝调的灰影)。
- **微磨砂 (Micro-Blur)**：在顶部导航栏和侧边栏使用背景模糊，增加层次感。
  - *CSS*: `backdrop-filter: blur(12px); background: rgba(255, 255, 255, 0.85);`

## 3. 布局与空间 (Layout & Space)

### 3.1 容器美学
- **Bento Grid (便当盒布局)**：仪表盘采用圆角卡片拼接的网格布局，像精致的便当盒一样收纳数据。
- **悬浮感**：卡片不使用明显的边框，而是通过“白色背景 + 极淡阴影”从浅灰色背景中浮起。

### 3.2 留白韵律
- **亲密性原则**：相关元素间距 8px/16px，不同模块间距 32px/48px。
- **版心聚焦**：内容区域限制在 1280px 或 1440px，两侧留出呼吸空间。

## 4. 组件精修 (Component Refinement)

### 4.1 按钮：从“方块”到“触点”
- **主按钮**：使用微弱的垂直渐变（Top: `#2563EB` -> Bottom: `#1D4ED8`），增加立体感。圆角调整为 6px 或 8px。
- **次级按钮**：取消边框，仅使用淡灰色背景 (`#F3F4F6`)，悬停时变深。

### 4.2 表格：数据画卷
- **去线留白**：完全移除表格的纵向分割线。横向分割线使用极细的 `#E5E7EB` 或虚线。
- **悬停高亮**：鼠标滑过某一行时，整行背景轻微变为淡蓝色 (`#EFF6FF`)，左侧出现 3px 宽的蓝色指示条（类似书签）。

### 4.3 输入框：无感交互
- **默认状态**：浅灰色背景 (`#F9FAFB`)，无边框。
- **聚焦状态**：背景变白，出现淡蓝色光晕阴影，而非生硬的黑框。

### 4.4 状态指示
- **Glow Dots (呼吸点)**：使用“发光点”（中心一个小圆点，外围带淡入淡出的不透明度环）代替实心徽章，展现系统的生命感。

## 5. 交互动态 (Motion Design)

- **液体流动**：Tab 切换时，底部的指示条使用 `layoutId` (Framer Motion) 做平滑滑动过渡。
- **按压回弹**：点击卡片或按钮时，元素缩小 2% (`scale: 0.98`)，模拟真实的物理按压感。
- **渐进式入场**：页面加载时，内容卡片按顺序错开 50ms 向上浮动淡入 (Staggered Animation)。

## 6. 性能优化与技术实现

在追求美感的同时，必须保持极高的性能标准：

- **服务端优先**：默认使用 React Server Components，减少客户端 JS 负担。
- **轻量化渲染**：使用 `React.memo` 和 `useMemo` 优化复杂数据的渲染。
- **虚拟滚动**：长列表和大数据表格必须使用虚拟化技术（如 `@tanstack/react-virtual`）。
- **指标目标**：FCP < 1.8s, LCP < 2.5s, 初始 Bundle < 200KB。

## 7. 终极 Prompt (用于 AI 编程助手)

如果你想直接生成代码，请使用以下 Prompt：

> **Role**: Senior Frontend UI/UX Engineer & Designer
> **Project**: AI Higress Intelligent Gateway
> **Design Theme**: "Modern Digital Ink" (Minimalist, Breathable, Sophisticated)
>
> **Task**: Refine the UI implementation to be aesthetically pleasing, not just functional.
>
> **Visual Requirements**:
> - **Palette**: Use a subtle off-white (`#F9FAFB`) for page background. Text should be Slate-800 (primary) and Slate-500 (secondary), avoiding pure black.
> - **Cards & Depth**: Use pure white (`#FFFFFF`) cards with `rounded-xl` (12px). Do not use borders. Instead, use a soft diffuse shadow: `box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 10px 15px -3px rgba(0, 0, 0, 0.04)`.
> - **Glassmorphism**: Apply `backdrop-filter: blur(8px)` and `bg-white/80` to sticky headers and sidebars.
>
> **Data Presentation**:
> - **Tables**: Remove vertical borders. Use generous padding. Add a subtle hover effect (`bg-slate-50`).
> - **Status**: Use "Glow Dots" (a small central dot with a fading opacity ring) instead of solid badges.
>
> **Interactions**:
> - Implement subtle `hover:translate-y-[-2px]` on clickable cards.
> - Use smooth transitions (300ms ease-out).
> - Use Staggered Animation for card entry.

## 8. 避免的设计陷阱

- **生硬感**：避免使用纯黑色边框或纯黑色文字。
- **信息过载**：每个区域保持聚焦，利用留白（White Space）引导用户视线。
- **过度装饰**：虽然追求质感，但不要堆砌复杂的纹理或过度的阴影，保持“通透”。

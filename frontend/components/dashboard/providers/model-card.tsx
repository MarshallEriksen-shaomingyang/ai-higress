"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Model } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";

interface ModelCardProps {
  model: Model;
  canEdit: boolean;
  onEditPricing: () => void;
  onEditAlias: () => void;
}

/**
 * 计费标签组件
 * 显示模型的输入/输出价格，采用简洁的徽章样式
 */
function PricingBadge({ model }: { model: Model }) {
  const { t } = useI18n();
  const pricing = (model.pricing || {}) as Record<string, number>;
  const hasInput = typeof pricing.input === "number";
  const hasOutput = typeof pricing.output === "number";

  if (!hasInput && !hasOutput) {
    return (
      <Badge variant="outline" className="text-xs shrink-0 font-normal">
        {t("providers.model_pricing_not_configured")}
      </Badge>
    );
  }

  // 使用箭头符号表示输入/输出方向
  const label = [
    hasInput && `↓${pricing.input}`,
    hasOutput && `↑${pricing.output}`,
  ]
    .filter(Boolean)
    .join(" / ");

  return (
    <Badge variant="secondary" className="text-xs shrink-0 font-mono font-normal">
      {label}
    </Badge>
  );
}

/**
 * 格式化日期
 */
function formatDate(timestamp?: number): string {
  if (!timestamp) return "-";
  return new Date(timestamp * 1000).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

/**
 * 模型卡片组件
 * 
 * 设计原则：
 * - 极简主义：只显示核心信息，操作按钮悬停时才显示
 * - 墨水风格：细线边框、大量留白、微妙阴影
 * - 清晰层次：主标题 > 模型ID > 元数据 > 操作区
 * - 平滑交互：200ms 过渡动画，轻微上浮效果
 */
export function ModelCard({ model, canEdit, onEditPricing, onEditAlias }: ModelCardProps) {
  const { t } = useI18n();

  return (
    <div
      className="group relative border rounded-lg p-5 transition-all duration-200 
                 hover:border-foreground/20 hover:shadow-sm hover:-translate-y-0.5 
                 bg-card"
    >
      {/* 主标题区：模型名称 + 计费标签 */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <h3 className="font-medium text-base leading-tight break-words flex-1">
          {model.display_name || model.model_id}
        </h3>
        <PricingBadge model={model} />
      </div>

      {/* 模型 ID：小号等宽字体，灰色 */}
      <code className="text-xs text-muted-foreground font-mono block mb-4 break-all">
        {model.model_id}
      </code>

      {/* 元数据区：所有者、创建时间、别名 */}
      <div className="space-y-1.5 text-xs text-muted-foreground">
        <div>
          {t("providers.model_owned_by")}:{" "}
          {model.metadata?.owned_by || "-"}
        </div>
        <div>
          {t("providers.model_created")}:{" "}
          {formatDate(model.metadata?.created)}
        </div>
        {model.alias && (
          <div className="font-mono">
            {t("providers.model_alias")}: {model.alias} → {model.model_id}
          </div>
        )}
      </div>

      {/* 操作区：悬停时显示，使用细分隔线 */}
      <div
        className="mt-4 pt-4 border-t border-border/50 
                   opacity-0 group-hover:opacity-100 
                   transition-opacity duration-200 
                   flex gap-2"
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={onEditPricing}
          className="h-8 text-xs hover:bg-muted"
        >
          {t("providers.model_edit_pricing")}
        </Button>
        {canEdit && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onEditAlias}
            className="h-8 text-xs hover:bg-muted"
          >
            {t("providers.model_edit_alias")}
          </Button>
        )}
      </div>
    </div>
  );
}

import * as React from "react";

interface IntensityCardProps {
  level: 1 | 2 | 3;
  label?: string;
  description?: string;
}

/**
 * 强度展示卡片
 * 用于展示不同强度级别
 */
export function IntensityCard({ level, label, description }: IntensityCardProps) {
  const defaultLabel = label || `Intensity ${level}`;
  const defaultDescription = description || getDefaultDescription(level);

  return (
    <div className="space-y-2 text-center">
      <p className="text-sm text-muted-foreground">{getIntensityLabel(level)}</p>
      <div
        className="text-3xl"
        style={{
          fontWeight: 200,
          color: "#fff1d6",
          textShadow: "0 0 12px rgba(255, 241, 214, 0.25)",
          letterSpacing: "0.5px",
        }}
      >
        {defaultLabel}
      </div>
      <p className="text-xs text-muted-foreground">{defaultDescription}</p>
    </div>
  );
}

function getIntensityLabel(level: 1 | 2 | 3): string {
  switch (level) {
    case 1:
      return "低强度";
    case 2:
      return "中强度（默认）";
    case 3:
      return "高强度";
  }
}

function getDefaultDescription(level: 1 | 2 | 3): string {
  switch (level) {
    case 1:
      return "柔和发光";
    case 2:
      return "标准发光";
    case 3:
      return "强烈发光";
  }
}

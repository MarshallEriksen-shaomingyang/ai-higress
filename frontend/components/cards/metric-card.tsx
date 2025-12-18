import * as React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
}

/**
 * 指标卡片
 * 用于显示简单的指标数据
 */
export function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">{label}</p>
      <div
        className="text-3xl"
        style={{
          fontWeight: 200,
          color: "#fff1d6",
          textShadow: "0 0 12px rgba(255, 241, 214, 0.25)",
          letterSpacing: "0.5px",
        }}
      >
        {value}
      </div>
    </div>
  );
}

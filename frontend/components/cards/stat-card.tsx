import * as React from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  size?: "sm" | "md" | "lg";
}

/**
 * 统计数据卡片
 * 用于显示数字统计信息
 */
export function StatCard({ label, value, subtitle, size = "md" }: StatCardProps) {
  const sizeStyles = {
    sm: "text-3xl",
    md: "text-4xl",
    lg: "text-6xl",
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-white/70">{label}</p>
      <div
        className={`${sizeStyles[size]} tracking-wide`}
        style={{
          fontWeight: 200,
          color: "#fff1d6",
          textShadow: "0 0 15px rgba(255, 241, 214, 0.3)",
          letterSpacing: "1px",
        }}
      >
        {value}
      </div>
      {subtitle && <p className="text-xs text-white/50">{subtitle}</p>}
    </div>
  );
}

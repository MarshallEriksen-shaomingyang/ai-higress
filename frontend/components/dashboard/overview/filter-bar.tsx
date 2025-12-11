"use client";

import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useI18n } from "@/lib/i18n-context";

import { OverviewTimeRange } from "@/lib/swr/use-overview-metrics";

export type TimeRange = OverviewTimeRange;

interface FilterBarProps {
  onTimeRangeChange?: (range: TimeRange) => void;
  onProviderFilterChange?: (providers: string[]) => void;
  onModelFilterChange?: (models: string[]) => void;
}

const TIME_RANGE_OPTIONS: Array<{ value: TimeRange; labelKey: string }> = [
  { value: "today", labelKey: "filter.time_range.today" },
  { value: "7d", labelKey: "filter.time_range.7d" },
  { value: "30d", labelKey: "filter.time_range.30d" },
  { value: "all", labelKey: "filter.time_range.all" },
];

const STORAGE_KEY = "dashboard_overview_time_range";

/**
 * 时间范围筛选器组件
 *
 * 职责：
 * - 提供时间范围选择（today/7d/30d/90d/all）
 * - 支持本地存储状态持久化
 * - 触发父组件的数据更新回调
 *
 * 验证需求：6.1, 6.3
 */
export function FilterBar({
  onTimeRangeChange,
  // onProviderFilterChange,
  // onModelFilterChange,
}: FilterBarProps) {
  const { t } = useI18n();
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [isHydrated, setIsHydrated] = useState(false);

  // 从本地存储恢复时间范围选择
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && isValidTimeRange(saved)) {
        setTimeRange(saved as TimeRange);
      }
    } catch {
      // 忽略存储错误
    }
    setIsHydrated(true);
  }, []);

  // 处理时间范围变化
  const handleTimeRangeChange = (value: string) => {
    if (isValidTimeRange(value)) {
      const newRange = value as TimeRange;
      setTimeRange(newRange);

      // 保存到本地存储
      try {
        window.localStorage.setItem(STORAGE_KEY, newRange);
      } catch {
        // 忽略存储错误
      }

      // 触发回调
      onTimeRangeChange?.(newRange);
    }
  };

  // 避免水合错误
  if (!isHydrated) {
    return (
      <div className="flex items-center gap-4 p-4 bg-background border border-border rounded-lg">
        <div className="h-10 w-32 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between">
      {/* 时间范围选择器 */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground uppercase tracking-wider">
          {t("filter.time_range.label")}
        </span>
        <Select value={timeRange} onValueChange={handleTimeRangeChange}>
          <SelectTrigger className="w-32 h-8 text-sm border-none shadow-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIME_RANGE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {t(option.labelKey)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

/**
 * 验证时间范围值是否有效
 */
function isValidTimeRange(value: unknown): value is TimeRange {
  return (
    typeof value === "string" &&
    ["today", "7d", "30d", "all"].includes(value)
  );
}

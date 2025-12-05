"use client";

import React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useI18n } from "@/lib/i18n-context";

export type DateRangePreset = 'today' | 'week' | 'month' | '7days' | '30days' | 'all';

interface DateRangeFilterProps {
  value: DateRangePreset;
  onChange: (value: DateRangePreset) => void;
  disabled?: boolean;
}

export function DateRangeFilter({
  value,
  onChange,
  disabled = false
}: DateRangeFilterProps) {
  const { t } = useI18n();

  return (
    <Select
      value={value}
      onValueChange={(val) => onChange(val as DateRangePreset)}
      disabled={disabled}
    >
      <SelectTrigger className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="today">{t("credits.filter_today")}</SelectItem>
        <SelectItem value="week">{t("credits.filter_week")}</SelectItem>
        <SelectItem value="month">{t("credits.filter_month")}</SelectItem>
        <SelectItem value="7days">{t("credits.filter_7days")}</SelectItem>
        <SelectItem value="30days">{t("credits.filter_30days")}</SelectItem>
        <SelectItem value="all">{t("credits.filter_all")}</SelectItem>
      </SelectContent>
    </Select>
  );
}

/**
 * 根据预设值计算日期范围
 * @param preset 预设值
 * @returns { start_date, end_date } 或 undefined（表示不筛选）
 */
export function getDateRangeFromPreset(preset: DateRangePreset): {
  start_date?: string;
  end_date?: string;
} {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  
  switch (preset) {
    case 'today': {
      return {
        start_date: today.toISOString(),
        end_date: now.toISOString()
      };
    }
    case 'week': {
      // 本周（周一到现在）
      const dayOfWeek = today.getDay();
      const monday = new Date(today);
      monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));
      return {
        start_date: monday.toISOString(),
        end_date: now.toISOString()
      };
    }
    case 'month': {
      // 本月（1号到现在）
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
      return {
        start_date: firstDay.toISOString(),
        end_date: now.toISOString()
      };
    }
    case '7days': {
      // 最近7天
      const sevenDaysAgo = new Date(today);
      sevenDaysAgo.setDate(today.getDate() - 7);
      return {
        start_date: sevenDaysAgo.toISOString(),
        end_date: now.toISOString()
      };
    }
    case '30days': {
      // 最近30天
      const thirtyDaysAgo = new Date(today);
      thirtyDaysAgo.setDate(today.getDate() - 30);
      return {
        start_date: thirtyDaysAgo.toISOString(),
        end_date: now.toISOString()
      };
    }
    case 'all':
    default:
      // 不筛选
      return {};
  }
}
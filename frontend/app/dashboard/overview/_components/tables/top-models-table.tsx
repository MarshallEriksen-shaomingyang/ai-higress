"use client"

import { AdaptiveCard, CardContent } from "@/components/cards/adaptive-card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { useI18n } from "@/lib/i18n-context"
import type { DashboardV2TopModelItem } from "@/lib/api-types"

interface TopModelsTableProps {
  data: DashboardV2TopModelItem[]
  isLoading: boolean
  error?: Error
}

export function TopModelsTable({
  data,
  isLoading,
  error,
}: TopModelsTableProps) {
  const { t } = useI18n()

  // 按 requests 降序排序
  const sortedData = [...data].sort((a, b) => b.requests - a.requests)

  if (error) {
    return (
      <AdaptiveCard title={t("dashboardV2.topModels.title")}>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-muted-foreground text-sm">
              {t("dashboardV2.error.loadFailed")}
            </p>
            <p className="text-destructive text-xs mt-2">{error.message}</p>
          </div>
        </CardContent>
      </AdaptiveCard>
    )
  }

  if (isLoading) {
    return (
      <AdaptiveCard title={t("dashboardV2.topModels.title")}>
        <CardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        </CardContent>
      </AdaptiveCard>
    )
  }

  if (sortedData.length === 0) {
    return (
      <AdaptiveCard title={t("dashboardV2.topModels.title")}>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-muted-foreground text-sm">
              {t("dashboardV2.error.noData")}
            </p>
          </div>
        </CardContent>
      </AdaptiveCard>
    )
  }

  return (
    <AdaptiveCard title={t("dashboardV2.topModels.title")}>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("dashboardV2.topModels.modelName")}</TableHead>
              <TableHead className="text-right">
                {t("dashboardV2.topModels.requests")}
              </TableHead>
              <TableHead className="text-right">
                {t("dashboardV2.topModels.totalTokens")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedData.map((model, index) => (
              <TableRow key={`${model.model}-${index}`}>
                <TableCell className="font-medium">{model.model}</TableCell>
                <TableCell className="text-right">
                  {model.requests.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {model.tokens_total.toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </AdaptiveCard>
  )
}

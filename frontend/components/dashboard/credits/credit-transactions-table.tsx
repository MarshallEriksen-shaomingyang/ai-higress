"use client";

import React, { useMemo } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Receipt, ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { formatRelativeTime } from "@/lib/date-utils";
import type { CreditTransaction } from "@/lib/api-types";

interface CreditTransactionsTableProps {
  transactions: CreditTransaction[];
  loading: boolean;
  currentPage: number;
  pageSize: number;
  totalRecords: number;
  onPageChange: (page: number) => void;
  filterComponent?: React.ReactNode;
}

export function CreditTransactionsTable({
  transactions,
  loading,
  currentPage,
  pageSize,
  totalRecords,
  onPageChange,
  filterComponent
}: CreditTransactionsTableProps) {
  const { t, language } = useI18n();

  // 计算总页数
  const totalPages = useMemo(() => {
    return Math.ceil(totalRecords / pageSize);
  }, [totalRecords, pageSize]);

  // 格式化时间
  const formatTime = (dateString: string) => {
    try {
      return formatRelativeTime(dateString, language);
    } catch {
      return dateString;
    }
  };

  // 格式化金额（带颜色）
  const formatAmount = (amount: number) => {
    const isPositive = amount > 0;
    const colorClass = isPositive 
      ? "text-green-600 dark:text-green-400" 
      : "text-red-600 dark:text-red-400";
    
    return (
      <span className={`font-mono font-semibold ${colorClass}`}>
        {isPositive ? '+' : ''}{amount.toLocaleString()}
      </span>
    );
  };

  // 原因徽章
  const getReasonBadge = (reason: string) => {
    const badges = {
      usage: <Badge variant="secondary">{t("credits.reason_usage")}</Badge>,
      topup: <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">{t("credits.reason_topup")}</Badge>,
      refund: <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100">{t("credits.reason_refund")}</Badge>,
      adjustment: <Badge variant="outline">{t("credits.reason_adjustment")}</Badge>,
    };
    return badges[reason as keyof typeof badges] || <Badge>{reason}</Badge>;
  };

  // 格式化 tokens
  const formatTokens = (transaction: CreditTransaction) => {
    if (!transaction.total_tokens) return '-';
    
    return (
      <div className="text-sm space-y-0.5">
        <div className="font-mono">
          {transaction.total_tokens.toLocaleString()}
        </div>
        {transaction.input_tokens !== null && transaction.output_tokens !== null && (
          <div className="text-xs text-muted-foreground">
            {transaction.input_tokens.toLocaleString()} / {transaction.output_tokens.toLocaleString()}
          </div>
        )}
      </div>
    );
  };

  if (loading && transactions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("credits.transactions")}</CardTitle>
          <CardDescription>{t("credits.loading")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="w-5 h-5" />
              {t("credits.transactions")}
            </CardTitle>
            <CardDescription>
              {t("credits.total_records").replace("{count}", totalRecords.toString())}
            </CardDescription>
          </div>
          {filterComponent && (
            <div className="flex items-center gap-2">
              {filterComponent}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {transactions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Receipt className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">{t("credits.empty")}</h3>
            <p className="text-sm text-muted-foreground">
              {t("credits.empty_description")}
            </p>
          </div>
        ) : (
          <>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[180px]">{t("credits.time")}</TableHead>
                    <TableHead className="w-[100px]">{t("credits.amount")}</TableHead>
                    <TableHead className="w-[120px]">{t("credits.reason")}</TableHead>
                    <TableHead className="w-[200px]">{t("credits.description")}</TableHead>
                    <TableHead className="w-[150px]">{t("credits.model")}</TableHead>
                    <TableHead className="w-[180px] text-right">{t("credits.tokens")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactions.map((transaction) => (
                    <TableRow key={transaction.id}>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTime(transaction.created_at)}
                      </TableCell>
                      <TableCell>
                        {formatAmount(transaction.amount)}
                      </TableCell>
                      <TableCell>
                        {getReasonBadge(transaction.reason)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {transaction.description || '-'}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {transaction.model_name || '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatTokens(transaction)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* 分页控件 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPageChange(currentPage - 1)}
                  disabled={currentPage === 1 || loading}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  {t("common.previous")}
                </Button>
                <div className="text-sm text-muted-foreground px-4">
                  {currentPage} / {totalPages}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPageChange(currentPage + 1)}
                  disabled={currentPage === totalPages || loading}
                >
                  {t("common.next")}
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import React, { useState, useMemo, useCallback } from "react";
import { CreditBalanceCard } from "@/components/dashboard/credits/credit-balance-card";
import { CreditTransactionsTable } from "@/components/dashboard/credits/credit-transactions-table";
import { AdminTopupDialog } from "@/components/dashboard/credits/admin-topup-dialog";
import { DateRangeFilter, getDateRangeFromPreset, type DateRangePreset } from "@/components/dashboard/credits/date-range-filter";
import { useCreditBalance, useCreditTransactions } from "@/lib/swr/use-credits";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useI18n } from "@/lib/i18n-context";

export default function CreditsPage() {
  const { t } = useI18n();
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;

  // 状态管理
  const [topupDialogOpen, setTopupDialogOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [dateRange, setDateRange] = useState<DateRangePreset>('30days');
  const pageSize = 50;

  // 计算日期范围参数
  const dateRangeParams = useMemo(() => {
    return getDateRangeFromPreset(dateRange);
  }, [dateRange]);

  // 计算查询参数
  const transactionParams = useMemo(() => {
    return {
      limit: pageSize,
      offset: (currentPage - 1) * pageSize,
      ...dateRangeParams
    };
  }, [currentPage, pageSize, dateRangeParams]);

  // 获取积分余额
  const { balance, loading: balanceLoading, refresh: refreshBalance } = useCreditBalance();

  // 获取积分流水
  const { 
    transactions, 
    loading: transactionsLoading, 
    refresh: refreshTransactions 
  } = useCreditTransactions(transactionParams);

  // 处理充值成功
  const handleTopupSuccess = useCallback(() => {
    refreshBalance();
    refreshTransactions();
  }, [refreshBalance, refreshTransactions]);

  // 处理页码变化
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // 处理日期范围变化
  const handleDateRangeChange = useCallback((preset: DateRangePreset) => {
    setDateRange(preset);
    setCurrentPage(1); // 重置到第一页
  }, []);

  // 处理刷新
  const handleRefresh = useCallback(() => {
    refreshBalance();
    refreshTransactions();
  }, [refreshBalance, refreshTransactions]);

  // 筛选器组件
  const filterComponent = useMemo(() => (
    <DateRangeFilter
      value={dateRange}
      onChange={handleDateRangeChange}
      disabled={transactionsLoading}
    />
  ), [dateRange, handleDateRangeChange, transactionsLoading]);

  // 估算总记录数（实际应该从API返回）
  // 这里简化处理：如果返回了满页数据，假设还有更多
  const estimatedTotal = useMemo(() => {
    if (transactions.length < pageSize) {
      return (currentPage - 1) * pageSize + transactions.length;
    }
    // 如果是满页，估算至少还有一页
    return currentPage * pageSize + 1;
  }, [transactions.length, currentPage, pageSize]);

  return (
    <div className="space-y-6 max-w-7xl">
      {/* 页面标题 */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold">{t("credits.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {t("credits.subtitle")}
        </p>
      </div>

      {/* 积分余额卡片 */}
      <CreditBalanceCard
        balance={balance}
        loading={balanceLoading}
        onRefresh={handleRefresh}
        onTopup={() => setTopupDialogOpen(true)}
        showTopupButton={isSuperUser}
      />

      {/* 积分流水表格 */}
      <CreditTransactionsTable
        transactions={transactions}
        loading={transactionsLoading}
        currentPage={currentPage}
        pageSize={pageSize}
        totalRecords={estimatedTotal}
        onPageChange={handlePageChange}
        filterComponent={filterComponent}
      />

      {/* 管理员充值对话框 */}
      {isSuperUser && user && (
        <AdminTopupDialog
          open={topupDialogOpen}
          onOpenChange={setTopupDialogOpen}
          userId={user.id}
          onSuccess={handleTopupSuccess}
        />
      )}
    </div>
  );
}
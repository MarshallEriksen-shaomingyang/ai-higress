import { CostByProviderChartDemo } from "../_components/charts/cost-by-provider-chart-demo";

export default function CostDemoPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">成本结构图表演示</h1>
        <p className="text-muted-foreground mt-2">
          展示按 Provider 的成本分布（Donut 图）
        </p>
      </div>
      <CostByProviderChartDemo />
    </div>
  );
}

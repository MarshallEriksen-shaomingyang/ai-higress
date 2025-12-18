import { TopModelsTableDemo } from "../_components/tables/top-models-table-demo"

export default function TopModelsDemoPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Top Models Table Demo</h1>
        <p className="text-muted-foreground mt-2">
          演示 Top Models 排行榜组件的各种状态
        </p>
      </div>

      <TopModelsTableDemo />
    </div>
  )
}

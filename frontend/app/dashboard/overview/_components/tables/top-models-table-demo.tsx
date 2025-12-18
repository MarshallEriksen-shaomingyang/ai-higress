"use client"

import { useState } from "react"
import { TopModelsTable } from "./top-models-table"
import { Button } from "@/components/ui/button"
import type { DashboardV2TopModelItem } from "@/lib/api-types"

const mockData: DashboardV2TopModelItem[] = [
  {
    model: "gpt-4-turbo-preview",
    requests: 15234,
    tokens_total: 8456789,
  },
  {
    model: "claude-3-opus-20240229",
    requests: 12456,
    tokens_total: 6234567,
  },
  {
    model: "gpt-3.5-turbo",
    requests: 9876,
    tokens_total: 4567890,
  },
  {
    model: "claude-3-sonnet-20240229",
    requests: 7654,
    tokens_total: 3456789,
  },
  {
    model: "gemini-pro",
    requests: 5432,
    tokens_total: 2345678,
  },
  {
    model: "gpt-4",
    requests: 3210,
    tokens_total: 1234567,
  },
  {
    model: "claude-2.1",
    requests: 2109,
    tokens_total: 987654,
  },
  {
    model: "mistral-large",
    requests: 1543,
    tokens_total: 654321,
  },
]

export function TopModelsTableDemo() {
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [isEmpty, setIsEmpty] = useState(false)

  return (
    <div className="space-y-8">
      <div className="flex gap-4">
        <Button
          onClick={() => {
            setIsLoading(false)
            setHasError(false)
            setIsEmpty(false)
          }}
          variant="outline"
        >
          正常状态
        </Button>
        <Button
          onClick={() => {
            setIsLoading(true)
            setHasError(false)
            setIsEmpty(false)
          }}
          variant="outline"
        >
          加载中
        </Button>
        <Button
          onClick={() => {
            setIsLoading(false)
            setHasError(true)
            setIsEmpty(false)
          }}
          variant="outline"
        >
          错误状态
        </Button>
        <Button
          onClick={() => {
            setIsLoading(false)
            setHasError(false)
            setIsEmpty(true)
          }}
          variant="outline"
        >
          空数据
        </Button>
      </div>

      <TopModelsTable
        data={isEmpty ? [] : mockData}
        isLoading={isLoading}
        error={hasError ? new Error("Failed to fetch top models") : undefined}
      />
    </div>
  )
}

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useRouter } from "next/navigation";
import type { Provider } from "@/http/provider";
import { ProviderKeysTab } from "../provider-keys-tab";

vi.mock("next/navigation");

const mockUseRouter = useRouter as unknown as vi.Mock;

describe("ProviderKeysTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("点击管理密钥时使用 providerId 参数而不是 provider.provider_id", () => {
    const push = vi.fn();
    mockUseRouter.mockReturnValue({ push });

    const provider = {
      provider_id: "should-not-be-used",
      api_keys: [],
    } as unknown as Provider;

    render(
      <ProviderKeysTab
        providerId="openai"
        provider={provider}
        canManage={true}
        translations={{
          title: "API 密钥",
          description: "管理此提供商的 API 密钥",
          noKeys: "未配置 API 密钥",
          unnamed: "未命名密钥",
          weight: "权重",
          maxQps: "最大 QPS",
        }}
        actionManageKeys="管理密钥"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "管理密钥" }));
    expect(push).toHaveBeenCalledWith("/dashboard/providers/openai/keys");
  });
});


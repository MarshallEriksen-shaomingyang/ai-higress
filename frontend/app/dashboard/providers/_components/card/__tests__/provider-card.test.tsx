import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { Provider } from "@/http/provider";
import { I18nProvider } from "@/lib/i18n-context";
import { ProviderCard } from "../provider-card";

function renderWithI18n(component: React.ReactElement) {
  return render(<I18nProvider>{component}</I18nProvider>);
}

describe("ProviderCard", () => {
  it("点击管理密钥时传递 provider.provider_id", () => {
    const onManageKeys = vi.fn();

    const provider: Provider = {
      id: "internal-id-maybe-missing-in-some-responses",
      provider_id: "openai",
      name: "OpenAI",
      base_url: "https://example.com",
      transport: "http",
      provider_type: "native",
      sdk_vendor: null,
      visibility: "private",
      owner_id: "user-1",
      status: "healthy",
      weight: 1,
      region: null,
      cost_input: 0,
      cost_output: 0,
      billing_factor: 1,
      max_qps: null,
      retryable_status_codes: null,
      custom_headers: null,
      models_path: "/models",
      messages_path: null,
      chat_completions_path: "/v1/chat/completions",
      responses_path: null,
      images_generations_path: null,
      supported_api_styles: null,
      static_models: null,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };

    renderWithI18n(
      <ProviderCard provider={provider} onManageKeys={onManageKeys} />
    );

    fireEvent.click(screen.getByTestId("provider-card-manage-keys"));
    expect(onManageKeys).toHaveBeenCalledWith("openai");
  });
});


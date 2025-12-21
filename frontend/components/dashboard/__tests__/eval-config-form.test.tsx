import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EvalConfigForm } from "../eval-config-form";
import type { EvalConfig } from "@/lib/api-types";

// Mock i18n
vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

// Mock sonner
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("EvalConfigForm", () => {
  const mockConfig: EvalConfig = {
    id: "config-1",
    project_id: "project-1",
    enabled: true,
    max_challengers: 2,
    provider_scopes: ["private", "shared"],
    candidate_logical_models: ["gpt-4", "claude-3-opus"],
    cooldown_seconds: 60,
    budget_per_eval_credits: 5,
    rubric: "Test rubric",
    project_ai_enabled: false,
    project_ai_provider_model: undefined,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  it("should render loading state when config is null", () => {
    const onSubmit = vi.fn();
    render(<EvalConfigForm config={null} onSubmit={onSubmit} />);

    expect(screen.getByText("chat.eval_config.loading")).toBeInTheDocument();
  });

  it("should render form with config values", () => {
    const onSubmit = vi.fn();
    render(<EvalConfigForm config={mockConfig} onSubmit={onSubmit} />);

    // 验证表单标题
    expect(screen.getByText("chat.eval_config.title")).toBeInTheDocument();

    // 验证启用开关
    const enabledSwitch = screen.getByRole("switch", { name: /enabled/i });
    expect(enabledSwitch).toBeChecked();

    // 验证最大挑战者数输入框
    const maxChallengersInput = screen.getByLabelText(/max_challengers/i);
    expect(maxChallengersInput).toHaveValue(2);

    // 验证冷却时间输入框
    const cooldownInput = screen.getByLabelText(/cooldown_seconds/i);
    expect(cooldownInput).toHaveValue(60);
  });

  it("should handle form submission", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EvalConfigForm config={mockConfig} onSubmit={onSubmit} />);

    // 修改最大挑战者数
    const maxChallengersInput = screen.getByLabelText(/max_challengers/i);
    fireEvent.change(maxChallengersInput, { target: { value: "3" } });

    // 提交表单
    const submitButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          max_challengers: 3,
        })
      );
    });
  });

  it("should validate max_challengers range", async () => {
    const onSubmit = vi.fn();
    render(<EvalConfigForm config={mockConfig} onSubmit={onSubmit} />);

    // 设置无效值（超出范围）
    const maxChallengersInput = screen.getByLabelText(/max_challengers/i);
    fireEvent.change(maxChallengersInput, { target: { value: "15" } });

    // 提交表单
    const submitButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(submitButton);

    // 验证错误消息
    await waitFor(() => {
      expect(
        screen.getByText("chat.eval_config.validation_max_challengers")
      ).toBeInTheDocument();
    });

    // 验证 onSubmit 未被调用
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("should toggle candidate models", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const availableModels = ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"];
    render(
      <EvalConfigForm
        config={mockConfig}
        onSubmit={onSubmit}
        availableModels={availableModels}
      />
    );

    // 选中一个新模型
    const gpt35Checkbox = screen.getByLabelText("gpt-3.5-turbo");
    fireEvent.click(gpt35Checkbox);

    // 提交表单
    const submitButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          candidate_logical_models: expect.arrayContaining([
            "gpt-4",
            "claude-3-opus",
            "gpt-3.5-turbo",
          ]),
        })
      );
    });
  });

  it("should not crash when candidate_logical_models is null", () => {
    const onSubmit = vi.fn();
    const configWithNullCandidates: EvalConfig = {
      ...mockConfig,
      candidate_logical_models: null,
    };
    render(<EvalConfigForm config={configWithNullCandidates} onSubmit={onSubmit} />);

    expect(
      screen.getByText("chat.eval_config.validation_candidate_models")
    ).toBeInTheDocument();
  });

  it("should validate Project AI configuration", async () => {
    const onSubmit = vi.fn();
    render(<EvalConfigForm config={mockConfig} onSubmit={onSubmit} />);

    // 启用 Project AI
    const projectAiSwitch = screen.getByRole("switch", {
      name: /project_ai_enabled/i,
    });
    fireEvent.click(projectAiSwitch);

    // 不选择模型，直接提交
    const submitButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(submitButton);

    // 验证错误消息
    await waitFor(() => {
      expect(
        screen.getByText("chat.eval_config.validation_project_ai")
      ).toBeInTheDocument();
    });

    // 验证 onSubmit 未被调用
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("should handle provider scope selection", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EvalConfigForm config={mockConfig} onSubmit={onSubmit} />);

    // 取消选中 "shared" scope
    const sharedCheckbox = screen.getByLabelText(/scope_shared/i);
    fireEvent.click(sharedCheckbox);

    // 提交表单
    const submitButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          provider_scopes: ["private"],
        })
      );
    });
  });

  it("should disable submit button when submitting", () => {
    const onSubmit = vi.fn();
    render(
      <EvalConfigForm config={mockConfig} onSubmit={onSubmit} isSubmitting />
    );

    const submitButton = screen.getByRole("button", { name: /saving/i });
    expect(submitButton).toBeDisabled();
  });
});

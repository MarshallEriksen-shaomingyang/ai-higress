import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProviderKeyDialog } from "../provider-key-dialog";

vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe("ProviderKeyDialog", () => {
  it("使用 Dialog 渲染并可触发取消关闭", () => {
    const onOpenChange = vi.fn();

    render(
      <ProviderKeyDialog
        open={true}
        onOpenChange={onOpenChange}
        editingKey={null}
        onSuccess={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(
      screen.getByText("provider_keys.dialog_create_title")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "common.cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});


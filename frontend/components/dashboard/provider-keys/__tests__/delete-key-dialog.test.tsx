import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DeleteKeyDialog } from "../delete-key-dialog";

vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe("DeleteKeyDialog", () => {
  it("点击取消会触发关闭回调", () => {
    const onOpenChange = vi.fn();
    render(
      <DeleteKeyDialog
        open={true}
        onOpenChange={onOpenChange}
        keyLabel="prod-key"
        onConfirm={vi.fn().mockResolvedValue(undefined)}
        isDeleting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "provider_keys.delete_cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("点击删除会触发 onConfirm", () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <DeleteKeyDialog
        open={true}
        onOpenChange={vi.fn()}
        keyLabel="prod-key"
        onConfirm={onConfirm}
        isDeleting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "provider_keys.delete_confirm" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});


import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantList } from "../assistant-list";
import type { Assistant } from "@/lib/api-types";
import { useChatSidebarSearchStore } from "@/lib/stores/chat-sidebar-search-store";

// Mock i18n context
vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "chat.assistant.title": "Assistants",
        "chat.assistant.create": "Create Assistant",
        "chat.assistant.search_placeholder": "Search assistants...",
        "chat.assistant.search_empty": "No matching assistants",
        "chat.search.clear": "Clear search",
        "chat.assistant.empty": "No Assistants",
        "chat.assistant.empty_description": "Create your first assistant to get started",
        "chat.assistant.loading": "Loading assistants...",
        "chat.message.load_more": "Load More",
      };
      return translations[key] || key;
    },
  }),
}));

// Mock AssistantCard
vi.mock("../assistant-card", () => ({
  AssistantCard: ({ assistant, isSelected, onSelect }: any) => (
    <div
      data-testid={`assistant-${assistant.assistant_id}`}
      onClick={() => onSelect?.(assistant.assistant_id)}
      className={isSelected ? "selected" : ""}
    >
      {assistant.name}
    </div>
  ),
}));

describe("AssistantList", () => {
  beforeEach(() => {
    useChatSidebarSearchStore.getState().reset();
  });

  const mockAssistants: Assistant[] = [
    {
      assistant_id: "asst-1",
      project_id: "proj-1",
      name: "Alpha Assistant",
      default_logical_model: "gpt-4.1-mini",
      archived: false,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      assistant_id: "asst-2",
      project_id: "proj-1",
      name: "Beta Helper",
      default_logical_model: "claude-4.5-sonnet",
      archived: false,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  it("should render assistants list", () => {
    render(<AssistantList assistants={mockAssistants} />);

    expect(screen.getByText("Assistants")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-asst-1")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-asst-2")).toBeInTheDocument();
  });

  it("should filter assistants by search query", () => {
    useChatSidebarSearchStore.getState().setAssistantQuery("beta");
    render(<AssistantList assistants={mockAssistants} />);

    expect(screen.queryByTestId("assistant-asst-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("assistant-asst-2")).toBeInTheDocument();
  });

  it("should show empty search state when no assistants match", () => {
    useChatSidebarSearchStore.getState().setAssistantQuery("nope");
    render(<AssistantList assistants={mockAssistants} />);

    expect(screen.getByText("No matching assistants")).toBeInTheDocument();
  });

  it("should call onCreateAssistant when create button clicked", () => {
    const onCreateAssistant = vi.fn();
    render(
      <AssistantList assistants={mockAssistants} onCreateAssistant={onCreateAssistant} />
    );

    const createButton = screen.getByText("Create Assistant");
    fireEvent.click(createButton);

    expect(onCreateAssistant).toHaveBeenCalled();
  });
});


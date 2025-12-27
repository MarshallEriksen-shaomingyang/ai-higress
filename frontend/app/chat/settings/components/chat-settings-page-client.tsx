"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useI18n } from "@/lib/i18n-context";
import { useChatStore } from "@/lib/stores/chat-store";
import { useProjectChatSettings, useUpdateProjectChatSettings } from "@/lib/swr/use-project-chat-settings";
import { useSelectableChatModels } from "@/lib/swr/use-selectable-chat-models";
import { ChatSettingsPreferences } from "./chat-settings-preferences";

const DISABLE_VALUE = "__disable__";

export function ChatSettingsPageClient() {
  const { t } = useI18n();
  const { selectedProjectId } = useChatStore();

  const { settings, mutate: mutateProjectSettings } = useProjectChatSettings(selectedProjectId);
  const updateProjectSettings = useUpdateProjectChatSettings();

  const [savingProject, setSavingProject] = useState(false);

  const projectTitleModelValue =
    settings?.title_logical_model && settings.title_logical_model !== "auto"
      ? settings.title_logical_model
      : null;

  const { filterOptions } = useSelectableChatModels(
    selectedProjectId,
    {
      includeAuto: false,
      extraModels: [projectTitleModelValue ?? undefined],
    }
  );
  const [projectTitleSearch, setProjectTitleSearch] = useState("");

  const projectTitleModels = useMemo(
    () => filterOptions(projectTitleSearch),
    [filterOptions, projectTitleSearch]
  );

  const updateProjectTitleModel = async (value: string) => {
    if (!selectedProjectId) return;
    setSavingProject(true);
    try {
      await updateProjectSettings(selectedProjectId, {
        title_logical_model: value === DISABLE_VALUE ? null : value,
      });
      await mutateProjectSettings();
      toast.success(t("chat.settings.saved"));
    } catch (error) {
      console.error("Failed to update project title model:", error);
      toast.error(t("chat.settings.save_failed"));
    } finally {
      setSavingProject(false);
    }
  };

  if (!selectedProjectId) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-sm text-muted-foreground">
          {t("chat.project.not_selected")}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <div>
          <h1 className="text-xl font-semibold">{t("chat.settings.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("chat.settings.subtitle")}
          </p>
        </div>

        <Tabs defaultValue="project">
          <TabsList className="w-full">
            <TabsTrigger value="project" className="flex-1">
              {t("chat.settings.tab_project")}
            </TabsTrigger>
            <TabsTrigger value="preferences" className="flex-1">
              {t("chat.settings.tab_preferences")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="project" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t("chat.settings.project.title")}</CardTitle>
                <CardDescription>{t("chat.settings.project.description")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <div className="text-sm font-medium">{t("chat.settings.project.title_model")}</div>
                  <Select
                    value={projectTitleModelValue ?? DISABLE_VALUE}
                    onValueChange={(value) => void updateProjectTitleModel(value)}
                    onOpenChange={(open) => {
                      if (!open) setProjectTitleSearch("");
                    }}
                  >
                    <SelectTrigger disabled={savingProject}>
                      <SelectValue placeholder={t("chat.assistant.title_model_placeholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <div className="p-2 pb-1">
                        <Input
                          value={projectTitleSearch}
                          onChange={(event) => setProjectTitleSearch(event.target.value)}
                          placeholder={t("chat.model.search_placeholder")}
                          className="h-9"
                        />
                      </div>
                      <SelectItem value={DISABLE_VALUE}>
                        {t("chat.settings.title_model_disable")}
                      </SelectItem>
                      {projectTitleModels.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="text-xs text-muted-foreground">
                    {t("chat.settings.project.title_model_help")}
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button variant="outline" disabled>
                    {t("chat.settings.auto_saved")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="preferences" className="mt-4">
            <ChatSettingsPreferences />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

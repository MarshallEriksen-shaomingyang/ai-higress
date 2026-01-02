"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
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
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import { useProjectChatSettings, useUpdateProjectChatSettings } from "@/lib/swr/use-project-chat-settings";
import { useSelectableChatModels } from "@/lib/swr/use-selectable-chat-models";
import { useSelectableTtsModels } from "@/lib/swr/use-selectable-tts-models";
import { ChatSettingsPreferences } from "./chat-settings-preferences";

const DISABLE_VALUE = "__disable__";
const TTS_FORMAT_VALUES = ["mp3", "opus", "aac", "wav", "ogg", "flac", "aiff", "pcm"] as const;
type TtsFormatValue = (typeof TTS_FORMAT_VALUES)[number];

function isTtsFormatValue(value: string): value is TtsFormatValue {
  return (TTS_FORMAT_VALUES as readonly string[]).includes(value);
}

const TTS_VOICE_VALUES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] as const;
type TtsVoiceValue = (typeof TTS_VOICE_VALUES)[number];

function isTtsVoiceValue(value: string): value is TtsVoiceValue {
  return (TTS_VOICE_VALUES as readonly string[]).includes(value);
}

export function ChatSettingsPageClient() {
  const { t } = useI18n();
  const { selectedProjectId } = useChatStore();
  const {
    preferences,
    setPreferredTtsModel,
    setPreferredTtsVoice,
    setPreferredTtsFormat,
    setPreferredTtsSpeed,
  } = useUserPreferencesStore();

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
  const [projectTtsSearch, setProjectTtsSearch] = useState("");

  const projectTitleModels = useMemo(
    () => filterOptions(projectTitleSearch),
    [filterOptions, projectTitleSearch]
  );

  const projectTtsModelValue =
    (selectedProjectId && preferences.preferredTtsModelByProject[selectedProjectId]) || null;
  const projectTtsVoiceValue =
    (selectedProjectId && preferences.preferredTtsVoiceByProject?.[selectedProjectId]) || null;
  const projectTtsFormatValue =
    (selectedProjectId && preferences.preferredTtsFormatByProject[selectedProjectId]) || null;
  const projectTtsSpeedValue =
    (selectedProjectId && preferences.preferredTtsSpeedByProject?.[selectedProjectId]) || null;
  const { filterOptions: filterTtsOptions } = useSelectableTtsModels(selectedProjectId, {
    extraModels: [projectTtsModelValue],
  });
  const projectTtsModels = useMemo(
    () => filterTtsOptions(projectTtsSearch),
    [filterTtsOptions, projectTtsSearch]
  );

  const updateProjectTtsModel = (value: string) => {
    if (!selectedProjectId) return;
    const next = (value || "").trim();
    if (!next || next === DISABLE_VALUE) {
      setPreferredTtsModel(selectedProjectId, null);
    } else {
      setPreferredTtsModel(selectedProjectId, next);
    }
    toast.success(t("chat.settings.saved"));
  };

  const updateProjectTtsFormat = (value: string) => {
    if (!selectedProjectId) return;
    const next = (value || "").trim();
    if (!next || next === DISABLE_VALUE) {
      setPreferredTtsFormat(selectedProjectId, null);
    } else if (isTtsFormatValue(next)) {
      setPreferredTtsFormat(selectedProjectId, next);
    } else {
      console.warn("Unexpected TTS response_format:", next);
      setPreferredTtsFormat(selectedProjectId, null);
    }
    toast.success(t("chat.settings.saved"));
  };

  const updateProjectTtsVoice = (value: string) => {
    if (!selectedProjectId) return;
    const next = (value || "").trim();
    if (!next || next === DISABLE_VALUE) {
      setPreferredTtsVoice(selectedProjectId, null);
    } else if (isTtsVoiceValue(next)) {
      setPreferredTtsVoice(selectedProjectId, next);
    } else {
      console.warn("Unexpected TTS voice:", next);
      setPreferredTtsVoice(selectedProjectId, null);
    }
    toast.success(t("chat.settings.saved"));
  };

  const effectiveTtsSpeed = Number.isFinite(projectTtsSpeedValue) ? (projectTtsSpeedValue as number) : 1.0;
  const [ttsSpeedDraft, setTtsSpeedDraft] = useState<number>(effectiveTtsSpeed);
  useEffect(() => {
    setTtsSpeedDraft(effectiveTtsSpeed);
  }, [effectiveTtsSpeed, selectedProjectId]);

  const resetProjectTtsSpeed = () => {
    if (!selectedProjectId) return;
    setPreferredTtsSpeed(selectedProjectId, null);
    setTtsSpeedDraft(1.0);
    toast.success(t("chat.settings.saved"));
  };

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

                <div className="grid gap-2">
                  <div className="text-sm font-medium">{t("chat.settings.project.tts_model")}</div>
                  <Select
                    value={projectTtsModelValue ?? DISABLE_VALUE}
                    onValueChange={(value) => updateProjectTtsModel(value)}
                    onOpenChange={(open) => {
                      if (!open) setProjectTtsSearch("");
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("chat.settings.project.tts_model_placeholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <div className="p-2 pb-1">
                        <Input
                          value={projectTtsSearch}
                          onChange={(event) => setProjectTtsSearch(event.target.value)}
                          placeholder={t("chat.model.search_placeholder")}
                          className="h-9"
                        />
                      </div>
                      <SelectItem value={DISABLE_VALUE}>
                        {t("chat.settings.project.tts_model_disable")}
                      </SelectItem>
                      {projectTtsModels.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="text-xs text-muted-foreground">
                    {t("chat.settings.project.tts_model_help")}
                  </div>
                </div>

                <div className="grid gap-2">
                  <div className="text-sm font-medium">{t("chat.settings.project.tts_voice")}</div>
                  <Select
                    value={projectTtsVoiceValue ?? DISABLE_VALUE}
                    onValueChange={(value) => updateProjectTtsVoice(value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("chat.settings.project.tts_voice_placeholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={DISABLE_VALUE}>
                        {t("chat.settings.project.tts_voice_default")}
                      </SelectItem>
                      {TTS_VOICE_VALUES.map((voice) => (
                        <SelectItem key={voice} value={voice}>
                          {voice}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="text-xs text-muted-foreground">
                    {t("chat.settings.project.tts_voice_help")}
                  </div>
                </div>

                <div className="grid gap-2">
                  <div className="text-sm font-medium">{t("chat.settings.project.tts_format")}</div>
                  <Select
                    value={projectTtsFormatValue ?? DISABLE_VALUE}
                    onValueChange={(value) => updateProjectTtsFormat(value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("chat.settings.project.tts_format_placeholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={DISABLE_VALUE}>
                        {t("chat.settings.project.tts_format_default")}
                      </SelectItem>
                      <SelectItem value="mp3">{t("chat.settings.project.tts_format_mp3")}</SelectItem>
                      <SelectItem value="opus">{t("chat.settings.project.tts_format_opus")}</SelectItem>
                      <SelectItem value="aac">{t("chat.settings.project.tts_format_aac")}</SelectItem>
                      <SelectItem value="wav">{t("chat.settings.project.tts_format_wav")}</SelectItem>
                      <SelectItem value="ogg">{t("chat.settings.project.tts_format_ogg")}</SelectItem>
                      <SelectItem value="flac">{t("chat.settings.project.tts_format_flac")}</SelectItem>
                      <SelectItem value="aiff">{t("chat.settings.project.tts_format_aiff")}</SelectItem>
                      <SelectItem value="pcm">{t("chat.settings.project.tts_format_pcm")}</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="text-xs text-muted-foreground">
                    {t("chat.settings.project.tts_format_help")}
                  </div>
                </div>

                <div className="grid gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">{t("chat.settings.project.tts_speed")}</div>
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-muted-foreground tabular-nums">
                        {ttsSpeedDraft.toFixed(2)}×
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={resetProjectTtsSpeed}
                      >
                        {t("chat.settings.project.tts_speed_reset")}
                      </Button>
                    </div>
                  </div>
                  <Slider
                    value={[ttsSpeedDraft]}
                    min={0.25}
                    max={4}
                    step={0.05}
                    onValueChange={(values) => {
                      const next = values?.[0];
                      if (!Number.isFinite(next)) return;
                      setTtsSpeedDraft(next);
                    }}
                    onValueCommit={(values) => {
                      if (!selectedProjectId) return;
                      const next = values?.[0];
                      if (!Number.isFinite(next)) return;
                      // speed=1.0 视作默认，不落本地偏好
                      if (Math.abs(next - 1.0) < 1e-9) {
                        setPreferredTtsSpeed(selectedProjectId, null);
                      } else {
                        setPreferredTtsSpeed(selectedProjectId, next);
                      }
                      toast.success(t("chat.settings.saved"));
                    }}
                  />
                  <div className="text-xs text-muted-foreground">
                    {t("chat.settings.project.tts_speed_help")}
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

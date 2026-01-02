"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { RotateCcw, Sparkles, Volume2 } from "lucide-react";
import {
  useVideoComposerStore,
  selectVideoConfig,
} from "@/lib/stores/video-composer-store";
import { useI18n } from "@/lib/i18n-context";
import type { VideoResolution } from "@/lib/api-types";
import type { LogicalModel } from "@/lib/api-types";

interface VideoConfigSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  models: LogicalModel[];
}

export function VideoConfigSheet({
  open,
  onOpenChange,
  models,
}: VideoConfigSheetProps) {
  const { t } = useI18n();
  const config = useVideoComposerStore(selectVideoConfig);
  const {
    setModel,
    setResolution,
    setDuration,
    setNegativePrompt,
    setSeed,
    setFps,
    setEnhancePrompt,
    setGenerateAudio,
    resetConfig,
  } = useVideoComposerStore();

  const resolutionOptions: { value: VideoResolution; label: string }[] = [
    { value: "480p", label: t("video.settings.resolution_480p") },
    { value: "720p", label: t("video.settings.resolution_720p") },
    { value: "1080p", label: t("video.settings.resolution_1080p") },
  ];

  const durationOptions = [5, 8, 10, 12];
  const fpsOptions = [16, 24, 30];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="!w-[340px] sm:!w-[420px] sm:!max-w-[420px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            {t("video.settings.title")}
          </SheetTitle>
          <SheetDescription>
            {t("video.settings.description")}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Model Selection */}
          <div className="space-y-2">
            <Label htmlFor="model">{t("video.settings.model")}</Label>
            <Select value={config.model} onValueChange={setModel}>
              <SelectTrigger id="model">
                <SelectValue placeholder={t("video.settings.model_placeholder")} />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.logical_id} value={model.logical_id}>
                    {model.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Resolution */}
          <div className="space-y-2">
            <Label htmlFor="resolution">{t("video.settings.resolution")}</Label>
            <Select
              value={config.resolution}
              onValueChange={(v) => setResolution(v as VideoResolution)}
            >
              <SelectTrigger id="resolution">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {resolutionOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Duration */}
          <div className="space-y-2">
            <Label>{t("video.settings.duration")}: {config.duration}s</Label>
            <div className="flex gap-2">
              {durationOptions.map((d) => (
                <Button
                  key={d}
                  variant={config.duration === d ? "default" : "outline"}
                  size="sm"
                  onClick={() => setDuration(d)}
                >
                  {d}s
                </Button>
              ))}
            </div>
          </div>

          {/* FPS */}
          <div className="space-y-2">
            <Label>{t("video.settings.fps")}: {config.fps} FPS</Label>
            <div className="flex gap-2">
              {fpsOptions.map((f) => (
                <Button
                  key={f}
                  variant={config.fps === f ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFps(f)}
                >
                  {f}
                </Button>
              ))}
            </div>
          </div>

          {/* Seed */}
          <div className="space-y-2">
            <Label htmlFor="seed">{t("video.settings.seed")}</Label>
            <div className="flex gap-2">
              <Input
                id="seed"
                type="number"
                min={0}
                placeholder={t("video.settings.seed_placeholder")}
                value={config.seed ?? ""}
                onChange={(e) =>
                  setSeed(e.target.value ? Number(e.target.value) : undefined)
                }
                className="flex-1"
              />
              <Button
                variant="outline"
                size="icon"
                onClick={() => setSeed(Math.floor(Math.random() * 4294967295))}
                title={t("video.settings.seed_random")}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("video.settings.seed_hint")}
            </p>
          </div>

          {/* Negative Prompt */}
          <div className="space-y-2">
            <Label htmlFor="negative-prompt">{t("video.settings.negative_prompt")}</Label>
            <Textarea
              id="negative-prompt"
              placeholder={t("video.settings.negative_prompt_placeholder")}
              value={config.negativePrompt}
              onChange={(e) => setNegativePrompt(e.target.value)}
              className="min-h-[80px] resize-none"
            />
          </div>

          {/* Enhance Prompt */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="enhance-prompt" className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                {t("video.settings.enhance_prompt")}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t("video.settings.enhance_prompt_hint")}
              </p>
            </div>
            <Switch
              id="enhance-prompt"
              checked={config.enhancePrompt}
              onCheckedChange={setEnhancePrompt}
            />
          </div>

          {/* Generate Audio */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="generate-audio" className="flex items-center gap-2">
                <Volume2 className="h-4 w-4" />
                {t("video.settings.generate_audio")}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t("video.settings.generate_audio_hint")}
              </p>
            </div>
            <Switch
              id="generate-audio"
              checked={config.generateAudio}
              onCheckedChange={setGenerateAudio}
            />
          </div>

          {/* Reset Button */}
          <div className="pt-4 border-t">
            <Button
              variant="outline"
              className="w-full"
              onClick={resetConfig}
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              {t("video.settings.reset")}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

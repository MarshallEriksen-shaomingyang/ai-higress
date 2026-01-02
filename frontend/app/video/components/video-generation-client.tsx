"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { nanoid } from "nanoid";
import {
  Settings2,
  Sparkles,
  RectangleHorizontal,
  RectangleVertical,
  Square,
  Video,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useVideoComposerStore,
  selectVideoConfig,
  selectIsGenerating,
  type VideoGenTask,
} from "@/lib/stores/video-composer-store";
import { useVideoGenerations } from "@/lib/swr/use-video-generations";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useI18n } from "@/lib/i18n-context";
import { VideoConfigSheet } from "./video-config-sheet";
import { VideoFilmstrip } from "./video-filmstrip";
import type { VideoAspectRatio, VideoGenerationTaskStatusResponse } from "@/lib/api-types";

const ASPECT_RATIOS: {
  value: VideoAspectRatio;
  icon: typeof RectangleHorizontal;
  labelKey: string;
}[] = [
  { value: "16:9", icon: RectangleHorizontal, labelKey: "video.aspect_ratio.landscape" },
  { value: "9:16", icon: RectangleVertical, labelKey: "video.aspect_ratio.portrait" },
  { value: "1:1", icon: Square, labelKey: "video.aspect_ratio.square" },
];

export function VideoGenerationClient() {
  const { t } = useI18n();
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<VideoGenTask | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const currentTaskIdRef = useRef<string | null>(null);

  const config = useVideoComposerStore(selectVideoConfig);
  const isGenerating = useVideoComposerStore(selectIsGenerating);
  const {
    setPrompt,
    setAspectRatio,
    setModel,
    setIsGenerating,
    addTask,
    updateTask,
    buildRequest,
  } = useVideoComposerStore();

  const { generateVideoAsync, cancelPolling } = useVideoGenerations({
    onStatusChange: (status: VideoGenerationTaskStatusResponse) => {
      // Update progress
      if (status.progress !== undefined) {
        setProgress(status.progress);
      }

      // Update status message
      switch (status.status) {
        case "queued":
          setStatusMessage(t("video.status.queued"));
          break;
        case "running":
          setStatusMessage(t("video.status.running"));
          break;
        case "succeeded":
          setStatusMessage(t("video.status.complete"));
          break;
        case "failed":
          setStatusMessage(t("video.status.failed"));
          break;
      }

      // Update task in store if we have a matching task
      if (currentTaskIdRef.current) {
        const taskId = currentTaskIdRef.current;
        if (status.status === "succeeded" && status.result) {
          updateTask(taskId, {
            status: "success",
            result: status.result,
            completedAt: Date.now(),
          });
        } else if (status.status === "failed") {
          updateTask(taskId, {
            status: "failed",
            error: status.error?.message || t("video.error.generation_failed"),
            completedAt: Date.now(),
          });
        }
      }
    },
  });

  const { models } = useLogicalModels();

  // Filter models that support video generation
  const videoModels = models.filter((m) =>
    m.capabilities?.includes("video_generation")
  );

  // Auto-select first video model if none selected
  useEffect(() => {
    if (!config.model && videoModels.length > 0 && videoModels[0]) {
      setModel(videoModels[0].logical_id);
    }
  }, [config.model, videoModels, setModel]);

  const handleGenerate = useCallback(async () => {
    if (!config.prompt.trim() || !config.model || isGenerating) return;

    const taskId = nanoid();
    currentTaskIdRef.current = taskId;
    const request = buildRequest();

    // Reset progress
    setProgress(0);
    setStatusMessage(t("video.status.creating"));

    // Create task entry
    const task: VideoGenTask = {
      id: taskId,
      status: "generating",
      prompt: config.prompt,
      params: {
        model: request.model,
        aspect_ratio: request.aspect_ratio,
        resolution: request.resolution,
        seconds: request.seconds,
        fps: request.fps,
        negative_prompt: request.negative_prompt,
        seed: request.seed,
        enhance_prompt: request.enhance_prompt,
        generate_audio: request.generate_audio,
      },
      createdAt: Date.now(),
    };

    addTask(task);
    setIsGenerating(true);

    try {
      const response = await generateVideoAsync(request);

      if (response.status === "succeeded" && response.result) {
        updateTask(taskId, {
          status: "success",
          result: response.result,
          completedAt: Date.now(),
        });
      } else if (response.status === "failed") {
        updateTask(taskId, {
          status: "failed",
          error: response.error?.message || t("video.error.generation_failed"),
          completedAt: Date.now(),
        });
      }
    } catch (error) {
      updateTask(taskId, {
        status: "failed",
        error: error instanceof Error ? error.message : t("video.error.generation_failed"),
        completedAt: Date.now(),
      });
    } finally {
      setIsGenerating(false);
      currentTaskIdRef.current = null;
      setProgress(0);
      setStatusMessage("");
    }
  }, [
    config.prompt,
    config.model,
    isGenerating,
    buildRequest,
    addTask,
    updateTask,
    setIsGenerating,
    generateVideoAsync,
    t,
  ]);

  const handleCancel = useCallback(() => {
    cancelPolling();
    if (currentTaskIdRef.current) {
      updateTask(currentTaskIdRef.current, {
        status: "failed",
        error: t("video.error.cancelled"),
        completedAt: Date.now(),
      });
    }
    setIsGenerating(false);
    currentTaskIdRef.current = null;
    setProgress(0);
    setStatusMessage("");
  }, [cancelPolling, updateTask, setIsGenerating, t]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleGenerate();
      }
    },
    [handleGenerate]
  );

  return (
    <div className="relative flex flex-col h-full w-full overflow-hidden">
      {/* Aurora/Gradient Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-violet-500/10 via-background to-cyan-500/10" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-transparent to-transparent" />

      {/* Main Content Area */}
      <div className="relative flex-1 flex flex-col items-center justify-center p-4 md:p-8">
        {/* Video Preview Area */}
        {selectedVideo?.status === "success" && selectedVideo.result?.data?.[0]?.url ? (
          <div className="w-full max-w-4xl mb-8">
            <video
              src={selectedVideo.result.data[0].url}
              controls
              autoPlay
              className="w-full rounded-xl shadow-2xl"
            />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-4">
              <Video className="h-16 w-16 mx-auto text-muted-foreground/50" />
              <p className="text-muted-foreground">
                {t("video.placeholder")}
              </p>
            </div>
          </div>
        )}

        {/* Progress Bar (shown during generation) */}
        {isGenerating && (
          <div className="w-full max-w-2xl mb-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{statusMessage}</span>
              <span className="text-muted-foreground">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        {/* Magic Bar - Central Input Area */}
        <div
          className={cn(
            "w-full max-w-2xl",
            "bg-white/10 dark:bg-black/20",
            "backdrop-blur-xl",
            "border border-white/20 dark:border-white/10",
            "rounded-2xl",
            "shadow-[0_8px_32px_rgba(0,0,0,0.12)]",
            "p-4",
            "transition-all duration-300",
            "hover:shadow-[0_12px_48px_rgba(0,0,0,0.16)]"
          )}
        >
          {/* Prompt Input */}
          <Textarea
            placeholder={t("video.input_placeholder")}
            value={config.prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
            className={cn(
              "w-full min-h-[80px] max-h-[200px] resize-none",
              "bg-transparent border-0 focus-visible:ring-0",
              "text-base placeholder:text-muted-foreground/60",
              "scrollbar-thin scrollbar-thumb-white/10",
              isGenerating && "opacity-50"
            )}
            autoFocus
          />

          {/* Quick Toolbar */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/10">
            <div className="flex items-center gap-2">
              {/* Aspect Ratio Buttons */}
              <TooltipProvider>
                {ASPECT_RATIOS.map((ratio) => (
                  <Tooltip key={ratio.value}>
                    <TooltipTrigger asChild>
                      <Button
                        variant={
                          config.aspectRatio === ratio.value
                            ? "default"
                            : "ghost"
                        }
                        size="icon"
                        disabled={isGenerating}
                        className={cn(
                          "h-8 w-8",
                          config.aspectRatio === ratio.value
                            ? "bg-primary/80"
                            : "hover:bg-white/10"
                        )}
                        onClick={() => setAspectRatio(ratio.value)}
                      >
                        <ratio.icon className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{t(ratio.labelKey)}</TooltipContent>
                  </Tooltip>
                ))}
              </TooltipProvider>

              {/* Settings Button */}
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={isGenerating}
                      className="h-8 w-8 hover:bg-white/10"
                      onClick={() => setIsConfigOpen(true)}
                    >
                      <Settings2 className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{t("video.settings.tooltip")}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            {/* Generate / Cancel Button */}
            {isGenerating ? (
              <Button
                onClick={handleCancel}
                variant="destructive"
                className="px-6 gap-2"
              >
                <XCircle className="h-4 w-4" />
                {t("video.cancel")}
              </Button>
            ) : (
              <Button
                onClick={handleGenerate}
                disabled={!config.prompt.trim() || !config.model}
                className={cn(
                  "px-6 gap-2",
                  "bg-gradient-to-r from-primary to-primary/80",
                  "hover:from-primary/90 hover:to-primary/70",
                  "shadow-lg shadow-primary/25"
                )}
              >
                <Sparkles className="h-4 w-4" />
                {t("video.generate")}
              </Button>
            )}
          </div>

          {/* Model indicator */}
          {config.model && (
            <div className="mt-2 text-xs text-muted-foreground/60 text-center">
              {t("video.using_model").replace("{model}", videoModels.find((m) => m.logical_id === config.model)?.display_name || config.model)}
            </div>
          )}
        </div>

        {/* Keyboard Shortcut Hint */}
        <p className="mt-3 text-xs text-muted-foreground/50">
          {t("video.keyboard_hint")} <kbd className="px-1.5 py-0.5 rounded bg-muted/50 text-[10px]">Cmd</kbd> +{" "}
          <kbd className="px-1.5 py-0.5 rounded bg-muted/50 text-[10px]">Enter</kbd> {t("video.keyboard_hint_to_generate")}
        </p>
      </div>

      {/* Bottom Filmstrip */}
      <div className="relative px-4 pb-4 md:px-8 md:pb-6">
        <VideoFilmstrip onSelectVideo={setSelectedVideo} />
      </div>

      {/* Config Sheet */}
      <VideoConfigSheet
        open={isConfigOpen}
        onOpenChange={setIsConfigOpen}
        models={videoModels}
      />
    </div>
  );
}

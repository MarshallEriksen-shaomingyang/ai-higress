"use client";

import { memo } from "react";
import { Play, Trash2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useVideoComposerStore,
  selectVideoHistory,
  type VideoGenTask,
} from "@/lib/stores/video-composer-store";
import { useI18n } from "@/lib/i18n-context";

interface VideoFilmstripProps {
  onSelectVideo?: (task: VideoGenTask) => void;
}

function FilmstripItem({
  task,
  onSelect,
  onRemove,
  statusLabels,
}: {
  task: VideoGenTask;
  onSelect?: () => void;
  onRemove: () => void;
  statusLabels: Record<string, string>;
}) {
  const videoUrl = task.result?.data?.[0]?.url;

  const getStatusLabel = (status: string) => {
    return statusLabels[status] || status;
  };

  return (
    <div
      className={cn(
        "relative flex-shrink-0 w-32 h-20 rounded-lg overflow-hidden",
        "bg-black/20 backdrop-blur-sm border border-white/10",
        "group cursor-pointer transition-all duration-200",
        "hover:border-primary/50 hover:scale-105",
        task.status === "generating" && "animate-pulse"
      )}
      onClick={onSelect}
    >
      {/* Video Preview or Status */}
      {task.status === "success" && videoUrl ? (
        <video
          src={videoUrl}
          className="w-full h-full object-cover"
          muted
          playsInline
          preload="metadata"
          onMouseEnter={(e) => e.currentTarget.play()}
          onMouseLeave={(e) => {
            e.currentTarget.pause();
            e.currentTarget.currentTime = 0;
          }}
        />
      ) : task.status === "generating" ? (
        <div className="w-full h-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 text-primary animate-spin" />
        </div>
      ) : task.status === "failed" ? (
        <div className="w-full h-full flex items-center justify-center">
          <AlertCircle className="h-6 w-6 text-destructive" />
        </div>
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <Play className="h-6 w-6 text-muted-foreground" />
        </div>
      )}

      {/* Hover Overlay */}
      <div
        className={cn(
          "absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100",
          "transition-opacity flex items-center justify-center gap-2"
        )}
      >
        {task.status === "success" && (
          <Button size="icon" variant="ghost" className="h-8 w-8 text-white">
            <Play className="h-4 w-4" />
          </Button>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-white hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Status Badge */}
      {task.status !== "success" && (
        <div
          className={cn(
            "absolute bottom-1 left-1 px-1.5 py-0.5 rounded text-[10px] font-medium",
            task.status === "generating" &&
              "bg-primary/80 text-primary-foreground",
            task.status === "failed" && "bg-destructive/80 text-white",
            task.status === "pending" && "bg-muted text-muted-foreground"
          )}
        >
          {getStatusLabel(task.status)}
        </div>
      )}
    </div>
  );
}

export const VideoFilmstrip = memo(function VideoFilmstrip({
  onSelectVideo,
}: VideoFilmstripProps) {
  const { t } = useI18n();
  const history = useVideoComposerStore(selectVideoHistory);
  const { removeTask, clearHistory } = useVideoComposerStore();

  const statusLabels: Record<string, string> = {
    generating: t("video.filmstrip.status_generating"),
    failed: t("video.filmstrip.status_failed"),
    pending: t("video.filmstrip.status_pending"),
  };

  if (history.length === 0) {
    return null;
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs text-muted-foreground">
          {t("video.filmstrip.recent")} ({history.length})
        </span>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-muted-foreground hover:text-destructive"
                onClick={clearHistory}
              >
                {t("video.filmstrip.clear_all")}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("video.filmstrip.clear_all_tooltip")}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div
        className={cn(
          "flex gap-3 overflow-x-auto pb-2 px-1",
          "scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
        )}
      >
        {history.map((task) => (
          <FilmstripItem
            key={task.id}
            task={task}
            onSelect={() => onSelectVideo?.(task)}
            onRemove={() => removeTask(task.id)}
            statusLabels={statusLabels}
          />
        ))}
      </div>
    </div>
  );
});

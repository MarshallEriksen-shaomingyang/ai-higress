"use client";

import { Download, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useI18n } from "@/lib/i18n-context";
import type { ImageGenerationTask } from "@/lib/chat/composer-tasks";
import { API_BASE_URL } from "@/http/client";
import { resolveApiUrl } from "@/lib/http/resolve-api-url";

interface ImageDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task: ImageGenerationTask;
  selectedImageIndex?: number;
}

export function ImageDetailDialog({
  open,
  onOpenChange,
  task,
  selectedImageIndex = 0,
}: ImageDetailDialogProps) {
  const { t } = useI18n();

  if (!task.result?.data) return null;

  const image = task.result.data[selectedImageIndex];
  if (!image) return null;

  const imageUrl = image.url
    ? resolveApiUrl(image.url, API_BASE_URL)
    : (image.b64_json ? `data:image/png;base64,${image.b64_json}` : "");

  const handleDownload = () => {
    if (!imageUrl) return;
    const a = document.createElement("a");
    a.href = imageUrl;
    a.download = `generated-image-${task.id}-${selectedImageIndex}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0 flex flex-row items-center justify-between">
          <DialogTitle>{t("chat.image_gen.view_details")}</DialogTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleDownload}>
              <Download className="size-4 mr-2" />
              {t("chat.image_gen.download")}
            </Button>
            <DialogClose asChild>
              <Button variant="ghost" size="icon-sm" aria-label={t("chat.action.close")}>
                <X className="size-4" aria-hidden="true" />
              </Button>
            </DialogClose>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* Image Preview Area */}
          <div className="flex-1 bg-black/5 p-4 flex items-center justify-center overflow-auto min-h-[300px]">
            {imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                alt={task.prompt}
                className="max-w-full max-h-full object-contain rounded shadow-sm"
              />
            ) : (
              <div className="text-muted-foreground">{t("chat.image_gen.no_image_data")}</div>
            )}
          </div>

          {/* Details Sidebar */}
          <div className="w-full md:w-80 border-l bg-background flex flex-col shrink-0">
            <ScrollArea className="flex-1 p-6">
              <div className="space-y-6">
                <div>
                  <h4 className="font-medium mb-2 text-sm text-foreground/80">{t("chat.image_gen.prompt")}</h4>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{task.prompt}</p>
                  {image.revised_prompt && (
                    <div className="mt-4 p-3 bg-muted rounded text-xs">
                      <div className="font-semibold mb-1 opacity-70">{t("chat.image_gen.revised_prompt")}</div>
                      {image.revised_prompt}
                    </div>
                  )}
                </div>

                <div>
                  <h4 className="font-medium mb-2 text-sm text-foreground/80">{t("chat.image_gen.params")}</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground">{t("chat.image_gen.model")}</span>
                      <span className="font-mono text-xs">{task.params.model}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground">{t("chat.image_gen.size")}</span>
                      <span className="font-mono text-xs">{task.params.size}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground">{t("chat.image_gen.number")}</span>
                      <span className="font-mono text-xs">{task.params.n}</span>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

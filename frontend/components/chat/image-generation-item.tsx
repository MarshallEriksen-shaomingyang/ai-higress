"use client";

import { useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n-context";
import { ImageDetailDialog } from "./image-detail-dialog";
import type { ImageGenerationTask } from "@/lib/chat/composer-tasks";
import { API_BASE_URL } from "@/http/client";
import { resolveApiUrl } from "@/lib/http/resolve-api-url";

interface ImageGenerationItemProps {
  task: ImageGenerationTask;
}

export function ImageGenerationItem({ task }: ImageGenerationItemProps) {
  const { t } = useI18n();
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);

  if (task.status === "failed") {
    return (
      <Card className="w-full max-w-sm border-destructive/50 bg-destructive/5">
        <CardContent className="p-4 flex flex-col items-center gap-2 text-center">
          <AlertCircle className="size-6 text-destructive" />
          <p className="text-sm font-medium text-destructive">{t("chat.image_gen.failed")}</p>
          <p className="text-xs text-muted-foreground">{task.error}</p>
        </CardContent>
      </Card>
    );
  }

  if (task.status === "pending" || !task.result) {
    return (
      <Card className="w-full max-w-sm">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
             <Loader2 className="size-3 animate-spin" />
             <span>{t("chat.image_gen.generating")}</span>
          </div>
          <Skeleton className="w-full aspect-square rounded-lg" />
          <div className="flex gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-1/4" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const images = task.result.data || [];

  return (
    <>
      <div className="flex flex-col gap-2 w-full max-w-2xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {images.map((img, idx) => {
             const src = img.url
               ? resolveApiUrl(img.url, API_BASE_URL)
               : (img.b64_json ? `data:image/png;base64,${img.b64_json}` : "");
             if (!src) return null;

             return (
               <div 
                 key={idx} 
                 className="group relative aspect-square rounded-xl overflow-hidden border bg-muted/20 cursor-pointer hover:ring-2 hover:ring-primary/50 transition-all"
                 onClick={() => {
                   setSelectedImageIndex(idx);
                   setDetailOpen(true);
                 }}
               >
                 {/* eslint-disable-next-line @next/next/no-img-element */}
                 <img 
                   src={src} 
                   alt={t("chat.image_gen.generated_image_alt", { index: idx + 1 })} 
                   className="w-full h-full object-cover" 
                 />
                 <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
               </div>
             );
          })}
        </div>
        
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground px-1">
           <span className="bg-muted px-1.5 py-0.5 rounded border">{task.params.model}</span>
           <span className="bg-muted px-1.5 py-0.5 rounded border">{task.params.size}</span>
        </div>
      </div>

      <ImageDetailDialog 
        open={detailOpen}
        onOpenChange={setDetailOpen}
        task={task}
        selectedImageIndex={selectedImageIndex}
      />
    </>
  );
}

"use client";

import { Image as ImageIcon, X } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type ImageUploadActionProps = {
  disabled?: boolean;
  onFilesSelected: (files: FileList | null) => void;
  uploadLabel: string;
  className?: string;
};

export function ImageUploadAction({
  disabled = false,
  onFilesSelected,
  uploadLabel,
  className,
}: ImageUploadActionProps) {
  const inputId = useId();

  return (
    <div className={cn("contents", className)}>
      <Input
        id={inputId}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          onFilesSelected(e.target.files);
          e.target.value = "";
        }}
        disabled={disabled}
      />

      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            disabled={disabled}
            aria-label={uploadLabel}
            onClick={() => {
              const el = document.getElementById(inputId);
              if (el instanceof HTMLInputElement) el.click();
            }}
          >
            <ImageIcon className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{uploadLabel}</p>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

export type ImagePreviewGridProps = {
  images: string[];
  disabled?: boolean;
  onRemoveImage: (index: number) => void;
  uploadedAltPrefix: string;
  removeLabel: string;
  className?: string;
};

export function ImagePreviewGrid({
  images,
  disabled = false,
  onRemoveImage,
  uploadedAltPrefix,
  removeLabel,
  className,
}: ImagePreviewGridProps) {
  if (images.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {images.map((url, index) => (
        <div key={`${index}-${url.slice(0, 24)}`} className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={`${uploadedAltPrefix} ${index + 1}`}
            className="h-16 w-16 rounded-md border object-cover"
          />
          <Button
            type="button"
            size="icon-sm"
            variant="destructive"
            className="absolute -right-2 -top-2 h-7 w-7 rounded-full"
            onClick={() => onRemoveImage(index)}
            aria-label={removeLabel}
            disabled={disabled}
          >
            <X className="size-3" />
          </Button>
        </div>
      ))}
    </div>
  );
}

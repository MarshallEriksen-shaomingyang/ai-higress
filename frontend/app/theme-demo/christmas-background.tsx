"use client";

import { useState } from "react";

export function ChristmasBackground() {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none" style={{ zIndex: -1 }}>
      {/* 备用渐变背景 */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-100 via-purple-50 to-pink-100 dark:from-blue-950 dark:via-purple-950 dark:to-pink-950" />

      {/* 圣诞背景图片 (7MB, 可能加载较慢) */}
      {!imageError && (
        <img
          src="/theme/chrismas/background.svg"
          alt="Christmas background"
          className="absolute inset-0 w-full h-full object-cover"
          style={{ 
            opacity: imageLoaded ? 1 : 0,
            transition: "opacity 0.5s ease-in-out"
          }}
          loading="eager"
          onLoad={() => {
            console.log("Christmas background loaded successfully");
            setImageLoaded(true);
          }}
          onError={(e) => {
            console.error("Failed to load Christmas background");
            setImageError(true);
          }}
        />
      )}
      
      {/* 加载提示 */}
      {!imageLoaded && !imageError && (
        <div className="absolute bottom-4 right-4 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded">
          加载背景中... (7MB)
        </div>
      )}
    </div>
  );
}

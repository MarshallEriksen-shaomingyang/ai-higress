"use client";

import { useMediaQuery } from "@/lib/hooks/use-media-query";

export type ResponsiveDrawerDirection = "bottom" | "right";

export function useResponsiveDrawerDirection(): ResponsiveDrawerDirection {
  const isMobile = useMediaQuery("(max-width: 768px)");
  return isMobile ? "bottom" : "right";
}


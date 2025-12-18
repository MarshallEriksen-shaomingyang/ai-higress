"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import Image from "next/image";

export function ThemeBackground() {
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || theme !== "christmas") {
    return null;
  }

  return (
    <div className="fixed inset-0 z-0 pointer-events-none">
      <Image
        src="/theme/christmas/background.png"
        alt="Christmas Background"
        fill
        className="object-cover"
        priority
      />
      <div 
        className="absolute inset-0" 
        style={{
          background: "linear-gradient(180deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.12) 50%, rgba(255, 255, 255, 0.18) 100%)"
        }}
      />
    </div>
  );
}

"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type Language = "en" | "zh";

type Translations = {
  [key in Language]: Record<string, string>;
};

interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

// Cache translations at module level so they are only loaded once per runtime.
let translationsCache: Translations | null = null;
let translationsPromise: Promise<Translations> | null = null;

async function loadAllTranslations(): Promise<Translations> {
  if (translationsCache) {
    return translationsCache;
  }

  if (!translationsPromise) {
    translationsPromise = import("./i18n")
      .then((mod) => mod.allTranslations as Translations)
      .catch((error) => {
        // Fallback to empty translations on error, but keep the app usable.
        console.error("[i18n] Failed to load translations", error);
        return {
          en: {},
          zh: {},
        } as Translations;
      });
  }

  translationsCache = await translationsPromise;
  return translationsCache;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Default to Chinese as per the original design.
  const [language, setLanguageState] = useState<Language>("zh");
  const [translations, setTranslations] = useState<Translations | null>(
    translationsCache
  );

  // Load saved language on mount.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("ai_higress_lang");
      if (saved === "en" || saved === "zh") {
        setLanguageState(saved);
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  // Dynamically load all translations on first mount.
  useEffect(() => {
    if (!translations) {
      loadAllTranslations().then((loaded) => {
        setTranslations(loaded);
      });
    }
  }, [translations]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    try {
      window.localStorage.setItem("ai_higress_lang", lang);
    } catch {
      // ignore storage errors
    }
  };

  const t = (key: string) => {
    if (!translations) {
      // While translations are loading, fall back to the key itself.
      return key;
    }
    return translations[language]?.[key] ?? key;
  };

  return (
    <I18nContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (context === undefined) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}


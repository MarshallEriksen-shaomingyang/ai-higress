import type { Language } from "../i18n-context";
import { commonTranslations } from "./common";
import { navigationTranslations } from "./navigation";
import { overviewTranslations } from "./overview";
import { providersTranslations } from "./providers";
import { routingTranslations } from "./routing";
import { creditsTranslations } from "./credits";
import { providerKeysTranslations } from "./provider-keys";
import { authTranslations } from "./auth";
import { homeTranslations } from "./home";
import { errorTranslations } from "./error";
import { rolesTranslations } from "./roles";
import { usersTranslations } from "./users";

// Function to merge translation objects
const mergeTranslations = (
  ...translationObjects: Record<Language, Record<string, string>>[]
): Record<Language, Record<string, string>> => {
  const result: Record<Language, Record<string, string>> = {
    en: {},
    zh: {},
  };

  translationObjects.forEach((translationObj) => {
    (Object.keys(translationObj) as Language[]).forEach((lang) => {
      result[lang] = { ...result[lang], ...translationObj[lang] };
    });
  });

  return result;
};

// Export merged translations
export const allTranslations = mergeTranslations(
  commonTranslations,
  navigationTranslations,
  overviewTranslations,
  providersTranslations,
  routingTranslations,
  creditsTranslations,
  providerKeysTranslations,
  authTranslations,
  homeTranslations,
  errorTranslations,
  rolesTranslations,
  usersTranslations
);

// Export individual translation modules for dynamic loading
export {
  commonTranslations,
  navigationTranslations,
  overviewTranslations,
  providersTranslations,
  routingTranslations,
  creditsTranslations,
  providerKeysTranslations,
  authTranslations,
  homeTranslations,
  errorTranslations,
  rolesTranslations,
  usersTranslations,
};

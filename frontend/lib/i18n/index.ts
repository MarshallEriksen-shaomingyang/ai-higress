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
import { submissionsTranslations } from "./submissions";
import { sessionsTranslations } from "./sessions";
import { permissionsTranslations } from "./permissions";
import { errorsTranslations } from "./errors";
import { apiKeysTranslations } from "./api-keys";
import { providerPresetsTranslations } from "./provider-presets";
import { metricsTranslations } from "./metrics";
import { systemTranslations } from "./system";
import { profileTranslations } from "./profile";
import { logicalModelsTranslations } from "./logical-models";
import { notificationsTranslations } from "./notifications";
import { cliConfigTranslations } from "./cli-config";
import { themeTranslations } from "./theme";
import { dashboardV2Translations } from "./dashboard";
import { chatTranslations } from "./chat";
import { bridgeTranslations } from "./bridge";
import { requestLogsTranslations } from "./request-logs";
import { legalTranslations } from "./legal";
import { videoTranslations } from "./video";

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
  metricsTranslations,
  providersTranslations,
  routingTranslations,
  creditsTranslations,
  providerKeysTranslations,
  authTranslations,
  homeTranslations,
  errorTranslations,
  rolesTranslations,
  usersTranslations,
  submissionsTranslations,
  sessionsTranslations,
  permissionsTranslations,
  errorsTranslations,
  apiKeysTranslations,
  providerPresetsTranslations,
  systemTranslations,
  profileTranslations,
  logicalModelsTranslations,
  notificationsTranslations,
  cliConfigTranslations,
  themeTranslations,
  dashboardV2Translations,
  chatTranslations,
  bridgeTranslations,
  requestLogsTranslations,
  legalTranslations,
  videoTranslations
);

// Export individual translation modules for dynamic loading
export {
  commonTranslations,
  navigationTranslations,
  overviewTranslations,
  metricsTranslations,
  providersTranslations,
  routingTranslations,
  creditsTranslations,
  providerKeysTranslations,
  authTranslations,
  homeTranslations,
  errorTranslations,
  rolesTranslations,
  usersTranslations,
  submissionsTranslations,
  sessionsTranslations,
  permissionsTranslations,
  errorsTranslations,
  apiKeysTranslations,
  providerPresetsTranslations,
  systemTranslations,
  profileTranslations,
  logicalModelsTranslations,
  notificationsTranslations,
  cliConfigTranslations,
  themeTranslations,
  dashboardV2Translations,
  chatTranslations,
  bridgeTranslations,
  requestLogsTranslations,
  legalTranslations,
  videoTranslations,
};

"use client";

import { useI18n } from '@/lib/i18n-context';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Info } from 'lucide-react';
import { RoutingDecision } from './routing-decision';
import { SessionManagement } from './session-management';

export function RoutingClient() {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">{t('routing.title')}</h1>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-muted-foreground/30 text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                aria-label={t('routing.tooltip.label')}
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              {t('routing.tooltip.description')}
            </TooltipContent>
          </Tooltip>
        </div>
        <p className="text-muted-foreground">{t('routing.description')}</p>
      </div>

      <Tabs defaultValue="decision" className="space-y-6">
        <TabsList>
          <TabsTrigger value="decision">{t('routing.tabs.decision')}</TabsTrigger>
          <TabsTrigger value="session">{t('routing.tabs.session')}</TabsTrigger>
        </TabsList>

        <TabsContent value="decision" className="space-y-6">
          <RoutingDecision />
        </TabsContent>

        <TabsContent value="session" className="space-y-6">
          <SessionManagement />
        </TabsContent>
      </Tabs>
    </div>
  );
}

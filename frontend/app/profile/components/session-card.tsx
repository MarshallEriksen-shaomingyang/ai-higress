"use client";

import { AdaptiveCard, CardContent } from '@/components/cards/adaptive-card';
import { Button } from '@/components/ui/button';
import { Monitor, Smartphone, Tablet, HelpCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { parseUserAgent, formatDeviceInfo } from '@/lib/utils/user-agent-parser';
import { formatRelativeTime } from '@/lib/utils/time-formatter';
import { useI18n } from '@/lib/i18n-context';
import type { SessionResponse } from '@/lib/api-types';

interface SessionCardProps {
  session: SessionResponse;
  onRevoke: (sessionId: string) => void;
}

const iconMap = {
  Monitor,
  Smartphone,
  Tablet,
  HelpCircle,
};

export function SessionCard({ session, onRevoke }: SessionCardProps) {
  const { t, language } = useI18n();
  const parsed = parseUserAgent(session.device_info?.user_agent || null);
  const DeviceIcon = iconMap[parsed.icon];

  return (
    <AdaptiveCard
      showDecor={false}
      className={cn(
        'relative',
        session.is_current && 'bg-muted/30 border-green-500/20'
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3 flex-1">
            <DeviceIcon className="w-5 h-5 text-muted-foreground mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <h4 className="text-sm font-medium">
                  {session.is_current ? (
                    <span className="flex items-center space-x-1.5">
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                      <span>{t('sessions.current_device')}</span>
                    </span>
                  ) : (
                    formatDeviceInfo(parsed)
                  )}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground mb-2">
                {session.device_info?.ip_address || t('sessions.unknown_ip')}
              </p>
              <div className="space-y-0.5 text-xs text-muted-foreground">
                <p>
                  {t('sessions.last_active')}: {formatRelativeTime(session.last_used_at, language)}
                </p>
                <p>
                  {t('sessions.logged_in')}: {formatRelativeTime(session.created_at, language)}
                </p>
              </div>
            </div>
          </div>
          {!session.is_current && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRevoke(session.session_id)}
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
            >
              {t('sessions.revoke')}
            </Button>
          )}
        </div>
      </CardContent>
    </AdaptiveCard>
  );
}

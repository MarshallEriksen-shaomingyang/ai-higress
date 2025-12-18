"use client";

import { useState } from "react";
import {
  AdaptiveCard,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/cards/adaptive-card";
import { Button } from "@/components/ui/button";
import { SessionCard } from "./session-card";
import {
  RevokeSessionDialog,
  RevokeAllSessionsDialog,
} from "./revoke-session-dialog";
import { useSessions, useRevokeSession } from "@/lib/swr/use-sessions";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import type { SessionResponse } from "@/lib/api-types";

export function SessionsCard() {
  const { t } = useI18n();
  const { sessions, loading, refresh } = useSessions();
  const { revokeSession, revokeOtherSessions } = useRevokeSession();

  const [selectedSession, setSelectedSession] = useState<SessionResponse | null>(
    null,
  );
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);
  const [showRevokeAllDialog, setShowRevokeAllDialog] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);

  const otherSessionsCount = sessions.filter((s) => !s.is_current).length;

  const handleRevoke = (sessionId: string) => {
    const session = sessions.find((s) => s.session_id === sessionId);
    if (session) {
      setSelectedSession(session);
      setShowRevokeDialog(true);
    }
  };

  const handleConfirmRevoke = async () => {
    if (!selectedSession) return;

    setIsRevoking(true);
    try {
      await revokeSession(selectedSession.session_id);
      toast.success(t("sessions.revoke_success"));
      setShowRevokeDialog(false);
      refresh();
    } catch (error) {
      toast.error(t("sessions.revoke_error"));
    } finally {
      setIsRevoking(false);
    }
  };

  const handleRevokeAll = async () => {
    setIsRevoking(true);
    try {
      await revokeOtherSessions();
      toast.success(t("sessions.revoke_all_success"));
      setShowRevokeAllDialog(false);
      refresh();
    } catch (error) {
      toast.error(t("sessions.revoke_all_error"));
    } finally {
      setIsRevoking(false);
    }
  };

  return (
    <>
      <AdaptiveCard showDecor={false}>
        <CardHeader>
          <CardTitle>{t("sessions.title")}</CardTitle>
          <CardDescription>{t("sessions.description")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              {t("common.loading") || "Loading..."}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t("sessions.no_sessions")}
            </div>
          ) : (
            <>
              {sessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  onRevoke={handleRevoke}
                />
              ))}

              {otherSessionsCount > 0 && (
                <div className="pt-4 border-t">
                  <Button
                    variant="outline"
                    className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => setShowRevokeAllDialog(true)}
                  >
                    {t("sessions.revoke_all_other_sessions")} (
                    {otherSessionsCount})
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </AdaptiveCard>

      <RevokeSessionDialog
        open={showRevokeDialog}
        onOpenChange={setShowRevokeDialog}
        session={selectedSession}
        onConfirm={handleConfirmRevoke}
        isRevoking={isRevoking}
      />

      <RevokeAllSessionsDialog
        open={showRevokeAllDialog}
        onOpenChange={setShowRevokeAllDialog}
        sessionCount={otherSessionsCount}
        onConfirm={handleRevokeAll}
        isRevoking={isRevoking}
      />
    </>
  );
}

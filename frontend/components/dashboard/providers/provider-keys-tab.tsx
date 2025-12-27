"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Key } from "lucide-react";
import type { Provider } from "@/http/provider";

interface ProviderKeysTabProps {
  providerId: string;
  provider: Provider;
  canManage: boolean;
  translations: {
    title: string;
    description: string;
    noKeys: string;
    unnamed: string;
    weight: string;
    maxQps: string;
  };
  actionManageKeys: string;
}

export const ProviderKeysTab = ({ 
  providerId,
  provider, 
  canManage, 
  translations,
  actionManageKeys 
}: ProviderKeysTabProps) => {
  const router = useRouter();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{translations.title}</CardTitle>
          <CardDescription>{translations.description}</CardDescription>
        </div>
        {canManage && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/dashboard/providers/${providerId}/keys`)}
          >
            <Key className="w-4 h-4 mr-1" />
            {actionManageKeys}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {!provider.api_keys || provider.api_keys.length === 0 ? (
          <div className="text-sm text-muted-foreground py-8 text-center">
            {translations.noKeys}
          </div>
        ) : (
          <div className="space-y-4">
            {provider.api_keys.map((key, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div>
                  <div className="font-medium">{key.label || translations.unnamed}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {translations.weight}: {key.weight} | {translations.maxQps}: {key.max_qps}
                  </div>
                </div>
                <code className="text-sm font-mono bg-muted px-2 py-1 rounded">
                  {key.key.substring(0, 8)}...
                </code>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

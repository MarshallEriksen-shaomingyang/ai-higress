"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Layers } from "lucide-react";
import type { ModelsResponse } from "@/http/provider";
import { ModelCard } from "./model-card";

interface ProviderModelsTabProps {
  providerId: string;
  models?: ModelsResponse;
  canEdit: boolean;
  onEditPricing: (modelId: string) => void;
  onEditAlias: (modelId: string) => void;
  onRefresh: () => Promise<void>;
  translations: {
    title: string;
    description: string;
    noModels: string;
  };
}

export const ProviderModelsTab = ({
  providerId,
  models,
  canEdit,
  onEditPricing,
  onEditAlias,
  onRefresh,
  translations
}: ProviderModelsTabProps) => {
  const modelCount = models?.models?.length || 0;
  
  return (
    <div className="space-y-6">
      {/* 标题区域 */}
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-xl bg-primary/10 text-primary">
          <Layers className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold tracking-tight mb-1">
            {translations.title}
          </h2>
          <p className="text-muted-foreground">
            {translations.description}
            {modelCount > 0 && (
              <span className="ml-2 text-primary font-medium">
                • {modelCount} {modelCount === 1 ? 'model' : 'models'}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* 模型卡片网格 */}
      {!models?.models || models.models.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="p-4 rounded-full bg-muted mb-4">
              <Layers className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground text-center">
              {translations.noModels}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {models.models.map((model) => (
            <ModelCard
              key={model.model_id}
              providerId={providerId}
              model={model}
              canEdit={canEdit}
              onEditPricing={() => onEditPricing(model.model_id)}
              onEditAlias={() => onEditAlias(model.model_id)}
              onRefresh={onRefresh}
            />
          ))}
        </div>
      )}
    </div>
  );
};

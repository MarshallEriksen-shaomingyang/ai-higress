import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useAdminSystemConfig, useUpsertAdminSystemConfig, KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY } from '@/lib/swr';

export function useGlobalEmbeddingModelForm(t: (key: string) => string) {
  const { config, loading, error, refresh, isSuperUser } = useAdminSystemConfig(
    KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY,
    true
  );
  const { upsert, submitting } = useUpsertAdminSystemConfig();
  const [value, setValue] = useState<string>('');

  useEffect(() => {
    if (config) {
      setValue(config.value ?? '');
    }
  }, [config]);

  const currentSourceLabel = useMemo(() => {
    if (!config?.source) return '';
    return config.source === 'db' ? t('system.embedding.source_db') : t('system.embedding.source_env');
  }, [config?.source, t]);

  const handleReset = () => {
    setValue(config?.value ?? '');
  };

  const handleSave = async () => {
    try {
      const normalized = value.trim();
      const updated = await upsert({
        key: KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY,
        value: normalized ? normalized : null,
        description: t('system.embedding.description_db'),
      });
      setValue(updated.value ?? '');
      await refresh();
      toast.success(t('system.embedding.save_success'));
    } catch (e: any) {
      const message =
        e?.response?.data?.detail || e?.message || t('system.embedding.save_error');
      toast.error(message);
    }
  };

  const disabled = loading || submitting || !isSuperUser;

  return {
    value,
    setValue,
    loading,
    error,
    saving: submitting,
    disabled,
    isSuperUser,
    currentSourceLabel,
    handleReset,
    handleSave,
  };
}


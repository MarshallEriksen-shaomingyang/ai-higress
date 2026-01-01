import { describe, it, expect, vi, beforeEach } from 'vitest';

const STORAGE_KEY = 'user-preferences';

async function importStore() {
  vi.resetModules();
  const mod = await import('@/lib/stores/user-preferences-store');
  return mod.useUserPreferencesStore;
}

describe('lib: user-preferences-store', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('应将旧版本偏好迁移并补齐 TTS 格式字段', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 3,
        state: {
          preferences: {
            sendShortcut: 'ctrl-enter',
            preferredChatModelByProject: {},
            preferredImageModelByProject: {},
            preferredTtsModelByProject: {},
          },
        },
      })
    );

    const store = await importStore();
    await store.persist.rehydrate();

    const prefs = store.getState().preferences;
    expect(prefs.preferredTtsFormatByProject).toEqual({});
  });

  it('setPreferredTtsFormat 应按项目写入/删除', async () => {
    const store = await importStore();
    await store.persist.rehydrate();

    store.getState().setPreferredTtsFormat('proj-1', 'mp3');
    expect(store.getState().preferences.preferredTtsFormatByProject['proj-1']).toBe('mp3');

    store.getState().setPreferredTtsFormat('proj-1', null);
    expect(store.getState().preferences.preferredTtsFormatByProject['proj-1']).toBeUndefined();
  });
});


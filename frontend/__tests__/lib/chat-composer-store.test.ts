import { describe, it, expect } from 'vitest';

import { getConversationComposerState } from '@/lib/stores/chat-composer-store';

describe('lib: chat-composer-store', () => {
  it('getConversationComposerState 对缺失会话应返回稳定引用（避免 useSyncExternalStore 警告）', () => {
    const state = { byConversationId: {} };
    const first = getConversationComposerState(state, 'conv-1');
    const second = getConversationComposerState(state, 'conv-1');
    expect(first).toBe(second);
  });

  it('当会话已存在时应返回原对象引用', () => {
    const existing = {
      activeMode: 'image' as const,
      image: { model: 'm', size: '512x512', n: 2 },
    };
    const state = { byConversationId: { 'conv-2': existing } };
    expect(getConversationComposerState(state, 'conv-2')).toBe(existing);
  });
});


import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { MessageTtsControl } from '@/components/chat/message-tts-control';
import { useUserPreferencesStore } from '@/lib/stores/user-preferences-store';

const toastError = vi.fn();

vi.mock('sonner', () => ({
  toast: {
    error: (...args: any[]) => toastError(...args),
  },
}));

vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    language: 'zh',
  }),
}));

const getAudio = vi.fn();

vi.mock('@/lib/swr/use-tts', () => ({
  useMessageSpeechAudio: () => ({
    getAudio: (...args: any[]) => getAudio(...args),
    loading: false,
    error: null,
    audio: null,
    reset: vi.fn(),
  }),
}));

class FakeAudio {
  static instances: FakeAudio[] = [];
  src: string;
  preload = "";
  currentTime = 0;
  onended: (() => void) | null = null;
  onpause: (() => void) | null = null;
  onplay: (() => void) | null = null;
  play = vi.fn(async () => {
    this.onplay?.();
  });
  pause = vi.fn(() => {
    this.onpause?.();
  });

  constructor(src: string) {
    this.src = src;
    FakeAudio.instances.push(this);
  }
}

describe('UI: MessageTtsControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    useUserPreferencesStore.getState().resetPreferences();
    FakeAudio.instances = [];
    getAudio.mockImplementationOnce(async () => ({
      blob: new Blob(['a']),
      contentType: 'audio/wav',
      objectUrl: 'blob:tts-1',
      createdAt: Date.now(),
    }));
    getAudio.mockImplementationOnce(async () => ({
      blob: new Blob(['b']),
      contentType: 'audio/wav',
      objectUrl: 'blob:tts-2',
      createdAt: Date.now(),
    }));
    vi.stubGlobal('Audio', FakeAudio as any);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('当复用的 Audio 源不可用时应重新拉取并播放', async () => {
    const user = userEvent.setup();

    render(<MessageTtsControl messageId="msg-1" fallbackModel="tts-model" />);

    // 1) 第一次点击：拉取音频并播放
    const button = screen.getByRole('button', { name: 'chat.tts.play' });
    await user.click(button);

    await waitFor(() => expect(getAudio).toHaveBeenCalledTimes(1));
    expect(FakeAudio.instances).toHaveLength(1);

    // 2) 点击暂停
    const pauseButton = screen.getByRole('button', { name: 'chat.tts.pause' });
    await user.click(pauseButton);

    // 3) 模拟已缓存/已 revoke 的旧 objectUrl：再次播放时抛 NotSupportedError
    FakeAudio.instances[0].play = vi.fn(async () => {
      throw new DOMException(
        'Failed to load because no supported source was found.',
        'NotSupportedError'
      );
    });

    const playAgainButton = screen.getByRole('button', { name: 'chat.tts.play' });
    await user.click(playAgainButton);

    await waitFor(() => expect(getAudio).toHaveBeenCalledTimes(2));
    expect(FakeAudio.instances).toHaveLength(2);
    expect(FakeAudio.instances[1].src).toBe('blob:tts-2');
    expect(toastError).not.toHaveBeenCalled();
  });

  it('应把项目偏好的 voice/speed/format 传给 getAudio', async () => {
    const user = userEvent.setup();

    useUserPreferencesStore.getState().setPreferredTtsModel('proj-1', 'tts-model-1');
    useUserPreferencesStore.getState().setPreferredTtsFormat('proj-1', 'wav');
    useUserPreferencesStore.getState().setPreferredTtsVoice('proj-1', 'shimmer');
    useUserPreferencesStore.getState().setPreferredTtsSpeed('proj-1', 1.5);

    render(<MessageTtsControl messageId="msg-1" projectId="proj-1" fallbackModel="fallback" />);

    const button = screen.getByRole('button', { name: 'chat.tts.play' });
    await user.click(button);

    await waitFor(() => expect(getAudio).toHaveBeenCalledTimes(1));
    expect(getAudio).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'tts-model-1',
        voice: 'shimmer',
        response_format: 'wav',
        speed: 1.5,
      })
    );
  });
});

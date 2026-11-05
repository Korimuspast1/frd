import type { RemoteServerConfig } from '../types/opencode';
import { PlatformBridge } from '../bridge/platformBridge';

/**
 * Official `opencode serve` v2 Remote Server Client!
 * Connects Android directly to a PC / VPS / Termux running `opencode serve`
 * via HTTP URL + Password OR OpenCode Pairing Link / QR payload.
 */
export const RemoteOpenCodeClient = {
  buildHeaders(cfg: RemoteServerConfig): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    };
    if (cfg.pairingToken) {
      headers['Authorization'] = `Bearer ${cfg.pairingToken}`;
    } else if (cfg.password) {
      const basic = btoa(`opencode:${cfg.password}`);
      headers['Authorization'] = `Basic ${basic}`;
    }
    return headers;
  },

  async probeServer(cfg: RemoteServerConfig): Promise<{ ok: boolean; version?: string; error?: string }> {
    const cleanUrl = cfg.url.trim().replace(/\/$/, '');
    if (!cleanUrl) return { ok: false, error: 'Укажите адрес сервера (например http://192.168.1.10:4096)' };

    try {
      const res = await PlatformBridge.proxyStream(
        `${cleanUrl}/global/health`,
        'GET',
        this.buildHeaders(cfg),
        undefined,
      );
      if (res.ok) {
        const json = await res.json().catch(() => ({}));
        return { ok: true, version: json.version || '2.x' };
      }
      // Try /session fallback for older OpenCode servers
      const fallback = await PlatformBridge.proxyStream(
        `${cleanUrl}/session`,
        'GET',
        this.buildHeaders(cfg),
        undefined,
      );
      if (fallback.ok) {
        return { ok: true, version: 'opencode-server' };
      }
      return { ok: false, error: `Сервер ответил HTTP ${res.status}` };
    } catch (err: any) {
      return { ok: false, error: err?.message || 'Не удалось подключиться к opencode serve' };
    }
  },

  async redeemPairingInput(rawInput: string): Promise<{ url: string; token?: string } | null> {
    const trimmed = rawInput.trim();
    // Format 1: JSON QR payload {"code":"...","urls":["http://..."]}
    if (trimmed.startsWith('{')) {
      try {
        const parsed = JSON.parse(trimmed) as { code?: string; urls?: string[] };
        if (parsed.code && Array.isArray(parsed.urls)) {
          for (const candidate of parsed.urls) {
            const base = candidate.replace(/\/$/, '');
            const res = await PlatformBridge.proxyStream(
              `${base}/auth/connect/${encodeURIComponent(parsed.code)}`,
              'POST',
              { 'Content-Type': 'application/json' },
              {},
            );
            if (res.ok) {
              const data = await res.json();
              return { url: base, token: data.token || data.password };
            }
          }
        }
      } catch {
        return null;
      }
    }
    // Format 2: Pairing URL http://host:4096/auth/connect/<code>
    const match = trimmed.match(/^(https?:\/\/[^/]+)\/auth\/connect\/([^/?#]+)/i);
    if (match) {
      const [, base, code] = match;
      const res = await PlatformBridge.proxyStream(
        `${base}/auth/connect/${encodeURIComponent(code)}`,
        'POST',
        { 'Content-Type': 'application/json' },
        {},
      );
      if (res.ok) {
        const data = await res.json();
        return { url: base, token: data.token || data.password };
      }
    }
    return null;
  },

  async sendRemotePrompt(params: {
    cfg: RemoteServerConfig;
    remoteSessionId?: string;
    agent: string;
    prompt: string;
  }): Promise<{ remoteSessionId: string; replyText: string }> {
    const base = params.cfg.url.replace(/\/$/, '');
    const headers = this.buildHeaders(params.cfg);

    let sid = params.remoteSessionId;
    if (!sid) {
      const createRes = await PlatformBridge.proxyStream(`${base}/session`, 'POST', headers, {});
      if (!createRes.ok) {
        throw new Error(`Не удалось создать сессию на ПК (${createRes.status})`);
      }
      const created = await createRes.json();
      sid = created.id;
    }

    const msgRes = await PlatformBridge.proxyStream(`${base}/session/${sid}/message`, 'POST', headers, {
      agent: params.agent,
      parts: [{ type: 'text', text: params.prompt }],
    });
    if (!msgRes.ok) {
      const errTxt = await msgRes.text();
      throw new Error(`Ошибка ответа ПК-сервера (${msgRes.status}): ${errTxt.slice(0, 300)}`);
    }
    const data = await msgRes.json();
    const parts = Array.isArray(data?.parts) ? data.parts : [];
    const replyText =
      parts
        .map((p: any) => (p.type === 'text' ? p.text : p.type === 'tool' ? `[Tool: ${p.tool}]` : ''))
        .filter(Boolean)
        .join('\n\n') || JSON.stringify(data, null, 2);

    return { remoteSessionId: sid!, replyText };
  },
};

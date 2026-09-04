// Clipboard Intelligence service (Phase 3).
//
// Mirrors the shape of `screen.ts`:
//   * Tauri `invoke` for the local capture command
//     (`clipboard_capture_now`) and other Tauri-side actions.
//   * The backend HTTP API for listing, deleting, pinning, clearing,
//     explaining, and summarising stored items.

import { invoke } from '@tauri-apps/api/core';
import type {
  ClipboardCaptureRequest,
  ClipboardCaptureResponse,
  ClipboardHistoryResponse,
  ClipboardItem,
  ClipboardLLMResponse,
} from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'HttpError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === 'string') {
        detail = body.detail;
      }
    } catch {
      // ignore parse error
    }
    throw new HttpError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Tauri-side commands
// ---------------------------------------------------------------------------

/** Read the current OS clipboard and POST it to the backend. */
export function captureClipboardNow(
  sourceApp?: string,
): Promise<ClipboardCaptureResponse> {
  return invoke<ClipboardCaptureResponse>('clipboard_capture_now', {
    sourceApp: sourceApp ?? null,
  });
}

// ---------------------------------------------------------------------------
// Backend HTTP API
// ---------------------------------------------------------------------------

export interface ListClipboardOptions {
  limit?: number;
  offset?: number;
  content_type?: string;
  classification?: string;
  include_sensitive?: boolean;
}

export function listClipboard(
  opts: ListClipboardOptions = {},
): Promise<ClipboardHistoryResponse> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts.content_type) params.set('content_type', opts.content_type);
  if (opts.classification) params.set('classification', opts.classification);
  if (opts.include_sensitive !== undefined) {
    params.set('include_sensitive', String(opts.include_sensitive));
  }
  const qs = params.toString();
  return request<ClipboardHistoryResponse>(
    `/api/v1/clipboard${qs ? `?${qs}` : ''}`,
  );
}

export function getClipboardItem(id: number | string): Promise<ClipboardItem> {
  return request<ClipboardItem>(`/api/v1/clipboard/${id}`);
}

export function captureClipboardBackend(
  body: ClipboardCaptureRequest,
): Promise<ClipboardCaptureResponse> {
  return request<ClipboardCaptureResponse>('/api/v1/clipboard/capture', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function pinClipboardItem(
  id: number | string,
  pinned: boolean,
): Promise<ClipboardItem> {
  return request<ClipboardItem>(`/api/v1/clipboard/${id}/pin`, {
    method: 'PATCH',
    body: JSON.stringify({ pinned }),
  });
}

export function deleteClipboardItem(
  id: number | string,
): Promise<{ success: boolean; affected: number; detail: string | null }> {
  return request(`/api/v1/clipboard/${id}`, { method: 'DELETE' });
}

export function clearClipboardHistory(
  keepPinned: boolean = true,
): Promise<{ success: boolean; affected: number; detail: string | null }> {
  return request(`/api/v1/clipboard?keep_pinned=${keepPinned}`, {
    method: 'DELETE',
  });
}

export function reanalyseClipboardItem(
  id: number | string,
): Promise<ClipboardItem> {
  return request<ClipboardItem>(`/api/v1/clipboard/${id}/reanalyse`, {
    method: 'POST',
    body: '{}',
  });
}

export function explainClipboardItem(
  id: number | string,
): Promise<ClipboardLLMResponse> {
  return request<ClipboardLLMResponse>(`/api/v1/clipboard/${id}/explain`, {
    method: 'POST',
    body: '{}',
  });
}

export function summariseClipboardItem(
  id: number | string,
): Promise<ClipboardLLMResponse> {
  return request<ClipboardLLMResponse>(`/api/v1/clipboard/${id}/summarise`, {
    method: 'POST',
    body: '{}',
  });
}

export function purgeExpiredClipboard(): Promise<{
  success: boolean;
  affected: number;
}> {
  return request('/api/v1/clipboard/purge', { method: 'POST', body: '{}' });
}

export { HttpError };

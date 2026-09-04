// Screen Intelligence service (Phase 2).
//
// Two transport layers are used here:
//   1. Tauri `invoke` for the local screen-capture command
//      (capture_screen_now) and for events from the global hotkey.
//   2. The backend HTTP API for OCR/classification/listing/Q&A. The
//      backend base URL is taken from `import.meta.env.VITE_API_URL`
//      with the same default as the existing httpClient.

import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type {
  CaptureScreenNowRequest,
  CaptureScreenNowResponse,
  ScreenAnalysis,
  ScreenCaptureBackendRequest,
  ScreenCaptureBackendResponse,
  ScreenClassifierInfo,
  ScreenListResponse,
  ScreenOCRInfo,
  ScreenScreenshot,
  ScreenUpdateRequest,
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
// Tauri-side (local) commands
// ---------------------------------------------------------------------------

/** Trigger the native screen-capture provider from the Rust side. */
export function captureScreenNow(
  request: CaptureScreenNowRequest = {},
): Promise<CaptureScreenNowResponse> {
  return invoke<CaptureScreenNowResponse>('capture_screen_now', { request });
}

/**
 * Subscribe to `screen-capture-requested` events emitted by the global
 * hotkey (Ctrl+Shift+S) and by the tray "Capture" item. Returns an
 * unlisten function — call it on component unmount.
 */
export function onScreenCaptureRequested(
  callback: () => void,
): Promise<UnlistenFn> {
  return listen('screen-capture-requested', () => {
    callback();
  });
}

// ---------------------------------------------------------------------------
// Backend HTTP API
// ---------------------------------------------------------------------------

export interface ListScreensOptions {
  limit?: number;
  offset?: number;
  classification?: string;
  includeArchived?: boolean;
  search?: string;
}

export function listScreens(opts: ListScreensOptions = {}): Promise<ScreenListResponse> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts.classification) params.set('classification', opts.classification);
  if (opts.includeArchived) params.set('include_archived', 'true');
  if (opts.search) params.set('search', opts.search);
  const qs = params.toString();
  return request<ScreenListResponse>(`/api/v1/screen${qs ? `?${qs}` : ''}`);
}

export function getScreen(id: number | string): Promise<ScreenScreenshot> {
  return request<ScreenScreenshot>(`/api/v1/screen/${id}`);
}

export function captureScreenBackend(
  body: ScreenCaptureBackendRequest,
): Promise<ScreenCaptureBackendResponse> {
  return request<ScreenCaptureBackendResponse>('/api/v1/screen/capture', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function updateScreen(
  id: number | string,
  body: ScreenUpdateRequest,
): Promise<ScreenScreenshot> {
  return request<ScreenScreenshot>(`/api/v1/screen/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function deleteScreen(id: number | string): Promise<{ id: string; success: boolean }> {
  return request<{ id: string; success: boolean }>(`/api/v1/screen/${id}`, {
    method: 'DELETE',
  });
}

export function reanalyseScreen(
  id: number | string,
): Promise<{ success: boolean; classification?: string; classification_confidence?: number }> {
  return request(`/api/v1/screen/${id}/reanalyse`, { method: 'POST', body: '{}' });
}

export function summariseScreen(
  id: number | string,
): Promise<ScreenAnalysis> {
  return request<ScreenAnalysis>(`/api/v1/screen/${id}/summarise`, {
    method: 'POST',
    body: '{}',
  });
}

export function askScreen(
  id: number | string,
  question: string,
): Promise<ScreenAnalysis> {
  return request<ScreenAnalysis>(`/api/v1/screen/${id}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

export function listScreenAnalyses(
  id: number | string,
): Promise<ScreenAnalysis[]> {
  return request<ScreenAnalysis[]>(`/api/v1/screen/${id}/analyses`);
}

export function getOCRInfo(): Promise<ScreenOCRInfo> {
  return request<ScreenOCRInfo>('/api/v1/screen/ocr/info');
}

export function getClassifierInfo(): Promise<ScreenClassifierInfo> {
  return request<ScreenClassifierInfo>('/api/v1/screen/classifier/info');
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { HttpError };

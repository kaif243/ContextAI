// File Intelligence service (Phase 4)

import { invoke } from '@tauri-apps/api/core';

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
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      // ignore
    }
    throw new HttpError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function selectFileNative(): Promise<any> {
  return invoke('file_select');
}

export interface ListFilesOptions {
  limit?: number;
  offset?: number;
  classification?: string;
  file_type?: string;
  extension?: string;
}

export function listFiles(opts: ListFilesOptions = {}): Promise<any> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts.classification) params.set('classification', opts.classification);
  if (opts.file_type) params.set('file_type', opts.file_type);
  if (opts.extension) params.set('extension', opts.extension);
  const qs = params.toString();
  return request(`/api/v1/files${qs ? `?${qs}` : ''}`);
}

export interface SearchFilesOptions {
  query?: string;
  classification?: string;
  file_type?: string;
  extension?: string;
  status?: string;
  limit?: number;
}

export function searchFiles(opts: SearchFilesOptions = {}): Promise<any> {
  return request('/api/v1/files/search', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export function selectFileBackend(path: string): Promise<any> {
  return request('/api/v1/files/select', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export function getFileStats(): Promise<any> {
  return request('/api/v1/files/stats');
}

export { HttpError };

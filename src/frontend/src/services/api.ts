// Frontend API Service - wraps Tauri invoke calls

import { invoke } from '@tauri-apps/api/core';
import type {
  AppInfo,
  HealthResponse,
  Settings,
  UpdateSettingsRequest,
  ScreenCaptureRequest,
  ScreenCaptureResponse,
  ClipboardHistoryResponse,
  FileIndexRequest,
  FileIndexResponse,
  FileSearchRequest,
  FileSearchResponse,
} from '@/types';

export const api = {
  // App info
  getAppInfo: (): Promise<AppInfo> => invoke('get_app_info'),

  // Health
  checkHealth: (): Promise<HealthResponse> => invoke('check_backend_health'),

  // Settings
  getSettings: (): Promise<Settings> => invoke('get_settings'),
  updateSettings: (request: UpdateSettingsRequest): Promise<Settings> =>
    invoke('update_settings', { request }),

  // Screen
  captureScreen: (request: ScreenCaptureRequest): Promise<ScreenCaptureResponse> =>
    invoke('screen_capture', { request }),

  // Clipboard
  getClipboardHistory: (limit?: number, offset?: number): Promise<ClipboardHistoryResponse> =>
    invoke('clipboard_get_history', { limit, offset }),

  // Files
  indexFolder: (request: FileIndexRequest): Promise<FileIndexResponse> =>
    invoke('file_index_folder', { request }),
  searchFiles: (request: FileSearchRequest): Promise<FileSearchResponse> =>
    invoke('file_search', { request }),
};

// HTTP client for direct backend communication (WebSocket, file uploads, etc.)
const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000';

class HttpClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  put<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const httpClient = new HttpClient(API_BASE);

// WebSocket connection for real-time updates
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<(data: unknown) => void>> = new Map();
  private onOpenCallback?: () => void;
  private onCloseCallback?: () => void;
  private onErrorCallback?: (error: Event) => void;

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(`${WS_BASE}/ws`);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.onOpenCallback?.();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.notifyListeners(message.type, message.data);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.onCloseCallback?.();
          this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.onErrorCallback?.(error);
          if (this.reconnectAttempts === 0) {
            reject(error);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(), delay);
    }
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }

  send(type: string, data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    }
  }

  on(type: string, callback: (data: unknown) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(callback);
    return () => this.off(type, callback);
  }

  off(type: string, callback: (data: unknown) => void) {
    this.listeners.get(type)?.delete(callback);
  }

  private notifyListeners(type: string, data: unknown) {
    this.listeners.get(type)?.forEach((callback) => callback(data));
  }

  onOpen(callback: () => void) {
    this.onOpenCallback = callback;
  }

  onClose(callback: () => void) {
    this.onCloseCallback = callback;
  }

  onError(callback: (error: Event) => void) {
    this.onErrorCallback = callback;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const wsClient = new WebSocketClient();
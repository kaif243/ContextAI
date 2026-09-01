// Type definitions for ContextAI Frontend

export interface AppInfo {
  name: string;
  version: string;
  description: string;
  backend_connected: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  services: ServiceStatus;
}

export interface ServiceStatus {
  database: boolean;
  vector_store: boolean;
  ml_models: boolean;
  ocr: boolean;
}

export interface Settings {
  hotkey: string;
  auto_start: boolean;
  minimize_to_tray: boolean;
  privacy_mode: boolean;
  clipboard_monitoring: boolean;
  screen_monitoring: boolean;
  file_indexing_enabled: boolean;
  llm_provider: string;
  llm_model: string;
  log_level: string;
}

export interface UpdateSettingsRequest {
  hotkey?: string;
  auto_start?: boolean;
  minimize_to_tray?: boolean;
  privacy_mode?: boolean;
  clipboard_monitoring?: boolean;
  screen_monitoring?: boolean;
  file_indexing_enabled?: boolean;
  llm_provider?: string;
  llm_model?: string;
  log_level?: string;
}

export interface ScreenRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ScreenCaptureRequest {
  region?: ScreenRegion;
  include_cursor: boolean;
}

export interface ScreenCaptureResponse {
  success: boolean;
  image_path?: string;
  width: number;
  height: number;
  error?: string;
}

export interface ClipboardItem {
  id: string;
  content: string;
  content_type: string;
  timestamp: string;
  is_pinned: boolean;
}

export interface ClipboardHistoryResponse {
  items: ClipboardItem[];
  total: number;
}

export interface FileIndexRequest {
  folder_path: string;
  recursive: boolean;
  include_patterns?: string[];
  exclude_patterns?: string[];
}

export interface FileIndexResponse {
  success: boolean;
  files_indexed: number;
  errors: string[];
}

export interface FileSearchRequest {
  query: string;
  folder_path?: string;
  file_types?: string[];
  limit?: number;
  semantic: boolean;
}

export interface FileSearchResult {
  path: string;
  name: string;
  size: number;
  modified: string;
  score: number;
  match_type: string;
}

export interface FileSearchResponse {
  results: FileSearchResult[];
  total: number;
  query_time_ms: number;
}

export interface AgentTask {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  request: string;
  plan?: string;
  created_at: string;
  updated_at: string;
  steps: AgentStep[];
}

export interface AgentStep {
  id: string;
  task_id: string;
  step_number: number;
  action: string;
  tool?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface MemoryItem {
  id: string;
  title: string;
  content: string;
  type: 'note' | 'document' | 'snippet' | 'task' | 'date' | 'other';
  tags: string[];
  created_at: string;
  updated_at: string;
  is_pinned: boolean;
}

export interface MLModelMetrics {
  model_name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  dataset_size: number;
  inference_time_ms: number;
  confusion_matrix?: number[][];
  last_evaluated: string;
}

export interface NavigationItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  badge?: number;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
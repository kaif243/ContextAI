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

// ---------------------------------------------------------------------------
// Phase 2: Screen Intelligence
// ---------------------------------------------------------------------------

/** OCR engine name reported by the backend. */
export type OCREngine = 'mock' | 'tesseract' | 'paddle' | string;

/** Activity-classifier label set returned by the backend baseline. */
export type ActivityLabel =
  | 'code'
  | 'terminal'
  | 'error'
  | 'documentation'
  | 'browser'
  | 'chat'
  | 'email'
  | 'spreadsheet'
  | 'design'
  | 'media'
  | 'unknown'
  | string;

export interface ScreenEntityExtraction {
  dates: string[];
  times: string[];
  urls: string[];
  emails: string[];
  amounts: string[];
  names: string[];
  phone_numbers: string[];
  extra?: Record<string, unknown>;
}

export interface ScreenOCRInfo {
  provider: string;
  available: boolean;
  is_ml: boolean;
  note: string;
  settings_provider: string;
}

export interface ScreenClassifierInfo {
  name: string;
  version: string;
  is_ml: boolean;
  label_count: number;
  note: string;
}

/** Single screenshot as returned by /api/v1/screen. */
export interface ScreenScreenshot {
  id: number | string;
  file_path: string;
  file_name: string;
  width: number;
  height: number;
  file_size_bytes: number;
  content_hash?: string | null;
  region?: { x: number; y: number; width: number; height: number } | null;
  monitor_index?: number | null;
  ocr: {
    engine: string;
    text: string;
    confidence: number;
    word_count: number;
    char_count: number;
    regions: Array<{
      text: string;
      confidence: number;
      bbox: { x: number; y: number; width: number; height: number };
    }>;
    processing_ms?: number;
  } | null;
  classification: string | null;
  classification_confidence: number | null;
  classifier_version: string | null;
  extracted_entities: ScreenEntityExtraction | null;
  source_app: string | null;
  window_title: string | null;
  is_saved: boolean;
  is_archived: boolean;
  user_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScreenListResponse {
  items: ScreenScreenshot[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScreenCaptureBackendRequest {
  image_base64?: string;
  image_path?: string;
  width: number;
  height: number;
  source_app?: string;
  window_title?: string;
  run_ocr?: boolean;
  save_to_disk?: boolean;
  file_name?: string;
}

export interface ScreenCaptureBackendResponse {
  success: boolean;
  screenshot_id?: number | null;
  image_path: string;
  width: number;
  height: number;
  file_size_bytes: number;
  ocr_engine?: string | null;
  ocr_char_count?: number;
  ocr_word_count?: number;
  classification?: string | null;
  classification_confidence?: number | null;
  classifier_version?: string | null;
  extracted_entities?: ScreenEntityExtraction | null;
  error?: string | null;
}

/** Tauri-side local capture (no backend round-trip). */
export interface CaptureScreenNowRequest {
  region?: ScreenRegion;
  save_to_path?: string;
}

export interface CaptureScreenNowResponse {
  success: boolean;
  provider: string;
  width: number;
  height: number;
  image_base64: string | null;
  image_path: string | null;
  error: string | null;
}

export interface ScreenAnalysis {
  id: number;
  screenshot_id: number;
  analysis_type: 'qa' | 'summary' | string;
  question: string | null;
  answer: string;
  model_used: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  processing_ms: number | null;
  is_error: boolean;
  error_message: string | null;
  created_at: string;
}

export interface ScreenUpdateRequest {
  notes?: string;
  is_archived?: boolean;
}
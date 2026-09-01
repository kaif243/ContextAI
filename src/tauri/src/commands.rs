//! Tauri Commands - Frontend accessible Rust functions

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State, Window};
use tracing::{info, debug, error, warn};
use crate::state::AppState;

#[derive(Debug, Serialize, Deserialize)]
pub struct AppInfo {
    pub name: String,
    pub version: String,
    pub description: String,
    pub backend_connected: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub backend_url: String,
    pub timestamp: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Settings {
    pub hotkey: String,
    pub auto_start: bool,
    pub minimize_to_tray: bool,
    pub privacy_mode: bool,
    pub clipboard_monitoring: bool,
    pub screen_monitoring: bool,
    pub file_indexing_enabled: bool,
    pub llm_provider: String,
    pub llm_model: String,
    pub log_level: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateSettingsRequest {
    pub hotkey: Option<String>,
    pub auto_start: Option<bool>,
    pub minimize_to_tray: Option<bool>,
    pub privacy_mode: Option<bool>,
    pub clipboard_monitoring: Option<bool>,
    pub screen_monitoring: Option<bool>,
    pub file_indexing_enabled: Option<bool>,
    pub llm_provider: Option<String>,
    pub llm_model: Option<String>,
    pub log_level: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScreenCaptureRequest {
    pub region: Option<ScreenRegion>,
    pub include_cursor: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScreenRegion {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScreenCaptureResponse {
    pub success: bool,
    pub image_path: Option<String>,
    pub width: u32,
    pub height: u32,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ClipboardItem {
    pub id: String,
    pub content: String,
    pub content_type: String,
    pub timestamp: String,
    pub is_pinned: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ClipboardHistoryResponse {
    pub items: Vec<ClipboardItem>,
    pub total: usize,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileIndexRequest {
    pub folder_path: String,
    pub recursive: bool,
    pub include_patterns: Option<Vec<String>>,
    pub exclude_patterns: Option<Vec<String>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileIndexResponse {
    pub success: bool,
    pub files_indexed: usize,
    pub errors: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileSearchRequest {
    pub query: String,
    pub folder_path: Option<String>,
    pub file_types: Option<Vec<String>>,
    pub limit: Option<usize>,
    pub semantic: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileSearchResult {
    pub path: String,
    pub name: String,
    pub size: u64,
    pub modified: String,
    pub score: f32,
    pub match_type: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileSearchResponse {
    pub results: Vec<FileSearchResult>,
    pub total: usize,
    pub query_time_ms: u64,
}

#[tauri::command]
pub async fn get_app_info(state: State<'_, AppState>) -> Result<AppInfo, String> {
    let backend_connected = state.backend_client.is_connected().await;
    Ok(AppInfo {
        name: "ContextAI".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        description: "AI Desktop Intelligence & Automation Platform".to_string(),
        backend_connected,
    })
}

#[tauri::command]
pub async fn check_backend_health(state: State<'_, AppState>) -> Result<HealthResponse, String> {
    let client = &state.backend_client;
    let health = client.health_check().await.map_err(|e| e.to_string())?;
    Ok(health)
}

#[tauri::command]
pub async fn toggle_main_window(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            window.hide().map_err(|e| e.to_string())?;
        } else {
            window.show().map_err(|e| e.to_string())?;
            window.set_focus().map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn get_settings(state: State<'_, AppState>) -> Result<Settings, String> {
    let client = &state.backend_client;
    let settings = client.get_settings().await.map_err(|e| e.to_string())?;
    Ok(settings)
}

#[tauri::command]
pub async fn update_settings(
    state: State<'_, AppState>,
    request: UpdateSettingsRequest,
) -> Result<Settings, String> {
    let client = &state.backend_client;
    let settings = client.update_settings(request).await.map_err(|e| e.to_string())?;
    Ok(settings)
}

#[tauri::command]
pub async fn screen_capture(
    state: State<'_, AppState>,
    request: ScreenCaptureRequest,
) -> Result<ScreenCaptureResponse, String> {
    debug!("Screen capture requested: {:?}", request);

    let client = &state.backend_client;
    let response = client.capture_screen(request).await.map_err(|e| e.to_string())?;

    Ok(response)
}

#[tauri::command]
pub async fn clipboard_get_history(
    state: State<'_, AppState>,
    limit: Option<usize>,
    offset: Option<usize>,
) -> Result<ClipboardHistoryResponse, String> {
    let client = &state.backend_client;
    let response = client.get_clipboard_history(limit, offset).await.map_err(|e| e.to_string())?;
    Ok(response)
}

#[tauri::command]
pub async fn file_index_folder(
    state: State<'_, AppState>,
    request: FileIndexRequest,
) -> Result<FileIndexResponse, String> {
    let client = &state.backend_client;
    let response = client.index_folder(request).await.map_err(|e| e.to_string())?;
    Ok(response)
}

#[tauri::command]
pub async fn file_search(
    state: State<'_, AppState>,
    request: FileSearchRequest,
) -> Result<FileSearchResponse, String> {
    let client = &state.backend_client;
    let response = client.search_files(request).await.map_err(|e| e.to_string())?;
    Ok(response)
}
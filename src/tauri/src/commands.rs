//! Tauri Commands - Frontend accessible Rust functions

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State, Window};
use tracing::{info, debug, error, warn};
use crate::screen;
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

    let region = request.region.as_ref().map(|r| screen::CaptureRegion {
        x: r.x,
        y: r.y,
        width: r.width,
        height: r.height,
    });
    let provider = screen::default_provider();
    if !provider.is_available() {
        // Fall back to the backend-only path so the frontend still works
        // on platforms where we have no native capture (Linux dev box,
        // headless CI, etc.).
        warn!(
            "Native screen capture provider '{}' is unavailable; using backend passthrough",
            provider.name()
        );
        let client = &state.backend_client;
        return client
            .capture_screen(request)
            .await
            .map_err(|e| e.to_string());
    }

    let captured = match provider.capture(region) {
        Ok(c) => c,
        Err(e) => {
            error!("Native screen capture failed: {e}");
            return Ok(ScreenCaptureResponse {
                success: false,
                image_path: None,
                width: 0,
                height: 0,
                error: Some(e.to_string()),
            });
        }
    };

    // Save to a temp file so the backend can read it (and so the user
    // has a copy on disk after a successful capture).
    let hint = format!("{}x{}", captured.width, captured.height);
    let path = match screen::write_capture_to_temp(&captured, &hint) {
        Ok(p) => p,
        Err(e) => {
            return Ok(ScreenCaptureResponse {
                success: false,
                image_path: None,
                width: captured.width,
                height: captured.height,
                error: Some(format!("write_capture_to_temp: {e}")),
            });
        }
    };

    // Push to the backend so OCR + classification + DB write happen
    // server-side. We re-use the existing `image_path` field in the
    // backend request so we don't have to base64-encode a multi-MB
    // PNG across the wire.
    let width = captured.width;
    let height = captured.height;
    let backend_resp = state
        .backend_client
        .capture_screen_via_path(
            &path,
            width,
            height,
        )
        .await;

    // We deliberately do not propagate the backend's transient error to
    // the caller if it is just a connection failure — the local file
    // still exists, so the user (or a later retry) can use it.
    match backend_resp {
        Ok(resp) if resp.success => Ok(ScreenCaptureResponse {
            success: true,
            image_path: Some(path.to_string_lossy().to_string()),
            width: resp.width,
            height: resp.height,
            error: None,
        }),
        Ok(resp) => Ok(ScreenCaptureResponse {
            success: false,
            image_path: Some(path.to_string_lossy().to_string()),
            width: resp.width,
            height: resp.height,
            error: resp.error.or_else(|| Some("backend reported failure".to_string())),
        }),
        Err(e) => Ok(ScreenCaptureResponse {
            success: false,
            image_path: Some(path.to_string_lossy().to_string()),
            width,
            height,
            error: Some(format!("backend unreachable: {e}")),
        }),
    }
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

// ---------------------------------------------------------------------------
// Phase 2: native screen capture command (Tauri-side, no backend round-trip)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
pub struct CaptureScreenNowRequest {
    pub region: Option<ScreenRegion>,
    pub save_to_path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CaptureScreenNowResponse {
    pub success: bool,
    pub provider: String,
    pub width: u32,
    pub height: u32,
    pub image_base64: Option<String>,
    pub image_path: Option<String>,
    pub error: Option<String>,
}

/// Local-only screen capture: uses the active `ScreenCaptureProvider` to
/// grab the primary monitor (or a region) and returns the PNG bytes to
/// the caller. Does **not** contact the backend; the frontend is
/// expected to POST the bytes itself if it wants OCR/classification.
///
/// This is the command that the `Ctrl+Shift+S` hotkey and the UI
/// "Capture now" button both call.
#[tauri::command]
pub async fn capture_screen_now(
    request: CaptureScreenNowRequest,
) -> Result<CaptureScreenNowResponse, String> {
    let provider = screen::default_provider();
    if !provider.is_available() {
        return Ok(CaptureScreenNowResponse {
            success: false,
            provider: provider.name().to_string(),
            width: 0,
            height: 0,
            image_base64: None,
            image_path: None,
            error: Some("screen capture is not supported on this platform".to_string()),
        });
    }

    let region = request.region.as_ref().map(|r| screen::CaptureRegion {
        x: r.x,
        y: r.y,
        width: r.width,
        height: r.height,
    });

    let captured = match provider.capture(region) {
        Ok(c) => c,
        Err(e) => {
            error!("capture_screen_now: provider '{}' failed: {e}", provider.name());
            return Ok(CaptureScreenNowResponse {
                success: false,
                provider: provider.name().to_string(),
                width: 0,
                height: 0,
                image_base64: None,
                image_path: None,
                error: Some(e.to_string()),
            });
        }
    };

    // Optionally save to a user-supplied path. Otherwise drop to a temp
    // directory; the frontend can still hand the base64 to the backend.
    let path = if let Some(p) = request.save_to_path.as_deref() {
        let pb = std::path::PathBuf::from(p);
        if let Some(parent) = pb.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        match std::fs::write(&pb, &captured.png_bytes) {
            Ok(()) => Some(pb),
            Err(e) => {
                return Ok(CaptureScreenNowResponse {
                    success: false,
                    provider: provider.name().to_string(),
                    width: captured.width,
                    height: captured.height,
                    image_base64: None,
                    image_path: None,
                    error: Some(format!("write to {p}: {e}")),
                });
            }
        }
    } else {
        let hint = format!("{}x{}", captured.width, captured.height);
        match screen::write_capture_to_temp(&captured, &hint) {
            Ok(p) => Some(p),
            Err(e) => {
                return Ok(CaptureScreenNowResponse {
                    success: false,
                    provider: provider.name().to_string(),
                    width: captured.width,
                    height: captured.height,
                    image_base64: None,
                    image_path: None,
                    error: Some(format!("temp write: {e}")),
                });
            }
        }
    };

    let image_base64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &captured.png_bytes);

    Ok(CaptureScreenNowResponse {
        success: true,
        provider: provider.name().to_string(),
        width: captured.width,
        height: captured.height,
        image_base64: Some(image_base64),
        image_path: path.map(|p| p.to_string_lossy().to_string()),
        error: None,
    })
}
//! Backend Communication - HTTP + WebSocket Client

use std::sync::Arc;
use std::time::Duration;
use reqwest::{Client, ClientBuilder};
use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn, error};
use tokio::sync::RwLock;
use url::Url;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub timestamp: String,
    pub services: ServiceStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceStatus {
    pub database: bool,
    pub vector_store: bool,
    pub ml_models: bool,
    pub ocr: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
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

#[derive(Debug, Clone, Serialize, Deserialize)]
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenCaptureRequest {
    pub region: Option<ScreenRegion>,
    pub include_cursor: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenRegion {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenCaptureResponse {
    pub success: bool,
    pub image_path: Option<String>,
    pub width: u32,
    pub height: u32,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardItem {
    pub id: String,
    /// Raw content. Always empty for sensitive items — use
    /// ``redacted_content`` and ``preview`` for display.
    pub content: String,
    pub redacted_content: String,
    pub content_type: String,
    pub classification: Option<String>,
    pub classification_confidence: Option<f32>,
    pub classifier_version: Option<String>,
    pub is_sensitive: bool,
    pub sensitive_reasons: Vec<String>,
    pub source_app: Option<String>,
    pub metadata: serde_json::Value,
    pub timestamp: Option<String>,
    pub expires_at: Option<String>,
    pub is_pinned: bool,
    pub is_encrypted: bool,
    pub char_count: u32,
    pub word_count: u32,
    pub preview: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardHistoryResponse {
    pub items: Vec<ClipboardItem>,
    pub total: usize,
    pub limit: u32,
    pub offset: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardCaptureRequest {
    pub content: String,
    pub source_app: Option<String>,
    pub content_type: Option<String>,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardCaptureResponse {
    pub success: bool,
    pub stored: bool,
    pub reason: String,
    pub is_sensitive: bool,
    pub redacted_content: String,
    pub item: Option<ClipboardItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileIndexRequest {
    pub folder_path: String,
    pub recursive: bool,
    pub include_patterns: Option<Vec<String>>,
    pub exclude_patterns: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileIndexResponse {
    pub success: bool,
    pub files_indexed: usize,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSelectResponse {
    pub success: bool,
    pub stored: bool,
    pub reason: String,
    pub changed: bool,
    pub reused: bool,
    pub raw_path: String,
    pub file: Option<FileRowSummary>,
    pub files_indexed: usize,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileRowSummary {
    pub id: u32,
    pub path: String,
    pub name: String,
    pub file_type: String,
    pub extension: Option<String>,
    pub size_bytes: u64,
    pub modified_at: Option<String>,
    pub classification: Option<String>,
    pub classification_confidence: Option<f32>,
    pub extraction_status: String,
    pub is_indexed: bool,
    pub indexed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSearchRequest {
    pub query: String,
    pub folder_path: Option<String>,
    pub file_types: Option<Vec<String>>,
    pub limit: Option<usize>,
    pub semantic: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSearchResult {
    pub path: String,
    pub name: String,
    pub size: u64,
    pub modified: String,
    pub score: f32,
    pub match_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSearchResponse {
    pub results: Vec<FileSearchResult>,
    pub total: usize,
    pub query_time_ms: u64,
}

pub struct BackendClient {
    http_client: Client,
    base_url: String,
    ws_url: String,
    connected: Arc<RwLock<bool>>,
}

impl BackendClient {
    pub fn new() -> Self {
        let http_client = ClientBuilder::new()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            http_client,
            base_url: "http://127.0.0.1:8000".to_string(),
            ws_url: "ws://127.0.0.1:8000".to_string(),
            connected: Arc::new(RwLock::new(false)),
        }
    }

    pub async fn connect(&self) -> anyhow::Result<()> {
        match self.health_check().await {
            Ok(_) => {
                *self.connected.write().await = true;
                info!("Backend connection established");
                Ok(())
            }
            Err(e) => {
                *self.connected.write().await = false;
                Err(e)
            }
        }
    }

    pub async fn is_connected(&self) -> bool {
        *self.connected.read().await
    }

    pub async fn health_check(&self) -> anyhow::Result<HealthResponse> {
        let url = format!("{}/api/v1/health", self.base_url);
        debug!("Health check: {}", url);

        let response = self.http_client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Health check failed: {}", response.status()));
        }

        let health: HealthResponse = response.json().await?;
        *self.connected.write().await = true;
        Ok(health)
    }

    pub async fn get_settings(&self) -> anyhow::Result<Settings> {
        let url = format!("{}/api/v1/settings", self.base_url);
        debug!("Get settings: {}", url);

        let response = self.http_client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Get settings failed: {}", response.status()));
        }

        let settings: Settings = response.json().await?;
        Ok(settings)
    }

    pub async fn update_settings(&self, request: UpdateSettingsRequest) -> anyhow::Result<Settings> {
        let url = format!("{}/api/v1/settings", self.base_url);
        debug!("Update settings: {:?}", request);

        let response = self.http_client
            .patch(&url)
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Update settings failed: {}", response.status()));
        }

        let settings: Settings = response.json().await?;
        Ok(settings)
    }

    pub async fn capture_screen(&self, request: ScreenCaptureRequest) -> anyhow::Result<ScreenCaptureResponse> {
        let url = format!("{}/api/v1/screen/capture", self.base_url);
        debug!("Screen capture request: {:?}", request);

        let response = self.http_client
            .post(&url)
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Ok(ScreenCaptureResponse {
                success: false,
                image_path: None,
                width: 0,
                height: 0,
                error: Some(error),
            });
        }

        let result: ScreenCaptureResponse = response.json().await?;
        Ok(result)
    }

    /// Push a locally-captured PNG (already on disk) to the backend so
    /// OCR / classification can run. The backend reads the file from
    /// `image_path` so we don't have to base64 a multi-MB image across
    /// the wire.
    pub async fn capture_screen_via_path(
        &self,
        path: &std::path::Path,
        width: u32,
        height: u32,
    ) -> anyhow::Result<ScreenCaptureResponse> {
        use serde_json::json;
        let url = format!("{}/api/v1/screen/capture", self.base_url);
        debug!("Screen capture (path) -> backend: {}", path.display());

        let body = json!({
            "image_path": path.to_string_lossy(),
            "width": width,
            "height": height,
            "save_to_disk": false,
            "run_ocr": true,
        });
        let response = self.http_client.post(&url).json(&body).send().await?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Ok(ScreenCaptureResponse {
                success: false,
                image_path: Some(path.to_string_lossy().to_string()),
                width,
                height,
                error: Some(error),
            });
        }

        let result: ScreenCaptureResponse = response.json().await?;
        Ok(result)
    }

    pub async fn get_clipboard_history(
        &self,
        limit: Option<usize>,
        offset: Option<usize>,
    ) -> anyhow::Result<ClipboardHistoryResponse> {
        let mut url = format!("{}/api/v1/clipboard", self.base_url);
        let mut params = Vec::new();

        if let Some(limit) = limit {
            params.push(format!("limit={}", limit));
        }
        if let Some(offset) = offset {
            params.push(format!("offset={}", offset));
        }

        if !params.is_empty() {
            url.push('?');
            url.push_str(&params.join("&"));
        }

        debug!("Clipboard history request: {}", url);

        let response = self.http_client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Clipboard history request failed: {}", response.status()));
        }

        let result: ClipboardHistoryResponse = response.json().await?;
        Ok(result)
    }

    /// POST /api/v1/clipboard/capture — submit a new clipboard change.
    pub async fn capture_clipboard(
        &self,
        request: &ClipboardCaptureRequest,
    ) -> anyhow::Result<ClipboardCaptureResponse> {
        let url = format!("{}/api/v1/clipboard/capture", self.base_url);
        debug!("Clipboard capture request: {} bytes", request.content.len());
        let response = self.http_client.post(&url).json(request).send().await?;
        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("capture failed: {} {}", status, body));
        }
        let result: ClipboardCaptureResponse = response.json().await?;
        Ok(result)
    }

    /// PATCH /api/v1/clipboard/{id}/pin
    pub async fn pin_clipboard_item(
        &self,
        item_id: &str,
        pinned: bool,
    ) -> anyhow::Result<ClipboardItem> {
        let url = format!("{}/api/v1/clipboard/{}/pin", self.base_url, item_id);
        let body = serde_json::json!({ "pinned": pinned });
        let response = self
            .http_client
            .patch(&url)
            .json(&body)
            .send()
            .await?;
        if !response.status().is_success() {
            return Err(anyhow::anyhow!(
                "pin failed: {}",
                response.status()
            ));
        }
        let result: ClipboardItem = response.json().await?;
        Ok(result)
    }

    /// DELETE /api/v1/clipboard/{id}
    pub async fn delete_clipboard_item(&self, item_id: &str) -> anyhow::Result<()> {
        let url = format!("{}/api/v1/clipboard/{}", self.base_url, item_id);
        let response = self.http_client.delete(&url).send().await?;
        if !response.status().is_success() {
            return Err(anyhow::anyhow!(
                "delete failed: {}",
                response.status()
            ));
        }
        Ok(())
    }

    /// DELETE /api/v1/clipboard — clear history.
    pub async fn clear_clipboard_history(
        &self,
        keep_pinned: bool,
    ) -> anyhow::Result<usize> {
        let url = format!(
            "{}/api/v1/clipboard?keep_pinned={}",
            self.base_url, keep_pinned
        );
        let response = self.http_client.delete(&url).send().await?;
        if !response.status().is_success() {
            return Err(anyhow::anyhow!(
                "clear failed: {}",
                response.status()
            ));
        }
        let v: serde_json::Value = response.json().await?;
        Ok(v.get("affected").and_then(|x| x.as_u64()).unwrap_or(0) as usize)
    }

    pub async fn index_folder(&self, request: FileIndexRequest) -> anyhow::Result<FileIndexResponse> {
        let url = format!("{}/api/v1/files/index", self.base_url);
        debug!("File index request: {:?}", request);

        let response = self.http_client
            .post(&url)
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Ok(FileIndexResponse {
                success: false,
                files_indexed: 0,
                errors: vec![error],
            });
        }

        let result: FileIndexResponse = response.json().await?;
        Ok(result)
    }

    pub async fn search_files(&self, request: FileSearchRequest) -> anyhow::Result<FileSearchResponse> {
        let url = format!("{}/api/v1/files/search", self.base_url);
        debug!("File search request: {:?}", request);

        let response = self.http_client
            .post(&url)
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("File search failed: {}", response.status()));
        }

        let result: FileSearchResponse = response.json().await?;
        Ok(result)
    }

    /// POST /api/v1/files/select — index a single user-selected file.
    pub async fn select_file(&self, path: &str) -> anyhow::Result<FileSelectResponse> {
        use serde_json::json;
        let url = format!("{}/api/v1/files/select", self.base_url);
        debug!("File select request: path={}", path);

        let body = json!({ "path": path });
        let response = self.http_client.post(&url).json(&body).send().await?;

        if !response.status().is_success() {
            let error = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("File select failed: {}", error));
        }

        let result: FileSelectResponse = response.json().await?;
        Ok(result)
    }

    pub fn set_base_url(&mut self, url: String) {
        self.base_url = url.trim_end_matches('/').to_string();
    }

    pub fn set_ws_url(&mut self, url: String) {
        self.ws_url = url;
    }
}

impl Default for BackendClient {
    fn default() -> Self {
        Self::new()
    }
}
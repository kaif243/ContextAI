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
    pub content: String,
    pub content_type: String,
    pub timestamp: String,
    pub is_pinned: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardHistoryResponse {
    pub items: Vec<ClipboardItem>,
    pub total: usize,
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
        let mut url = format!("{}/api/v1/clipboard/history", self.base_url);
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
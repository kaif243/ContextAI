//! Application state shared across Tauri

use std::sync::Arc;

use crate::ipc::BackendClient;
use crate::hotkey::GlobalHotkeyManager;

/// Application state managed by Tauri
#[derive(Clone)]
pub struct AppState {
    pub backend_client: Arc<BackendClient>,
    pub hotkey_manager: Arc<GlobalHotkeyManager>,
}

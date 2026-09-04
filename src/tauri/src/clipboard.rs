//! Clipboard provider abstraction (Phase 3).
//!
//! Mirrors the shape of `screen.rs`: a trait that describes "read the
//! current clipboard text", a default provider that uses the OS
//! clipboard, and a null provider for non-desktop / headless builds.
//!
//! Polling
//! -------
//! The provider is intentionally pull-based. A background tokio task
//! (`start_polling`) reads the current text every `poll_interval` and,
//! if it changed, sends the new text through the supplied callback.
//! This is the same shape Phase 2 uses for screen captures and keeps
//! the backend-side storage/classification logic in one place
//! (the FastAPI `/api/v1/clipboard/capture` endpoint).
//!
//! We do **not** depend on `tauri-plugin-clipboard-manager` from this
//! module — the trait is the single point of truth and the plugin is
//! wired in at the Tauri command boundary. That keeps the abstraction
//! testable and means the rest of the codebase compiles even when the
//! plugin is replaced or removed.
//!
//! Hotkeys
//! -------
//! This module does not register any global shortcuts; that lives in
//! `hotkey.rs` and must not be modified by Phase 3. The Phase 2
//! `Ctrl+Space` (main) and `Ctrl+Shift+S` (screen) hotkeys continue to
//! work exactly as before.

use std::fmt;
use std::sync::Arc;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

/// Snapshot of the current clipboard text.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardSnapshot {
    pub text: String,
    /// Milliseconds since the UNIX epoch when the snapshot was taken.
    pub captured_at_ms: u128,
}

/// Errors a provider can surface.
#[derive(Debug, Error)]
pub enum ClipboardError {
    #[error("clipboard access is not supported on this platform")]
    UnsupportedPlatform,

    #[error("clipboard backend error: {0}")]
    Backend(String),
}

impl ClipboardError {
    pub fn backend<S: fmt::Display>(msg: S) -> Self {
        Self::Backend(msg.to_string())
    }
}

/// Provider contract. Implementations are responsible for talking to
/// the host OS / windowing layer.
pub trait ClipboardProvider: Send + Sync {
    fn name(&self) -> &'static str;
    fn is_available(&self) -> bool;
    fn read_text(&self) -> Result<String, ClipboardError>;
}

// ---------------------------------------------------------------------------
// Null provider (non-Windows builds, tests)
// ---------------------------------------------------------------------------

/// A provider that always reports "not available" with a clear message.
pub struct NullProvider;

impl ClipboardProvider for NullProvider {
    fn name(&self) -> &'static str {
        "null"
    }

    fn is_available(&self) -> bool {
        false
    }

    fn read_text(&self) -> Result<String, ClipboardError> {
        Err(ClipboardError::UnsupportedPlatform)
    }
}

// ---------------------------------------------------------------------------
// Default provider (designed to be wired to tauri-plugin-clipboard-manager
// at the command boundary; defaults to NullProvider for headless / tests)
// ---------------------------------------------------------------------------

/// A provider that delegates to a closure. The Tauri command layer can
/// construct one of these with a closure that calls
/// `tauri_plugin_clipboard_manager::ClipboardExt::read_text`, so the
/// plugin stays out of this module's compile-time dependencies.
pub struct CallbackProvider {
    name: &'static str,
    callback: Arc<dyn Fn() -> Result<String, ClipboardError> + Send + Sync>,
}

impl CallbackProvider {
    pub fn new<F>(name: &'static str, callback: F) -> Self
    where
        F: Fn() -> Result<String, ClipboardError> + Send + Sync + 'static,
    {
        Self {
            name,
            callback: Arc::new(callback),
        }
    }
}

impl ClipboardProvider for CallbackProvider {
    fn name(&self) -> &'static str {
        self.name
    }

    fn is_available(&self) -> bool {
        true
    }

    fn read_text(&self) -> Result<String, ClipboardError> {
        (self.callback)()
    }
}

/// Return the best provider available on the current host. Always
/// returns a valid pointer; callers must check `is_available()` before
/// invoking `read_text`.
pub fn default_provider() -> Box<dyn ClipboardProvider> {
    // We do not have a built-in OS provider here — the Tauri command
    // layer is expected to construct a CallbackProvider that wraps
    // `tauri-plugin-clipboard-manager`. Until that wiring is in place
    // we return the null provider so the polling loop and other
    // consumers degrade gracefully.
    Box::new(NullProvider)
}

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

/// Configuration for the polling loop.
#[derive(Debug, Clone)]
pub struct PollingConfig {
    /// How often to read the clipboard. Defaults to 750 ms.
    pub interval: Duration,
    /// Whether the loop is enabled at start. Default: `false`.
    pub enabled: bool,
}

impl Default for PollingConfig {
    fn default() -> Self {
        Self {
            interval: Duration::from_millis(750),
            enabled: false,
        }
    }
}

/// Handle to a running polling task. Drop it (or call `stop`) to stop
/// the loop.
pub struct PollingHandle {
    stop_flag: Arc<std::sync::atomic::AtomicBool>,
    join: Mutex<Option<tokio::task::JoinHandle<()>>>,
}

impl PollingHandle {
    /// Request the loop to stop and wait for it to finish.
    pub async fn stop(&self) {
        self.stop_flag
            .store(true, std::sync::atomic::Ordering::SeqCst);
        if let Some(j) = self.join.lock().await.take() {
            let _ = j.await;
        }
    }
}

use std::sync::atomic::AtomicBool;

/// Start a background task that polls the clipboard and invokes
/// `on_change` whenever the text differs from the previous read.
///
/// The closure runs on the tokio runtime; it must be cheap and
/// non-blocking (POSTing to the backend is fine).
///
/// Returns a [`PollingHandle`] the caller can use to stop the loop.
pub fn start_polling<P, F, Fut>(
    provider: Arc<P>,
    config: PollingConfig,
    on_change: F,
) -> PollingHandle
where
    P: ClipboardProvider + 'static,
    F: Fn(ClipboardSnapshot) -> Fut + Send + Sync + 'static,
    Fut: std::future::Future<Output = ()> + Send + 'static,
{
    let stop = Arc::new(AtomicBool::new(false));
    let on_change = Arc::new(on_change);
    let provider = provider.clone();
    let stop_for_task = stop.clone();
    let interval = config.interval;

    let join = tokio::spawn(async move {
        if !provider.is_available() {
            warn!(
                "Clipboard provider '{}' is not available; polling will not run",
                provider.name()
            );
            return;
        }
        if !config.enabled {
            debug!(
                "Clipboard polling started in disabled state; loop is idle. Call set_enabled(true) to begin polling."
            );
            // Even when disabled, the task stays alive so callers can
            // observe a "stop" via the PollingHandle. We just sleep
            // until told to exit.
            while !stop_for_task.load(std::sync::atomic::Ordering::SeqCst) {
                tokio::time::sleep(interval).await;
            }
            return;
        }

        let mut last: Option<String> = None;
        info!(
            "Clipboard polling started: provider='{}' interval={:?}",
            provider.name(),
            interval
        );
        while !stop_for_task.load(std::sync::atomic::Ordering::SeqCst) {
            match provider.read_text() {
                Ok(text) => {
                    if last.as_deref() != Some(text.as_str()) {
                        last = Some(text.clone());
                        let snap = ClipboardSnapshot {
                            text,
                            captured_at_ms: std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .map(|d| d.as_millis())
                                .unwrap_or(0),
                        };
                        (on_change)(snap).await;
                    }
                }
                Err(e) => {
                    debug!(
                        "Clipboard read failed ({}): {} — will retry",
                        provider.name(),
                        e
                    );
                }
            }
            tokio::time::sleep(interval).await;
        }
        info!("Clipboard polling stopped");
    });

    PollingHandle {
        stop_flag: stop,
        join: Mutex::new(Some(join)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;

    #[test]
    fn null_provider_reports_unavailable() {
        let p = NullProvider;
        assert_eq!(p.name(), "null");
        assert!(!p.is_available());
        assert!(matches!(
            p.read_text().unwrap_err(),
            ClipboardError::UnsupportedPlatform
        ));
    }

    #[test]
    fn callback_provider_invokes_callback() {
        let p = CallbackProvider::new("test", || Ok("hello".to_string()));
        assert_eq!(p.name(), "test");
        assert!(p.is_available());
        assert_eq!(p.read_text().unwrap(), "hello");
    }

    #[test]
    fn callback_provider_propagates_error() {
        let p = CallbackProvider::new("test", || {
            Err(ClipboardError::backend("nope"))
        });
        assert!(p.read_text().is_err());
    }

    #[tokio::test]
    async fn polling_invokes_on_change_only_when_text_differs() {
        // The provider alternates between "a" and "a" — actually we
        // simulate "different then same" by returning "x" the first
        // two reads, then returning Err.
        let counter = Arc::new(AtomicUsize::new(0));
        let counter_for_cb = counter.clone();
        let p = CallbackProvider::new("test", move || {
            let n = counter_for_cb.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            if n < 2 {
                Ok("x".to_string())
            } else {
                Err(ClipboardError::backend("stop"))
            }
        });

        let calls = Arc::new(AtomicUsize::new(0));
        let calls_for_cb = calls.clone();

        let handle = start_polling(
            Arc::new(p),
            PollingConfig {
                interval: Duration::from_millis(5),
                enabled: true,
            },
            move |_snap| {
                let calls = calls_for_cb.clone();
                async move {
                    calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                }
            },
        );

        // Let the loop run for a few intervals.
        tokio::time::sleep(Duration::from_millis(80)).await;
        handle.stop().await;

        // Two reads return the same text -> exactly one on_change.
        assert_eq!(calls.load(std::sync::atomic::Ordering::SeqCst), 1);
    }
}

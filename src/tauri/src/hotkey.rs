//! Global Hotkey Management

use std::sync::Arc;
use tauri::{AppHandle, Manager};
use tracing::{info, debug, error, warn};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

pub struct GlobalHotkeyManager {
    registered_shortcuts: Arc<tokio::sync::RwLock<Vec<String>>>,
}

impl GlobalHotkeyManager {
    pub fn new() -> Self {
        Self {
            registered_shortcuts: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        }
    }

    pub async fn register_hotkeys(&self, app: AppHandle) -> anyhow::Result<()> {
        // Ctrl+Space  -> toggle the main window (Phase 1, do not change).
        // Ctrl+Shift+S -> trigger a screen capture (Phase 2).
        let shortcuts = vec!["Ctrl+Space", "Ctrl+Shift+S"];

        for shortcut_str in shortcuts {
            match self.register_shortcut(&app, shortcut_str).await {
                Ok(_) => {
                    info!("Registered global hotkey: {}", shortcut_str);
                    self.registered_shortcuts.write().await.push(shortcut_str.to_string());
                }
                Err(e) => {
                    warn!("Failed to register hotkey {}: {}", shortcut_str, e);
                }
            }
        }

        Ok(())
    }

    /// Emit a `screen-capture-requested` event to every webview. The
    /// frontend listens for this and calls `capture_screen_now` to do
    /// the actual grab. We emit rather than call directly so the
    /// frontend can show a "Capturing..." indicator and route the
    /// resulting image into the right panel.
    pub async fn trigger_screen_capture(&self, app: &AppHandle) -> anyhow::Result<()> {
        if let Some(window) = app.get_webview_window("main") {
            window.emit("screen-capture-requested", ())?;
        }
        Ok(())
    }

    async fn register_shortcut(&self, app: &AppHandle, shortcut_str: &str) -> anyhow::Result<()> {
        let shortcut = Shortcut::from_str(shortcut_str)?;
        app.global_shortcut().register(shortcut)?;
        Ok(())
    }

    pub async fn unregister_all(&self, app: &AppHandle) -> anyhow::Result<()> {
        let shortcuts = self.registered_shortcuts.read().await.clone();
        for shortcut_str in shortcuts {
            if let Ok(shortcut) = Shortcut::from_str(&shortcut_str) {
                let _ = app.global_shortcut().unregister(shortcut);
            }
        }
        self.registered_shortcuts.write().await.clear();
        Ok(())
    }

    pub async fn update_hotkey(&self, app: &AppHandle, old: &str, new: &str) -> anyhow::Result<()> {
        // Unregister old
        if let Ok(shortcut) = Shortcut::from_str(old) {
            let _ = app.global_shortcut().unregister(shortcut);
        }

        // Register new
        let shortcut = Shortcut::from_str(new)?;
        app.global_shortcut().register(shortcut)?;

        // Update tracked list
        let mut shortcuts = self.registered_shortcuts.write().await;
        if let Some(pos) = shortcuts.iter().position(|s| s == old) {
            shortcuts[pos] = new.to_string();
        }

        Ok(())
    }
}

// Extension trait for parsing shortcut strings
impl Shortcut {
    fn from_str(s: &str) -> anyhow::Result<Self> {
        let parts: Vec<&str> = s.split('+').collect();
        let mut modifiers = tauri_plugin_global_shortcut::Modifiers::empty();
        let mut key = None;

        for part in parts {
            match part.trim().to_lowercase().as_str() {
                "ctrl" | "control" => modifiers |= tauri_plugin_global_shortcut::Modifiers::CONTROL,
                "alt" => modifiers |= tauri_plugin_global_shortcut::Modifiers::ALT,
                "shift" => modifiers |= tauri_plugin_global_shortcut::Modifiers::SHIFT,
                "super" | "meta" | "cmd" | "command" => modifiers |= tauri_plugin_global_shortcut::Modifiers::SUPER,
                k => {
                    key = Some(Self::parse_key(k)?);
                }
            }
        }

        let key = key.ok_or_else(|| anyhow::anyhow!("No key specified in shortcut"))?;
        Ok(Shortcut::new(Some(modifiers), key))
    }

    fn parse_key(s: &str) -> anyhow::Result<tauri_plugin_global_shortcut::Key> {
        use tauri_plugin_global_shortcut::Key;

        match s {
            "space" => Ok(Key::Space),
            "enter" => Ok(Key::Enter),
            "escape" | "esc" => Ok(Key::Escape),
            "tab" => Ok(Key::Tab),
            "backspace" => Ok(Key::Backspace),
            "delete" => Ok(Key::Delete),
            "home" => Ok(Key::Home),
            "end" => Ok(Key::End),
            "pageup" => Ok(Key::PageUp),
            "pagedown" => Ok(Key::PageDown),
            "up" => Ok(Key::ArrowUp),
            "down" => Ok(Key::ArrowDown),
            "left" => Ok(Key::ArrowLeft),
            "right" => Ok(Key::ArrowRight),
            "f1" => Ok(Key::F1),
            "f2" => Ok(Key::F2),
            "f3" => Ok(Key::F3),
            "f4" => Ok(Key::F4),
            "f5" => Ok(Key::F5),
            "f6" => Ok(Key::F6),
            "f7" => Ok(Key::F7),
            "f8" => Ok(Key::F8),
            "f9" => Ok(Key::F9),
            "f10" => Ok(Key::F10),
            "f11" => Ok(Key::F11),
            "f12" => Ok(Key::F12),
            "0" => Ok(Key::Key0),
            "1" => Ok(Key::Key1),
            "2" => Ok(Key::Key2),
            "3" => Ok(Key::Key3),
            "4" => Ok(Key::Key4),
            "5" => Ok(Key::Key5),
            "6" => Ok(Key::Key6),
            "7" => Ok(Key::Key7),
            "8" => Ok(Key::Key8),
            "9" => Ok(Key::Key9),
            "a" => Ok(Key::A),
            "b" => Ok(Key::B),
            "c" => Ok(Key::C),
            "d" => Ok(Key::D),
            "e" => Ok(Key::E),
            "f" => Ok(Key::F),
            "g" => Ok(Key::G),
            "h" => Ok(Key::H),
            "i" => Ok(Key::I),
            "j" => Ok(Key::J),
            "k" => Ok(Key::K),
            "l" => Ok(Key::L),
            "m" => Ok(Key::M),
            "n" => Ok(Key::N),
            "o" => Ok(Key::O),
            "p" => Ok(Key::P),
            "q" => Ok(Key::Q),
            "r" => Ok(Key::R),
            "s" => Ok(Key::S),
            "t" => Ok(Key::T),
            "u" => Ok(Key::U),
            "v" => Ok(Key::V),
            "w" => Ok(Key::W),
            "x" => Ok(Key::X),
            "y" => Ok(Key::Y),
            "z" => Ok(Key::Z),
            _ => Err(anyhow::anyhow!("Unknown key: {}", s)),
        }
    }
}

impl Default for GlobalHotkeyManager {
    fn default() -> Self {
        Self::new()
    }
}
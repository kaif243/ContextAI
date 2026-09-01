//! ContextAI - AI Desktop Intelligence & Automation Platform
//! Tauri 2.x + Rust Backend

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod hotkey;
mod ipc;
mod state;
mod tray;

use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, Runtime, WindowEvent,
};
use tracing::{info, error, warn};
use tracing_subscriber::{EnvFilter, fmt, layer::SubscriberExt, util::SubscriberInitExt};

use commands::{
    get_app_info, check_backend_health, toggle_main_window,
    get_settings, update_settings,
    screen_capture, clipboard_get_history,
    file_index_folder, file_search,
};
use hotkey::GlobalHotkeyManager;
use ipc::BackendClient;
use state::AppState;

fn setup_logging() -> anyhow::Result<()> {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,tauri=warn,wgpu=warn"));

    tracing_subscriber::registry()
        .with(env_filter)
        .with(fmt::layer().json().with_target(true))
        .init();

    Ok(())
}

fn create_tray_menu<R: Runtime>(app: &tauri::AppHandle<R>) -> anyhow::Result<Menu<R>> {
    let show_item = MenuItem::with_id(app, "show", "Show ContextAI", true, None::<&str>)?;
    let hide_item = MenuItem::with_id(app, "hide", "Hide Window", true, None::<&str>)?;
    let separator = MenuItem::with_id(app, "sep1", "", true, None::<&str>)?;
    let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let separator2 = MenuItem::with_id(app, "sep2", "", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit ContextAI", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[
        &show_item, &hide_item, &separator,
        &settings_item, &separator2, &quit_item,
    ])?;

    Ok(menu)
}

fn handle_tray_event(app: &tauri::AppHandle, event: tauri::tray::TrayIconEvent) {
    match event {
        tauri::tray::TrayIconEvent::Click { button, .. } => {
            if button == tauri::tray::MouseButton::Left {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        }
        _ => {}
    }
}

fn handle_menu_event(app: &tauri::AppHandle, event: tauri::menu::MenuEvent) {
    match event.id().as_ref() {
        "show" => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        "hide" => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }
        }
        "settings" => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
                let _ = window.emit("navigate", "/settings");
            }
        }
        "quit" => {
            app.exit(0);
        }
        _ => {}
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    setup_logging().expect("Failed to initialize logging");
    info!("Starting ContextAI v{}", env!("CARGO_PKG_VERSION"));

    let backend_client = Arc::new(BackendClient::new());
    let hotkey_manager = Arc::new(GlobalHotkeyManager::new());

    let app_state = AppState {
        backend_client: backend_client.clone(),
        hotkey_manager: hotkey_manager.clone(),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |app, shortcut, event| {
                if shortcut == "ctrl+space" && event.state == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                    let _ = toggle_main_window(app.clone());
                }
            })
            .build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_os_info::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_app_info,
            check_backend_health,
            toggle_main_window,
            get_settings,
            update_settings,
            screen_capture,
            clipboard_get_history,
            file_index_folder,
            file_search,
        ])
        .setup(move |app| {
            // Initialize global hotkey
            let hotkey_manager = hotkey_manager.clone();
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = hotkey_manager.register_hotkeys(app_handle).await {
                    error!("Failed to register global hotkeys: {}", e);
                }
            });

            // Create system tray
            let tray_menu = create_tray_menu(app.handle())?;
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&tray_menu)
                .on_tray_icon_event(handle_tray_event)
                .on_menu_event(handle_menu_event)
                .tooltip("ContextAI - AI Desktop Intelligence")
                .build(app)?;

            // Connect to backend
            let backend_client = backend_client.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = backend_client.connect().await {
                    warn!("Backend not available at startup: {}", e);
                } else {
                    info!("Connected to backend successfully");
                }
            });

            // Show main window on startup
            if let Some(window) = app.get_webview_window("main") {
                window.show()?;
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            match event {
                WindowEvent::CloseRequested { api, .. } => {
                    // Hide instead of close
                    window.hide().unwrap();
                    api.prevent_close();
                }
                WindowEvent::Focused(focused) => {
                    if !focused {
                        // Optionally auto-hide on focus loss
                    }
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("Error while running Tauri application");
}

fn main() {
    run();
}
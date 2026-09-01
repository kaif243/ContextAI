//! System Tray Management

use tauri::{AppHandle, Manager, Runtime};
use tauri::menu::{Menu, MenuItem};
use tracing::{info, debug};

pub fn create_tray_menu<R: Runtime>(app: &AppHandle<R>) -> anyhow::Result<Menu<R>> {
    let show_item = MenuItem::with_id(app, "show", "Show ContextAI", true, None::<&str>)?;
    let hide_item = MenuItem::with_id(app, "hide", "Hide Window", true, None::<&str>)?;
    let separator = MenuItem::with_id(app, "sep1", "", true, None::<&str>)?;
    let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let separator2 = MenuItem::with_id(app, "sep2", "", true, None::<&str>)?;
    let about_item = MenuItem::with_id(app, "about", "About ContextAI", true, None::<&str>)?;
    let separator3 = MenuItem::with_id(app, "sep3", "", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit ContextAI", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[
        &show_item, &hide_item, &separator,
        &settings_item, &separator2, &about_item, &separator3, &quit_item,
    ])?;

    Ok(menu)
}

pub fn handle_tray_event<R: Runtime>(app: &AppHandle<R>, event: tauri::tray::TrayIconEvent) {
    match event {
        tauri::tray::TrayIconEvent::Click { button, .. } => {
            if button == tauri::tray::MouseButton::Left {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        }
        tauri::tray::TrayIconEvent::DoubleClick { .. } => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        _ => {}
    }
}

pub fn handle_menu_event<R: Runtime>(app: &AppHandle<R>, event: tauri::menu::MenuEvent) {
    match event.id().as_ref() {
        "show" => {
            debug!("Tray menu: Show");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        "hide" => {
            debug!("Tray menu: Hide");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }
        }
        "settings" => {
            debug!("Tray menu: Settings");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
                let _ = window.emit("navigate", "/settings");
            }
        }
        "about" => {
            debug!("Tray menu: About");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
                let _ = window.emit("navigate", "/about");
            }
        }
        "quit" => {
            debug!("Tray menu: Quit");
            app.exit(0);
        }
        _ => {}
    }
}

pub fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> anyhow::Result<tauri::tray::TrayIcon<R>> {
    let tray_menu = create_tray_menu(app)?;
    let tray = tauri::tray::TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&tray_menu)
        .on_tray_icon_event(handle_tray_event)
        .on_menu_event(handle_menu_event)
        .tooltip("ContextAI - AI Desktop Intelligence")
        .build(app)?;

    info!("System tray initialized");
    Ok(tray)
}
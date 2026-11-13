mod sidecar;
mod mini_window;

use sidecar::{CoreInfo, Sidecar};
use std::sync::Arc;
use std::time::Duration;
use tauri::{Manager, RunEvent, State};

/// Imports pesados (voz, UIA) levam alguns segundos na primeira abertura.
const CORE_START_TIMEOUT: Duration = Duration::from_secs(60);

/// Porta e token do nucleo. Espera o sidecar anunciar.
#[tauri::command]
async fn core_info(sidecar: State<'_, Arc<Sidecar>>) -> Result<CoreInfo, String> {
    let sidecar = Arc::clone(sidecar.inner());
    tauri::async_runtime::spawn_blocking(move || sidecar.info(CORE_START_TIMEOUT))
        .await
        .map_err(|e| e.to_string())?
}

/// Encerra e sobe o nucleo de novo (botao "Reiniciar nucleo" e queda do sidecar).
#[tauri::command]
async fn restart_core(sidecar: State<'_, Arc<Sidecar>>) -> Result<(), String> {
    let sidecar = Arc::clone(sidecar.inner());
    tauri::async_runtime::spawn_blocking(move || sidecar.restart())
        .await
        .map_err(|e| e.to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        // Instancia unica: abrir de novo so traz a janela principal para frente.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.unminimize();
                let _ = main.show();
                let _ = main.set_focus();
            }
        }))
        .setup(|app| {
            let sidecar = Arc::new(Sidecar::new());
            if let Err(err) = sidecar.start() {
                eprintln!("[core] {err}");
            }
            app.manage(sidecar);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_info,
            restart_core,
            mini_window::enter_mini,
            mini_window::set_mini_busy,
            mini_window::restore_main,
            mini_window::close_mini,
            mini_window::quick_entry
        ])
        .build(tauri::generate_context!())
        .expect("falha ao montar a casca Tauri");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            handle.state::<Arc<Sidecar>>().stop();
        }
    });
}

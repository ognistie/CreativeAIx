//! Janela completa <-> mini chat (o mesmo comportamento de app/desktop/window_mode.py).
//!
//! Regras que protegem a execucao: durante a tarefa nada aqui ativa janela. O mini chat aparece sem foco
//! (SW_SHOWNOACTIVATE + WS_EX_NOACTIVATE) e sem receber cliques; a principal minimiza com
//! SW_SHOWMINNOACTIVE, que nao muda a janela em primeiro plano. Parar e pelo atalho global (Ctrl+Alt+X).

use tauri::{AppHandle, Manager, PhysicalPosition, WebviewWindow};

const MARGIN: f64 = 16.0;

fn window(app: &AppHandle, label: &str) -> Result<WebviewWindow, String> {
    app.get_webview_window(label)
        .ok_or_else(|| format!("janela {label} ausente"))
}

/// Canto inferior direito da area de trabalho (sem a barra de tarefas) do monitor da janela principal.
fn place_mini(app: &AppHandle, mini: &WebviewWindow) -> Result<(), String> {
    let main = window(app, "main")?;
    let monitor = main
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| mini.primary_monitor().ok().flatten())
        .ok_or("nenhum monitor")?;
    let area = monitor.work_area();
    let margin = (MARGIN * monitor.scale_factor()).round() as i32;
    let size = mini.outer_size().map_err(|e| e.to_string())?;
    let x = area.position.x + area.size.width as i32 - size.width as i32 - margin;
    let y = area.position.y + area.size.height as i32 - size.height as i32 - margin;
    mini.set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())
}

/// Mini chat no canto; a principal minimiza sem ativar nada. `busy`: tarefa rodando (sem foco, sem cliques).
#[tauri::command]
pub fn enter_mini(app: AppHandle, busy: bool) -> Result<(), String> {
    let mini = window(&app, "mini")?;
    let main = window(&app, "main")?;
    place_mini(&app, &mini)?;
    platform::set_no_activate(&mini, busy);
    platform::show_no_activate(&mini).map_err(|e| e.to_string())?;
    mini.set_ignore_cursor_events(busy)
        .map_err(|e| e.to_string())?;
    platform::minimize_no_activate(&main).map_err(|e| e.to_string())
}

/// A tarefa terminou (ou comecou) com o mini chat em cena: liga ou desliga cliques e foco.
#[tauri::command]
pub fn set_mini_busy(app: AppHandle, busy: bool) -> Result<(), String> {
    let mini = window(&app, "mini")?;
    platform::set_no_activate(&mini, busy);
    mini.set_ignore_cursor_events(busy)
        .map_err(|e| e.to_string())
}

/// Volta para a janela completa (pedido do usuario).
#[tauri::command]
pub fn restore_main(app: AppHandle) -> Result<(), String> {
    let mini = window(&app, "mini")?;
    let main = window(&app, "main")?;
    mini.hide().map_err(|e| e.to_string())?;
    main.unminimize().map_err(|e| e.to_string())?;
    main.show().map_err(|e| e.to_string())?;
    main.set_focus().map_err(|e| e.to_string())
}

/// Fecha so o mini chat; a principal segue na barra de tarefas.
#[tauri::command]
pub fn close_mini(app: AppHandle) -> Result<(), String> {
    window(&app, "mini")?.hide().map_err(|e| e.to_string())
}

/// Atalho de acesso rapido (Alt+Espaco): o mini chat aparece ja com foco na caixa; de novo, some.
#[tauri::command]
pub fn quick_entry(app: AppHandle) -> Result<(), String> {
    let mini = window(&app, "mini")?;
    if mini.is_visible().unwrap_or(false) && mini.is_focused().unwrap_or(false) {
        return mini.hide().map_err(|e| e.to_string());
    }
    place_mini(&app, &mini)?;
    platform::set_no_activate(&mini, false);
    mini.set_ignore_cursor_events(false)
        .map_err(|e| e.to_string())?;
    mini.show().map_err(|e| e.to_string())?;
    mini.set_focus().map_err(|e| e.to_string())
}

#[cfg(windows)]
mod platform {
    use tauri::WebviewWindow;
    use windows_sys::Win32::Foundation::HWND;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, ShowWindow, GWL_EXSTYLE, SW_SHOWMINNOACTIVE,
        SW_SHOWNOACTIVATE, WS_EX_NOACTIVATE,
    };

    fn hwnd(win: &WebviewWindow) -> Option<HWND> {
        win.hwnd().ok().map(|h| h.0 as HWND)
    }

    /// WS_EX_NOACTIVATE: clicar na janela nao rouba o foco do app que o agente esta usando.
    pub fn set_no_activate(win: &WebviewWindow, on: bool) {
        let Some(h) = hwnd(win) else { return };
        unsafe {
            let style = GetWindowLongPtrW(h, GWL_EXSTYLE);
            let flag = WS_EX_NOACTIVATE as isize;
            let next = if on { style | flag } else { style & !flag };
            if next != style {
                SetWindowLongPtrW(h, GWL_EXSTYLE, next);
            }
        }
    }

    pub fn show_no_activate(win: &WebviewWindow) -> tauri::Result<()> {
        match hwnd(win) {
            Some(h) => {
                unsafe { ShowWindow(h, SW_SHOWNOACTIVATE) };
                Ok(())
            }
            None => win.show(),
        }
    }

    pub fn minimize_no_activate(win: &WebviewWindow) -> tauri::Result<()> {
        match hwnd(win) {
            Some(h) => {
                unsafe { ShowWindow(h, SW_SHOWMINNOACTIVE) };
                Ok(())
            }
            None => win.minimize(),
        }
    }
}

#[cfg(not(windows))]
mod platform {
    use tauri::WebviewWindow;

    pub fn set_no_activate(_win: &WebviewWindow, _on: bool) {}

    pub fn show_no_activate(win: &WebviewWindow) -> tauri::Result<()> {
        win.show()
    }

    pub fn minimize_no_activate(win: &WebviewWindow) -> tauri::Result<()> {
        win.minimize()
    }
}

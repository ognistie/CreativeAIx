//! Atualizacao automatica assinada (feature `updater`).
//!
//! Sem a feature, os comandos respondem "sem atualizacao" e nada sai para a rede. Com a feature, o
//! build de release recebe a chave publica e o endereco do latest.json (tauri.updater.conf.json, gerado
//! na CI a partir de segredos) e so instala pacote assinado pela chave privada correspondente.

use serde::Serialize;
use tauri::AppHandle;

#[derive(Serialize)]
pub struct Available {
    pub version: String,
    pub notes: Option<String>,
}

#[cfg(feature = "updater")]
mod imp {
    use super::Available;
    use tauri::AppHandle;
    use tauri_plugin_updater::UpdaterExt;

    pub async fn check(app: AppHandle) -> Result<Option<Available>, String> {
        let updater = app.updater().map_err(|e| e.to_string())?;
        let found = updater.check().await.map_err(|e| e.to_string())?;
        Ok(found.map(|u| Available { version: u.version.clone(), notes: u.body.clone() }))
    }

    pub async fn install(app: AppHandle) -> Result<(), String> {
        let updater = app.updater().map_err(|e| e.to_string())?;
        let Some(update) = updater.check().await.map_err(|e| e.to_string())? else {
            return Ok(());
        };
        update
            .download_and_install(|_, _| {}, || {})
            .await
            .map_err(|e| e.to_string())?;
        app.restart();
    }
}

#[cfg(not(feature = "updater"))]
mod imp {
    use super::Available;
    use tauri::AppHandle;

    pub async fn check(_app: AppHandle) -> Result<Option<Available>, String> {
        Ok(None)
    }

    pub async fn install(_app: AppHandle) -> Result<(), String> {
        Err("atualização automática desligada nesta versão".into())
    }
}

/// Ha versao nova? (None sem a feature ou sem atualizacao)
#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<Option<Available>, String> {
    imp::check(app).await
}

/// Baixa, confere a assinatura, instala e reinicia.
#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<(), String> {
    imp::install(app).await
}

/// Registra o plugin quando a feature esta ligada.
pub fn plugin<R: tauri::Runtime>(builder: tauri::Builder<R>) -> tauri::Builder<R> {
    #[cfg(feature = "updater")]
    {
        builder.plugin(tauri_plugin_updater::Builder::new().build())
    }
    #[cfg(not(feature = "updater"))]
    {
        builder
    }
}

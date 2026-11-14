//! Nucleo Python como processo filho: `main.py --ui tauri --headless`.
//!
//! O nucleo anuncia porta e token numa unica linha no stdout (`CREATIVE_AIX_READY {...}`).
//! O stdin fica aberto enquanto a casca vive: fechar o stdin (ou a casca morrer) encerra o nucleo.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const READY_PREFIX: &str = "CREATIVE_AIX_READY ";
const STDERR_TAIL: usize = 20;
const STOP_GRACE: Duration = Duration::from_secs(5);
/// Nucleo empacotado (scripts/build_core.py): <recursos>/core/creative-aix-core.exe
const PACKAGED_CORE: &str = "creative-aix-core.exe";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CoreInfo {
    pub port: u16,
    pub token: String,
}

#[derive(Default)]
struct Shared {
    generation: u64,
    info: Option<CoreInfo>,
    error: Option<String>,
    stderr: VecDeque<String>,
}

struct Running {
    child: Child,
    stdin: Option<ChildStdin>,
}

pub struct Sidecar {
    shared: Arc<(Mutex<Shared>, Condvar)>,
    running: Mutex<Option<Running>>,
    resource_dir: Option<PathBuf>,
}

impl Sidecar {
    /// `resource_dir`: pasta de recursos do app instalado (onde fica o nucleo empacotado).
    pub fn new(resource_dir: Option<PathBuf>) -> Self {
        Self {
            shared: Arc::new((Mutex::new(Shared::default()), Condvar::new())),
            running: Mutex::new(None),
            resource_dir,
        }
    }

    /// Sobe o nucleo. A porta e o token chegam depois, por `info`.
    pub fn start(&self) -> Result<(), String> {
        let mut running = self.running.lock().map_err(|_| "estado do nucleo corrompido")?;
        if running.is_some() {
            return Ok(());
        }
        let generation = {
            let (lock, _) = &*self.shared;
            let mut s = lock.lock().map_err(|_| "estado do nucleo corrompido")?;
            s.generation += 1;
            s.info = None;
            s.error = None;
            s.stderr.clear();
            s.generation
        };

        let launch = Launch::resolve(self.resource_dir.as_deref())?;
        let mut cmd = Command::new(&launch.program);
        cmd.args(&launch.args)
            .args(["--ui", "tauri", "--headless"])
            .current_dir(&launch.dir)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8")
            // Fase 4: o nucleo usa o PID da casca para saber quando o agente foi para outro app.
            .env("CREATIVE_AIX_SHELL_PID", std::process::id().to_string())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if cfg!(debug_assertions) {
            cmd.arg("--dev"); // aceita a origem do Vite (http://127.0.0.1:1420)
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("nao consegui abrir o nucleo ({}): {e}", launch.program.display()))?;
        let stdout = child.stdout.take().ok_or("sem stdout do nucleo")?;
        let stderr = child.stderr.take().ok_or("sem stderr do nucleo")?;
        let stdin = child.stdin.take();

        let shared = Arc::clone(&self.shared);
        thread::Builder::new()
            .name("core-stderr".into())
            .spawn(move || {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    let (lock, _) = &*shared;
                    if let Ok(mut s) = lock.lock() {
                        if s.generation != generation {
                            break;
                        }
                        if s.stderr.len() == STDERR_TAIL {
                            s.stderr.pop_front();
                        }
                        s.stderr.push_back(line);
                    }
                }
            })
            .map_err(|e| e.to_string())?;

        let shared = Arc::clone(&self.shared);
        thread::Builder::new()
            .name("core-stdout".into())
            .spawn(move || {
                let mut announced = false;
                for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                    if announced {
                        continue; // o nucleo nao deve escrever mais nada aqui; so drena
                    }
                    let Some(json) = line.strip_prefix(READY_PREFIX) else {
                        // Antes do anuncio, o que sair aqui e erro de subida (ex.: chave ausente):
                        // guarda junto do stderr para a tela mostrar se o nucleo cair.
                        let (lock, _) = &*shared;
                        if let Ok(mut s) = lock.lock() {
                            if s.generation == generation && !line.trim().is_empty() {
                                if s.stderr.len() == STDERR_TAIL {
                                    s.stderr.pop_front();
                                }
                                s.stderr.push_back(line.clone());
                            }
                        }
                        continue;
                    };
                    {
                        let parsed = serde_json::from_str::<CoreInfo>(json)
                            .map_err(|e| format!("anuncio do nucleo invalido: {e}"));
                        let (lock, cvar) = &*shared;
                        if let Ok(mut s) = lock.lock() {
                            if s.generation != generation {
                                return;
                            }
                            match parsed {
                                Ok(info) => s.info = Some(info),
                                Err(e) => s.error = Some(e),
                            }
                            announced = true;
                            cvar.notify_all();
                        }
                    }
                }
                // stdout fechou: o nucleo saiu
                let (lock, cvar) = &*shared;
                if let Ok(mut s) = lock.lock() {
                    if s.generation == generation {
                        let tail: Vec<String> = s.stderr.iter().cloned().collect();
                        s.info = None;
                        s.error = Some(if tail.is_empty() {
                            "o nucleo encerrou".to_string()
                        } else {
                            format!("o nucleo encerrou:\n{}", tail.join("\n"))
                        });
                        cvar.notify_all();
                    }
                }
            })
            .map_err(|e| e.to_string())?;

        *running = Some(Running { child, stdin });
        Ok(())
    }

    /// Espera o anuncio do nucleo (ou o erro de subida).
    pub fn info(&self, timeout: Duration) -> Result<CoreInfo, String> {
        let (lock, cvar) = &*self.shared;
        let deadline = Instant::now() + timeout;
        let mut s = lock.lock().map_err(|_| "estado do nucleo corrompido")?;
        loop {
            if let Some(info) = &s.info {
                return Ok(info.clone());
            }
            if let Some(err) = &s.error {
                return Err(err.clone());
            }
            let now = Instant::now();
            if now >= deadline {
                return Err("o nucleo demorou demais para abrir".into());
            }
            s = cvar
                .wait_timeout(s, deadline - now)
                .map_err(|_| "estado do nucleo corrompido")?
                .0;
        }
    }

    /// Fecha o stdin (o nucleo encerra sozinho); depois de STOP_GRACE, mata.
    pub fn stop(&self) {
        let Ok(mut running) = self.running.lock() else { return };
        let Some(mut r) = running.take() else { return };
        {
            let (lock, cvar) = &*self.shared;
            if let Ok(mut s) = lock.lock() {
                s.generation += 1;
                s.info = None;
                s.error = Some("o nucleo foi encerrado".into());
                cvar.notify_all();
            }
        }
        drop(r.stdin.take());
        let deadline = Instant::now() + STOP_GRACE;
        while Instant::now() < deadline {
            match r.child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => thread::sleep(Duration::from_millis(100)),
                Err(_) => break,
            }
        }
        let _ = r.child.kill();
        let _ = r.child.wait();
    }

    pub fn restart(&self) -> Result<(), String> {
        self.stop();
        self.start()
    }
}

/// O que executar para subir o nucleo.
/// Ordem: CREATIVE_AIX_PYTHON / CREATIVE_AIX_APP (desenvolvimento manual); o nucleo empacotado nos
/// recursos do app instalado; o repositorio (desenvolvimento, `npm run tauri dev`).
struct Launch {
    program: PathBuf,
    args: Vec<OsString>,
    dir: PathBuf,
}

impl Launch {
    fn resolve(resource_dir: Option<&Path>) -> Result<Self, String> {
        let forced = std::env::var_os("CREATIVE_AIX_PYTHON").is_some() || std::env::var_os("CREATIVE_AIX_APP").is_some();
        if !forced {
            if let Some(core_dir) = resource_dir.map(|r| r.join("core")) {
                let exe = core_dir.join(PACKAGED_CORE);
                if exe.is_file() {
                    return Ok(Self { program: exe, args: Vec::new(), dir: core_dir });
                }
            }
        }
        let app_dir = match std::env::var_os("CREATIVE_AIX_APP") {
            Some(dir) => PathBuf::from(dir),
            None => repo_root().join("app"),
        };
        let main_py = app_dir.join("main.py");
        if !main_py.is_file() {
            return Err(format!("nucleo nao encontrado: nem {PACKAGED_CORE} nos recursos nem main.py em {}", app_dir.display()));
        }
        let python = match std::env::var_os("CREATIVE_AIX_PYTHON") {
            Some(p) => PathBuf::from(p),
            None => {
                let venv = repo_root().join(".venv").join("Scripts").join("python.exe");
                if venv.is_file() {
                    venv
                } else {
                    PathBuf::from("python")
                }
            }
        };
        Ok(Self { program: python, args: vec![main_py.into_os_string()], dir: app_dir })
    }
}

fn repo_root() -> PathBuf {
    // ui/src-tauri -> raiz do repositorio
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .map(Path::to_path_buf)
        .unwrap_or_default()
}

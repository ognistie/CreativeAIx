"""Ações de arquivo, projeto, planilha e código do AutomationEngine (separadas de core/automation.py).

Sem janela, mouse ou teclado: só sistema de arquivos e os executores isolados (artifact_builder,
project_versions, process_runner). O AutomationEngine herda FileActions; a porta de política continua
no execute() de core/automation.py.
"""

import glob
import json
import os
import pathlib
import shutil
import time
import getpass
from datetime import datetime


BLOCKED_CMDS = ["rm -rf","rmdir /s","format c","del /f /s","shutdown","reg delete","diskpart","bcdedit"]
USERNAME = getpass.getuser()
BASE = f"C:/Users/{USERNAME}"


def expand(p):
    """So o "~" do INICIO e a pasta do usuario (como os.path.expanduser, que a validacao usa). Antes todo "~"
    era trocado: o nome curto do Windows "ABCDEF~1" virava "ABCDEC:/Users/...1" e o caminho executado deixava
    de ser o caminho validado pela politica."""
    if not p: return p
    if p == "~" or p.startswith(("~/", "~\\")):
        p = BASE + p[1:]
    p = p.replace("$HOME",BASE).replace("%USERPROFILE%",BASE)
    return os.path.expandvars(p).replace("\\","/")


def safe(cmd):
    return not any(b in cmd.lower().strip() for b in BLOCKED_CMDS)


class FileActions:
    """Handlers de arquivo/projeto/código; o execute() do AutomationEngine os chama pelo nome da ação."""

    def _create_project(self, p):
        from core.artifact_builder import build_project
        return build_project(p.get('manifest'))

    def _create_workbook(self, p):
        from core.artifact_builder import build_workbook
        return build_workbook(p.get('manifest'))

    def _run_python(self, p):
        """Same-user managed worker; no code executes in the desktop process."""
        if self.dry_run:
            return "[SIM] Python"
        code = p.get("code", "")
        if not isinstance(code, str) or not code.strip():
            return {"success": False, "status": "rejected", "result": "Codigo vazio.", "verified": False}
        from core.process_runner import run_python
        import uuid
        directory = pathlib.Path(__file__).resolve().parent.parent / "memory" / "executions" / uuid.uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
        cwd = str(directory)
        serializable = {}
        for key, value in self.workspace.items():
            try:
                json.dumps(value, allow_nan=False)
                serializable[key] = value
            except (TypeError, ValueError):
                continue
        result = run_python(code.replace("{BASE}", BASE).replace("{USERNAME}", USERNAME),
                            workspace=serializable, cwd=cwd,
                            should_stop=getattr(self, "should_stop", None))
        if result["success"]:
            self.workspace.update(result.pop("workspace", {}))
        result["result"] = f"🐍 {p.get('description', 'codigo')}\n" + result["result"]
        return result

    def _pip_install(self, p):
        return {"success": False, "status": "rejected", "verified": False,
                "result": "Instalacao durante tarefas desativada. Instale dependencias pelo ambiente do projeto."}

    # === SMART ACTIONS ===
    def _excel_write(self, p):
        data = p.get("data", []); filepath = expand(p.get("filepath", "")); sheet = p.get("sheet_name", "Planilha1")
        if self.dry_run: return f"[SIM] Excel: {len(data)} linhas"
        if not data: return "❌ Dados vazios"
        if not filepath: filepath = os.path.join(BASE, "Desktop", f"planilha_{datetime.now().strftime('%H%M%S')}.xlsx")
        try:
            import openpyxl
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = sheet
            for row in data: ws.append([str(c) for c in row])
            for col in ws.columns:
                mx = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[col[0].column_letter].width = max(mx+2, 10)
            if os.path.dirname(filepath): os.makedirs(os.path.dirname(filepath), exist_ok=True)
            wb.save(filepath)
            os.startfile(filepath); time.sleep(2)     # abre pelo app padrao, sem passar o caminho por um shell
            return f"📊 {filepath} ({len(data)} linhas)"
        except ImportError:
            return "❌ openpyxl não instalado. Use pip_install primeiro."

    # === FILES ===
    def _list_files(self, p):
        path = expand(p.get("path","."))
        if not os.path.exists(path): return f"❌ {path}"
        items = []
        for i in os.listdir(path):
            f = os.path.join(path,i); t = "📁" if os.path.isdir(f) else "📄"
            try: s = self._fmt(os.path.getsize(f))
            except: s = "?"
            items.append(f"{t} {i} ({s})")
        return "\n".join(items[:50]) if items else "Vazio"

    def _move_file(self, p):
        s,d = expand(p.get("source","")),expand(p.get("destination",""))
        if not os.path.exists(s): return f"❌ {s}"
        if os.path.lexists(d): return f"⛔ Destino ja existe: {d}"
        if os.path.dirname(d): os.makedirs(os.path.dirname(d),exist_ok=True)
        shutil.move(s,d)
        ok = os.path.exists(d) and not os.path.exists(s)
        return {"success": ok, "verified": ok, "result": f"→ {d}",
                "evidence": {"verifier": "filesystem", "source_absent": not os.path.exists(s), "destination": d}}

    def _copy_file(self, p):
        s,d = expand(p.get("source","")),expand(p.get("destination",""))
        if not os.path.exists(s): return f"❌ {s}"
        if os.path.lexists(d): return f"⛔ Destino ja existe: {d}"
        if os.path.dirname(d): os.makedirs(os.path.dirname(d),exist_ok=True)
        shutil.copytree(s,d) if os.path.isdir(s) else shutil.copy2(s,d)
        # Existence is observed, but content equality of a directory is not assumed.
        return {"success": os.path.exists(d), "verified": False, "result": f"→ {d}",
                "evidence": {"verifier": "filesystem", "destination": d}}

    def _create_folder(self, p):
        path = expand(p.get("path","")); os.makedirs(path,exist_ok=True)
        return {"success": os.path.isdir(path), "verified": os.path.isdir(path), "result": f"📁 {path}",
                "evidence": {"verifier": "filesystem", "directory": path}}

    def _delete_file(self, p):
        path = expand(p.get("path",""))
        if not os.path.exists(path): return "❌"
        from send2trash import send2trash
        send2trash(path)
        return {"success": not os.path.exists(path), "verified": not os.path.exists(path),
                "result": "Enviado para a lixeira.", "evidence": {"verifier": "filesystem_absence", "path": path}}

    def _read_file(self, p):
        path = expand(p.get("path",""))
        if not os.path.exists(path): return "❌"
        try:
            with open(path,"r",encoding="utf-8") as f: return f.read(5000)
        except: return "❌ Binário"

    def _write_file(self, p):
        path, content = expand(p.get("path","")), p.get("content","")
        if self.dry_run: return f"[SIM] Gravar {path} ({len(content)} chars)"
        if os.path.dirname(path): os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w",encoding="utf-8") as f: f.write(content)
        return f"✅ {path} ({len(content)} chars)"

    # === PROJETO EXISTENTE (continuacao da conversa) ===
    def _edit_project(self, p):
        """Grava as alteracoes de um projeto guardando ANTES a versao anterior
        (projeto/.ai_versions/<data>/), para 'desfaz' voltar."""
        from core.project_versions import apply_edit
        folder, files = p.get("folder", ""), p.get("files") or []
        if self.dry_run:
            return f"[SIM] Editaria {len(files)} arquivo(s) em {folder}: " + \
                   ", ".join(f.get("path", "") for f in files)[:200]
        r = apply_edit(folder, files, expected_hashes=p.get('expected_hashes'))
        if not r["ok"]:
            return f"❌ {r['error']}"
        paths = [str(pathlib.Path(folder) / rel) for rel in r['changed']]
        return {"success": True, "verified": r.get('verified', False),
                "result": f"Projeto alterado e conteudo conferido. Versao anterior preservada.\nPasta: {folder}",
                "artifacts": {"folder": folder, "files": paths},
                "evidence": {"verifier": "filesystem", "scope": "artifact_content", "files": paths}}

    def _revert_project(self, p):
        from core.project_versions import revert_last
        folder = p.get("folder", "")
        if self.dry_run: return f"[SIM] Voltar a versão anterior de {folder}"
        r = revert_last(folder)
        if not r["ok"]:
            return f"❌ {r['error']}"
        return {"success": True, "verified": False,
                "result": f"Versao anterior restaurada ({', '.join(r['restored'])})\nPasta: {folder}"}

    def _find_files(self, p):
        path, pat = expand(p.get("path",".")), p.get("pattern","*")
        m = glob.glob(os.path.join(path,"**",pat),recursive=True)[:30]
        return "\n".join(f"📄 {f}" for f in m) if m else "Nenhum"

    def _run_command(self, p):
        command = p.get("command", "")
        if not isinstance(command, str) or not command.strip() or not safe(command):
            return {"success": False, "status": "rejected", "verified": False, "result": "Comando bloqueado ou vazio."}
        from core.process_runner import run_command
        return run_command(command, timeout=30, should_stop=getattr(self, "should_stop", None))

    @staticmethod
    def _fmt(b):
        for u in ["B","KB","MB","GB"]:
            if b < 1024: return f"{b:.0f}{u}"
            b /= 1024
        return f"{b:.0f}TB"

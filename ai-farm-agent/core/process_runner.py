"""Bounded same-user worker processes. This is process containment, not a sandbox.

Windows Job Objects kill descendants on close. If job setup fails, no user code is released.
https://learn.microsoft.com/windows/win32/procthread/job-objects
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import threading
from contextlib import contextmanager
from pathlib import Path

OUTPUT_LIMIT = 1024 * 1024
WORKSPACE_LIMIT = 256 * 1024
CREATE_SUSPENDED = 0x00000004  # not exported by subprocess


@contextmanager
def _working_directory():
    directory = tempfile.TemporaryDirectory(prefix='ai-farm-worker-')
    try:
        yield directory.name
    finally:
        # Windows can release inherited file handles just after process exit is signalled.
        for attempt in range(40):
            try:
                directory.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)


def _resume(process):
    # Popen closes the primary thread handle, so ResumeThread is not available here.
    import ctypes
    status = ctypes.WinDLL('ntdll').NtResumeProcess(ctypes.c_void_p(int(process._handle)))
    if status:
        raise OSError(f'NtResumeProcess falhou: {status & 0xffffffff:#x}')


def _attach_job(process, max_processes=8, max_memory=1024 * 1024 * 1024):
    """Assign a process created suspended to a new job, then let it run.

    A venv's python.exe is a launcher that starts the real interpreter. Assigning a job
    does not move children that already exist, and the launcher's own job allows silent
    breakaway, so a process assigned after that point leaves the whole tree outside this job.
    """
    if os.name != 'nt':
        return None
    import win32job
    job = win32job.CreateJobObject(None, '')
    try:
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        limits['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
        limits['BasicLimitInformation']['ActiveProcessLimit'] = max_processes
        limits['JobMemoryLimit'] = max_memory
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        win32job.AssignProcessToJobObject(job, int(process._handle))
        _resume(process)
        return job
    except Exception:
        job.Close()
        raise


class _Output:
    """Drain an inherited pipe continuously while retaining at most the configured limit."""
    def __init__(self, stream):
        self.stream, self.data = stream, bytearray()
        self.overflow = threading.Event()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            while True:
                block = self.stream.read(16384)
                if not block:
                    break
                available = OUTPUT_LIMIT - len(self.data)
                self.data.extend(block[:max(0, available)])
                if len(block) > available:
                    self.overflow.set()
        except (OSError, ValueError):
            pass

    def finish(self):
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError('Pipe de processo descendente permaneceu aberto.')
        self.stream.close()
        return self.data.decode('utf-8', 'replace')


def _run(payload, *, cwd=None, timeout=60, should_stop=None):
    stop = should_stop or (lambda: False)
    result = {'success': False, 'status': 'failed', 'verified': False, 'exit_code': None, 'result': ''}
    if stop():
        return {**result, 'status': 'cancelled', 'result': 'Cancelado antes de iniciar.'}
    timeout = max(0.05, min(float(timeout), 120))
    worker = Path(__file__).with_name('process_worker.py')
    with _working_directory() as tmp:
        root = Path(tmp)
        payload['result_path'] = str(root / 'result.json')
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(encoded) > WORKSPACE_LIMIT * 4:
            return {**result, 'result': 'Entrada do worker excede o limite.'}
        process, job, stdout, stderr = None, None, None, None
        output, errors = '', ''
        try:
            environment = {k: v for k, v in os.environ.items() if k.upper() in {
                'SYSTEMROOT', 'WINDIR', 'PATH', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA',
                'LOCALAPPDATA', 'TMP', 'TEMP', 'COMSPEC', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
                'PROGRAMDATA', 'USERNAME', 'LANG', 'LC_ALL'}}
            environment['PYTHONIOENCODING'] = 'utf-8'
            process = subprocess.Popen([sys.executable, '-u', str(worker)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd or tmp,
                creationflags=subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt', env=environment)
            stdout, stderr = _Output(process.stdout), _Output(process.stderr)
            job = _attach_job(process)
            process.stdin.write(encoded)
            process.stdin.close()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if stop():
                    result.update(status='cancelled', result='Execucao cancelada.')
                    break
                if time.monotonic() >= deadline:
                    result.update(status='timeout', result='Tempo limite de execucao atingido.')
                    break
                if stdout.overflow.is_set() or stderr.overflow.is_set():
                    result.update(status='output_limit', result='Limite de saida excedido.')
                    break
                manifest = root / 'result.json'
                if manifest.exists() and manifest.stat().st_size > OUTPUT_LIMIT:
                    result.update(status='output_limit', result='Manifesto excede limite de saida.')
                    break
                time.sleep(0.025)
            else:
                result['exit_code'] = process.returncode
                manifest = root / 'result.json'
                if manifest.exists() and manifest.stat().st_size <= OUTPUT_LIMIT:
                    data = json.loads(manifest.read_text(encoding='utf-8'))
                    result.update(success=data.get('success') is True and process.returncode == 0,
                                  exit_code=data.get('exit_code', process.returncode))
                    workspace = data.get('workspace', {})
                    if isinstance(workspace, dict) and len(json.dumps(workspace)) <= WORKSPACE_LIMIT:
                        result['workspace'] = workspace
                result['status'] = 'succeeded' if result['success'] else 'failed'
        except Exception as error:
            result.update(success=False, status='failed', result=f'Worker indisponivel: {error}')
        finally:
            if job is not None:
                import win32job
                try:
                    win32job.TerminateJobObject(job, 1)
                    until = time.monotonic() + 10
                    while win32job.QueryInformationJobObject(job, win32job.JobObjectBasicAccountingInformation)['ActiveProcesses']:
                        if time.monotonic() >= until:
                            raise RuntimeError('A arvore nao confirmou encerramento.')
                        time.sleep(0.025)
                finally:
                    job.Close()
            elif process is not None and os.name != 'nt':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
            if stdout is not None:
                output = stdout.finish()
            if stderr is not None:
                errors = stderr.finish()
        if stdout is not None and (stdout.overflow.is_set() or stderr.overflow.is_set()):
            result.update(success=False, status='output_limit', result='Limite de saida excedido.')
        if result['status'] in ('succeeded', 'failed') and not result['result']:
            result['result'] = (output + ('\n' + errors if errors else '')).strip()[:8000] or (
                'Processo concluido.' if result['success'] else 'Processo falhou.')
        return result


def run_python(code, workspace=None, **kwargs):
    return _run({'mode': 'python', 'code': code, 'workspace': workspace or {}}, **kwargs)


def run_command(command, **kwargs):
    return _run({'mode': 'command', 'command': command}, **kwargs)


# ── Processo de longa duracao com saida linha a linha (CLIs do Claude Code e do Codex) ──────

STREAM_TIMEOUT_MAX = 1800
STREAM_LINE_LIMIT = 256 * 1024
STREAM_STDERR_LIMIT = 64 * 1024
# As CLIs de codigo abrem varios processos (sandbox do Codex, helper de ACL, servidor MCP, node): com o
# limite de 8 do worker o 9o era negado e o Codex nao conseguia gravar arquivo.
STREAM_MAX_PROCESSES = 64
STREAM_MAX_MEMORY = 4 * 1024 * 1024 * 1024
_SECRET_ENV = re.compile(r'(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)', re.I)
# Variaveis que uma CLI instalada pela pessoa precisa para achar a propria sessao e o Windows.
# Nada com cara de segredo passa, mesmo que esteja no ambiente do app.
_STREAM_ENV = {'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'PATH', 'PATHEXT', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'HOME',
               'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'TMP', 'TEMP', 'COMSPEC', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
               'USERNAME', 'COMPUTERNAME', 'NUMBER_OF_PROCESSORS', 'LANG', 'LC_ALL', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR'}


def child_environment():
    env = {k: v for k, v in os.environ.items() if k.upper() in _STREAM_ENV and not _SECRET_ENV.search(k)}
    env['PYTHONIOENCODING'] = 'utf-8'
    env['NO_COLOR'] = '1'
    return env


class _Lines:
    """Entrega cada linha do stdout a `on_line` assim que chega; guarda so a contagem."""
    def __init__(self, stream, on_line):
        self.stream, self.on_line, self.count = stream, on_line, 0
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            for raw in iter(self.stream.readline, b''):
                self.count += 1
                if self.on_line is None or len(raw) > STREAM_LINE_LIMIT:
                    continue
                try:
                    self.on_line(raw.decode('utf-8', 'replace').rstrip('\r\n'))
                except Exception:
                    pass
        except (OSError, ValueError):
            pass

    def finish(self):
        self.thread.join(timeout=10)
        self.stream.close()


def stream_process(argv, *, cwd, stdin_text=None, on_line=None, should_stop=None, timeout=600):
    """Roda `argv` na pasta `cwd` dentro de um Job Object (morre com o app), com a saida linha a
    linha em `on_line`. Para no `should_stop` e no tempo limite. Sem shell, sem segredos no ambiente.
    -> {'status': succeeded|failed|cancelled|timeout, 'exit_code', 'stderr', 'lines', 'result'}"""
    stop = should_stop or (lambda: False)
    result = {'success': False, 'status': 'failed', 'verified': False, 'exit_code': None, 'result': '',
              'stderr': '', 'lines': 0}
    if stop():
        return {**result, 'status': 'cancelled', 'result': 'Cancelado antes de iniciar.'}
    timeout = max(0.05, min(float(timeout), STREAM_TIMEOUT_MAX))
    process, job, stdout, stderr = None, None, None, None
    try:
        process = subprocess.Popen([str(a) for a in argv], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=cwd, env=child_environment(),
                                   creationflags=subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED if os.name == 'nt' else 0,
                                   start_new_session=os.name != 'nt')
        stdout, stderr = _Lines(process.stdout, on_line), _Output(process.stderr)
        job = _attach_job(process, STREAM_MAX_PROCESSES, STREAM_MAX_MEMORY)
        try:
            if stdin_text:
                process.stdin.write(stdin_text.encode('utf-8'))
        except OSError:
            pass
        finally:
            process.stdin.close()
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if stop():
                result.update(status='cancelled', result='Execucao cancelada.')
                break
            if time.monotonic() >= deadline:
                result.update(status='timeout', result='Tempo limite de execucao atingido.')
                break
            time.sleep(0.05)
        else:
            result['exit_code'] = process.returncode
            result['success'] = process.returncode == 0
            result['status'] = 'succeeded' if result['success'] else 'failed'
    except Exception as error:
        result.update(success=False, status='failed', result=f'Processo indisponivel: {error}')
    finally:
        if job is not None:
            import win32job
            try:
                win32job.TerminateJobObject(job, 1)
                until = time.monotonic() + 10
                while win32job.QueryInformationJobObject(job, win32job.JobObjectBasicAccountingInformation)['ActiveProcesses']:
                    if time.monotonic() >= until:
                        raise RuntimeError('A arvore nao confirmou encerramento.')
                    time.sleep(0.025)
            finally:
                job.Close()
        elif process is not None and os.name != 'nt':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        if stdout is not None:
            stdout.finish()
            result['lines'] = stdout.count
        if stderr is not None:
            result['stderr'] = stderr.finish()[-STREAM_STDERR_LIMIT:]
    return result

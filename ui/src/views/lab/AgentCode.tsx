import { memo, useEffect, useMemo, useState } from "react";
import { DevProposals } from "../../components/DevProposals";
import { Button, Field, Icon, Skeleton, Spinner } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { call, type Spec } from "./types";

// Codigo do agente: leitura dos arquivos que o definem (lista fechada no nucleo) e mudancas pelo Modo
// Desenvolvedor — Claude Code ou Codex numa copia separada, com diff, gate de testes e desfazer.
// O app nao grava codigo direto desta tela: cada mudanca e revisada antes de entrar.

export function AgentCode({ agent, name, files }: { agent: string; name: string; files: Spec["files"] }) {
  const own = files.filter((f) => !f.shared);
  const shared = files.filter((f) => f.shared);
  const [path, setPath] = useState(own[0]?.path ?? files[0]?.path ?? "");
  const [opened, setOpened] = useState(() => path ? [path] : []);
  const [source, setSource] = useState<{ path: string; text: string } | null>(null);
  const text = source?.path === path ? source.text : null;
  const [error, setError] = useState("");
  const [find, setFind] = useState("");
  const [codeOn, setCodeOn] = useState<boolean | null>(null);
  const [enabling, setEnabling] = useState(false);

  useEffect(() => {
    if (!path) return;
    let active = true;
    setError("");
    void call(core().call("studioSource", agent, path)).then((r) => {
      if (!active) return;
      if (r.ok) setSource({ path, text: (r.file as { text: string }).text });
      else setError(r.error || "Não deu para abrir.");
    });
    return () => { active = false; };
  }, [agent, path]);


  useEffect(() => {
    void call(core().call("harnessGet")).then((r) => r.ok && setCodeOn(!!(r.harness as { dev?: { code_changes?: boolean } }).dev?.code_changes));
  }, []);

  const enable = async () => {
    setEnabling(true);
    const r = await call(core().call("harnessGet"));
    if (r.ok) {
      const h = r.harness as { dev: Record<string, unknown> };
      h.dev = { ...h.dev, enabled: true, code_changes: true };
      const s = await call(core().call("harnessSave", JSON.stringify(h), "Mudanças de código ligadas"));
      if (s.ok) setCodeOn(true);
      else setError(s.error || "Não deu para ligar.");
    }
    setEnabling(false);
  };

  const context = `[Agente ${name}] Arquivos principais: ${own.map((f) => f.path).join(", ")}.`;

  const openFile = (file: string) => {
    setOpened((tabs) => tabs.includes(file) ? tabs : [...tabs, file]);
    setPath(file);
  };
  const closeFile = (file: string) => {
    const index = opened.indexOf(file);
    const next = opened.filter((item) => item !== file);
    setOpened(next);
    if (path === file) setPath(next[Math.min(index, next.length - 1)] ?? "");
  };

  return (
    <div className="code-workbench">
      <div className="code-layout">
        <nav aria-label="Explorador de arquivos do agente" className="code-files">
          <h3 className="mb-2 px-2 text-sm font-semibold text-fg">Explorador</h3>
          <FileGroup title="Deste agente" files={own} path={path} onPick={openFile} />
          {shared.length > 0 && <FileGroup title="Compartilhados" files={shared} path={path} onPick={openFile} />}
        </nav>

        <div className="code-document">
          <div className="code-filetabs" aria-label="Arquivos abertos">
            {opened.map((file) => <div key={file} data-active={path === file}>
              <button type="button" title={file} aria-current={path === file ? "true" : undefined} onClick={() => setPath(file)}>{file.split("/").at(-1)}</button>
              <button type="button" aria-label={`Fechar ${file.split("/").at(-1)}`} onClick={() => closeFile(file)}><Icon name="x" size={12} /></button>
            </div>)}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-b border-hairline px-4 py-2.5">
            <Icon name="file" size={14} className="text-fg-muted" />
            <span className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-fg">{path ? `app/${path}` : "Nenhum arquivo aberto"}</span>
            <span className="flex items-center gap-1 rounded-full bg-chip px-2 py-0.5 text-xs text-fg-muted">
              <Icon name="lock" size={11} /> Só leitura
            </span>
            <Field value={find} onChange={(e) => setFind(e.target.value)} placeholder="Destacar no arquivo" aria-label="Destacar texto no arquivo" className="h-7 w-48 text-xs" />
          </div>
          {!path ? <p className="p-5 text-sm text-fg-muted">Escolha um arquivo no Explorador.</p> : error ? (
            <p className="p-4 text-sm text-bad-ink">{error}</p>
          ) : text === null ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className={cn("h-3.5 rounded", ["w-2/5", "w-3/4", "w-1/2", "w-5/6", "w-2/3", "w-1/3"][i])} />
              ))}
            </div>
          ) : (
            <CodeView key={path} text={text} find={find} />
          )}
        </div>
      </div>

      <details className="code-proposals">
        <summary className="cursor-pointer text-md font-semibold text-fg">
          Propor alteração em {name}
        </summary>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">
          Descreva a mudança. O Claude Code ou o Codex trabalha numa cópia separada do projeto; você lê o diff, roda os testes (gate) e só então aplica. Dá
          para desfazer depois.
        </p>
        <div className="mt-4">
          {codeOn === null ? (
            <Spinner />
          ) : codeOn ? (
            <DevProposals context={context} filter={`[Agente ${name}]`} placeholder={`Ex.: no ${name}, registrar o tempo de cada passo no log`} />
          ) : (
            <div className="flex flex-wrap items-center gap-3 rounded-r3 border border-dashed border-hairline-hi p-4">
              <Icon name="lock" size={18} className="text-fg-muted" />
              <p className="min-w-0 flex-1 text-sm text-fg">
                Mudanças de código estão desligadas. Ao ligar, você poderá pedir alterações revisadas; nada é aplicado sem você.
              </p>
              <Button variant="primary" icon="shield-check" disabled={enabling} onClick={() => void enable()}>
                {enabling ? <Spinner size={12} /> : null} Ligar mudanças de código
              </Button>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

function FileGroup({ title, files, path, onPick }: { title: string; files: Spec["files"]; path: string; onPick: (p: string) => void }) {
  return (
    <div className="mb-2 last:mb-0">
      <p className="px-2 pb-1.5 pt-1 text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">{title}</p>
      <ul className="space-y-0.5">
        {files.map((f) => {
          const on = f.path === path;
          return (
            <li key={f.path}>
              <button
                type="button"
                aria-current={on ? "true" : undefined}
                title={f.doc || f.path}
                onClick={() => onPick(f.path)}
                className={cn("flex w-full items-center gap-2 rounded-r2 px-2 py-1.5 text-left transition-colors", on ? "bg-row-hover" : "hover:bg-hover")}
              >
                <Icon name="file-text" size={13} className="shrink-0 text-fg-muted" />
                <span className={cn("min-w-0 flex-1 truncate font-mono text-[12px]", on ? "text-fg" : "text-fg-muted")}>{f.path.split("/").pop()}</span>
                <span className="shrink-0 text-[11px] tabular-nums text-fg-muted">{f.lines}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Realce simples de Python (palavra-chave, texto, comentario, numero): leve, sem biblioteca.
const KW = /\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|yield|lambda|None|True|False|pass|break|continue|async|await|is|global|nonlocal)\b/g;

function highlight(line: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(#.*$)|("""|''')|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  const kw = (s: string, key: string) => {
    const parts: React.ReactNode[] = [];
    let i = 0;
    for (const k of s.matchAll(KW)) {
      parts.push(s.slice(i, k.index));
      parts.push(
        <span key={`${key}-${k.index}`} className="text-[var(--code-kw)]">
          {k[0]}
        </span>,
      );
      i = (k.index ?? 0) + k[0].length;
    }
    parts.push(s.slice(i));
    return parts;
  };
  while ((m = re.exec(line))) {
    out.push(...kw(line.slice(last, m.index), `k${last}`));
    const cls = m[1] ? "text-[var(--code-comment)] italic" : m[2] || m[3] ? "text-[var(--code-str)]" : "text-[var(--code-num)]";
    out.push(
      <span key={m.index} className={cls}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  out.push(...kw(line.slice(last), `k${last}e`));
  return out;
}

const CodeView = memo(function CodeView({ text, find }: { text: string; find: string }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const highlighted = useMemo(() => lines.map(highlight), [lines]);
  const q = find.trim().toLowerCase();
  const hits = useMemo(() => (q.length >= 2 ? lines.reduce((n, l) => n + (l.toLowerCase().includes(q) ? 1 : 0), 0) : 0), [lines, q]);
  return (
    <div className="relative">
      {q.length >= 2 && <p className="border-b border-hairline px-4 py-1.5 text-xs text-fg-muted">{hits} linha(s) com “{find}”</p>}
      <pre className="max-h-[62vh] select-text overflow-auto py-2 font-mono text-[12.5px] leading-[1.6] text-fg">
        {lines.map((l, i) => {
          const hit = q.length >= 2 && l.toLowerCase().includes(q);
          return (
            <div key={i} className={cn("flex", hit && "bg-accent/15")}>
              <span aria-hidden className="w-12 shrink-0 select-none pr-3 text-right tabular-nums text-fg-subtle/70">
                {i + 1}
              </span>
              <code className="whitespace-pre pr-6">{highlighted[i]}</code>
            </div>
          );
        })}
      </pre>
    </div>
  );
});

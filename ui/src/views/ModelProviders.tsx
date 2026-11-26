import { useCallback, useEffect, useState } from "react";
import { Button, Field, Segmented } from "../components/ui";
import { core } from "../lib/host";
import { cn } from "../lib/cn";

// Configuracoes > Modelos, no formato de "conexoes": cada provedor ligado vira um cartao com estado e Editar;
// o painel abaixo adiciona/edita (provedor do catalogo ou API personalizada compativel com OpenAI).
// A chave vai uma vez para o nucleo (DPAPI do Windows, core/secret_store.py) e nunca volta para a tela.

interface CatalogEntry {
  name: string;
  label: string;
  local: boolean;
  needs_key: boolean;
  configured: boolean;
  stored: boolean;
  signup: string;
  example: string;
  key_env: string;
  env_detected: boolean;
  custom: boolean;
  base_url: string;
  images: boolean;
  tools: boolean;
  web_search: boolean;
}

interface Catalog {
  catalog?: CatalogEntry[];
  models?: Record<"fast" | "strong", { chosen: string; default: string }>;
  can_store?: boolean;
  ok?: boolean;
  error?: string;
}

type Mode = "catalog" | "custom";
type Draft = { mode: Mode; provider: string; key: string; name: string; label: string; base_url: string; images: boolean; open: boolean };

const TIERS = [
  { tier: "strong", label: "Modelo principal", hint: "Maestro, código, planilhas e conversa" },
  { tier: "fast", label: "Modelo rápido", hint: "Visão, voz e tarefas curtas" },
] as const;

const selectClass = "h-[38px] w-full rounded-r3 border border-hairline-hi bg-surface px-3 text-md text-fg outline-none focus:border-accent/60";
const empty = (provider = ""): Draft => ({ mode: "catalog", provider, key: "", name: "", label: "", base_url: "", images: false, open: false });

function Dot({ ok }: { ok: boolean }) {
  return <span aria-hidden className={cn("inline-block size-2 rounded-full", ok ? "bg-ok" : "bg-bad")} />;
}

function Label({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-fg">
      {children}
      {hint && (
        <span title={hint} aria-label={hint} className="inline-grid size-4 cursor-help place-items-center rounded-full border border-hairline-hi text-[10px] text-fg-muted">
          ?
        </span>
      )}
    </p>
  );
}

export function ModelProviders() {
  const [data, setData] = useState<Catalog>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [found, setFound] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const apply = useCallback((r: unknown) => {
    const v = r as Catalog;
    setError(v.ok === false && v.error ? v.error : "");
    if (v.catalog) setData(v);
    return v;
  }, []);
  const refresh = useCallback(() => core().call("providerStatus").then(apply), [apply]);
  useEffect(() => {
    refresh().catch((e: Error) => setError(e.message));
  }, [refresh]);

  const catalog = data.catalog ?? [];
  const connected = catalog.filter((p) => p.configured && (p.stored || p.env_detected || p.custom || p.local || p.name === "anthropic"));
  const current = catalog.find((p) => p.name === draft?.provider);

  const test = (name: string) =>
    core()
      .call("providerModels", name)
      .then((r) => {
        const v = r as { ok?: boolean; models?: string[]; error?: string; hint?: string };
        if (v.models?.length) setFound((cur) => [...new Set([...cur, ...v.models!])]);
        setNote(v.ok ? (v.models?.length ? `Conectado: ${v.models.length} modelos disponíveis.` : v.hint || "Conectado.") : v.error || "Falhou.");
      })
      .catch((e: Error) => setNote(e.message));

  const submit = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      let r: Catalog;
      if (draft.mode === "custom") {
        r = apply(await core().call("providerCustomSave", JSON.stringify({ name: draft.name.trim().toLowerCase(), label: draft.label,
          base_url: draft.base_url.trim(), key: draft.key, images: draft.images, tools: true })));
      } else if (draft.key.trim()) {
        r = apply(await core().call("providerKeySave", draft.provider, draft.key));
      } else {
        r = apply(await core().call("providerStatus"));
      }
      if (r.ok !== false) {
        const name = draft.mode === "custom" ? draft.name.trim().toLowerCase() : draft.provider;
        setDraft(null);
        void test(name);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = (p: CatalogEntry) =>
    core()
      .call(p.custom ? "providerCustomRemove" : "providerKeyRemove", p.name)
      .then(apply)
      .then(() => setDraft(null))
      .catch((e: Error) => setError(e.message));

  const useModel = (tier: string, value: string) =>
    core()
      .call("saveSettings", JSON.stringify({ models: { [tier]: value.trim() } }))
      .then((r) => {
        if ((r as { ok?: boolean }).ok === false) setError("Modelo inválido: use provedor:modelo, ex.: deepseek:deepseek-chat.");
        else {
          setModels((m) => ({ ...m, [tier]: "" }));
          return refresh();
        }
      })
      .catch((e: Error) => setError(e.message));

  if (!data.catalog) return null;
  const envHint = current?.key_env ? `Deixe em branco para usar a variável do ambiente (${current.key_env})` : "Cole a chave de API";

  return (
    <section className="mb-8">
      <div className="photo-label">
        <h2 className="text-lg font-semibold text-fg">Modelos</h2>
        <p className="mt-1 text-sm text-fg-muted">Insira suas chaves de API para usar modelos destes provedores. As chaves ficam protegidas pelo Windows.</p>
      </div>

      {error && <p className="mt-3 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}

      <div className="mt-3 grid gap-2">
        {connected.map((p) => (
          <div key={p.name} className="flex items-center gap-2 rounded-r3 border border-edge bg-glass px-4 py-3.5 backdrop-blur-xl">
            <span className="text-md font-medium text-fg">{p.label}</span>
            <Dot ok />
            <span className="text-sm text-ok-ink">{p.local ? "Local" : "Conectado"}</span>
            <span className="flex-1" />
            {draft?.provider !== p.name && (
              <Button size="compact" onClick={() => { setNote(""); setDraft({ ...empty(p.name), mode: p.custom ? "custom" : "catalog", name: p.custom ? p.name : "",
                label: p.custom ? p.label : "", base_url: p.base_url, images: p.images }); }}>
                Editar
              </Button>
            )}
          </div>
        ))}
        {!draft && (
          <button type="button" onClick={() => { setNote(""); setDraft(empty(catalog.find((p) => !p.configured)?.name ?? "deepseek")); }}
            className="flex items-center gap-2 rounded-r3 border border-dashed border-hairline-hi px-4 py-3.5 text-left text-md text-fg-muted hover:bg-hover hover:text-fg">
            + Adicionar provedor
          </button>
        )}
      </div>

      {draft && (
        <div className="mt-2 rounded-r3 border border-edge bg-glass p-4 backdrop-blur-xl">
          <Segmented<Mode>
            label="Tipo de provedor"
            value={draft.mode}
            onValueChange={(mode) => setDraft({ ...draft, mode })}
            options={[{ value: "catalog", label: "Provedor do catálogo" }, { value: "custom", label: "API personalizada" }]}
          />
          {draft.mode === "catalog" ? (
            <div className="mt-3 grid gap-4">
              <p className="text-sm text-fg-muted">Escolha DeepSeek, OpenAI, OpenRouter, Ollama ou outro provedor do catálogo e insira sua chave de API.</p>
              <div className="max-w-[320px]">
                <Label>Provedor</Label>
                <select aria-label="Provedor" className={selectClass} value={draft.provider} onChange={(e) => setDraft({ ...draft, provider: e.target.value, key: "" })}>
                  {catalog.filter((p) => !p.custom).map((p) => (
                    <option key={p.name} value={p.name}>{p.label}</option>
                  ))}
                </select>
              </div>
              {current?.needs_key ? (
                <div>
                  <Label hint={`Crie a chave ou compre créditos em ${current.signup}`}>Chave de API</Label>
                  <Field type="password" autoComplete="off" aria-label="Chave de API" placeholder={current.stored ? "Chave guardada — cole outra para trocar" : envHint}
                    value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} />
                  {!current.stored && !current.env_detected && !draft.key && (
                    <p className="mt-1.5 text-sm text-warn-ink">
                      Variável não detectada. Insira uma chave de API{current.key_env ? ` ou configure ${current.key_env} no ambiente` : ""}.
                    </p>
                  )}
                </div>
              ) : (
                current && <p className="text-sm text-fg-muted">Roda neste computador, sem chave. Deixe o {current.label.replace(" (local)", "")} aberto ({current.signup}).</p>
              )}
            </div>
          ) : (
            <div className="mt-3 grid gap-4">
              <p className="text-sm text-fg-muted">Qualquer serviço compatível com a API da OpenAI (chat/completions). Endereço https, ou http só no próprio computador.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label hint="Usado no nome do modelo: nome:modelo">Nome curto</Label>
                  <Field aria-label="Nome curto" placeholder="ex.: minhaia" value={draft.name} disabled={catalog.some((p) => p.custom && p.name === draft.provider)}
                    onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                </div>
                <div>
                  <Label>Nome exibido</Label>
                  <Field aria-label="Nome exibido" placeholder="ex.: Minha IA" value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
                </div>
              </div>
              <div>
                <Label>Endereço da API</Label>
                <Field aria-label="Endereço da API" placeholder="https://api.exemplo.com/v1" value={draft.base_url} onChange={(e) => setDraft({ ...draft, base_url: e.target.value })} />
              </div>
              <div>
                <Label>Chave de API</Label>
                <Field type="password" autoComplete="off" aria-label="Chave de API" placeholder="Opcional para servidores locais"
                  value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} />
              </div>
            </div>
          )}

          <div className="mt-4 border-t border-hairline pt-3">
            <button type="button" onClick={() => setDraft({ ...draft, open: !draft.open })} className="flex items-center gap-1.5 text-sm font-medium text-fg-muted hover:text-fg">
              <span className={cn("inline-block transition-transform", draft.open && "rotate-90")}>›</span> Configurações personalizadas
            </button>
            {draft.open && (
              <div className="mt-3 grid gap-2 text-sm text-fg-muted">
                {draft.mode === "custom" && (
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={draft.images} onChange={(e) => setDraft({ ...draft, images: e.target.checked })} />
                    O modelo aceita imagens (necessário para o agente de visão)
                  </label>
                )}
                {current && draft.mode === "catalog" && (
                  <p>
                    {[current.images ? "aceita imagens" : "sem imagens", current.tools ? "usa as ferramentas do app" : "sem ferramentas",
                      current.web_search ? "busca na web" : "sem busca na web"].join(" · ")}
                    {current.example ? ` · ex.: ${current.example}` : ""}
                  </p>
                )}
                {current && current.name !== "anthropic" && (
                  <div><Button size="compact" variant="ghost" onClick={() => void test(current.name)}>Testar conexão</Button></div>
                )}
              </div>
            )}
          </div>

          {note && <p className="mt-2 text-sm text-fg-muted">{note}</p>}
          <div className="mt-4 flex items-center gap-2">
            {current && (current.stored || current.custom) && (
              <Button variant="danger" onClick={() => void remove(current)}>Remover</Button>
            )}
            <span className="flex-1" />
            <Button onClick={() => setDraft(null)}>Cancelar</Button>
            <Button variant="primary" disabled={busy || (draft.mode === "custom" && (!draft.name.trim() || !draft.base_url.trim()))} onClick={() => void submit()}>
              Aplicar
            </Button>
          </div>
        </div>
      )}

      <datalist id="model-options">
        {found.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
      <div className="mt-3 overflow-hidden rounded-r3 border border-edge bg-glass backdrop-blur-xl">
        {TIERS.map(({ tier, label, hint }) => {
          const info = data.models?.[tier];
          const active = info?.chosen || info?.default || "";
          return (
            <div key={tier} className="flex flex-wrap items-center gap-3 border-b border-hairline px-4 py-3 last:border-0">
              <div className="min-w-0 flex-1">
                <p className="text-md text-fg">{label}</p>
                <p className="mt-0.5 text-sm text-fg-muted">{hint} · em uso: {active}{info?.chosen ? "" : " (padrão)"}</p>
              </div>
              <div className="flex w-[340px] items-center gap-2">
                <Field aria-label={label} list="model-options" placeholder="provedor:modelo" value={models[tier] ?? ""}
                  onChange={(e) => setModels((m) => ({ ...m, [tier]: e.target.value }))} />
                <Button size="compact" disabled={!(models[tier] ?? "").trim()} onClick={() => void useModel(tier, models[tier] ?? "")}>Usar</Button>
                {info?.chosen && <Button size="compact" variant="ghost" onClick={() => void useModel(tier, "")}>Padrão</Button>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

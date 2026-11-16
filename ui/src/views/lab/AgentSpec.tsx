import { useState } from "react";
import { Button, GlassPanel, Icon, type IconName } from "../../components/ui";
import { cn } from "../../lib/cn";
import { AUTH_LABEL, EFFORT_LABEL, type Spec } from "./types";

// Visao geral: a especificacao do agente, lida do codigo e da configuracao (nao e texto escrito a mao).

export function AgentSpec({ spec, onGo }: { spec: Spec; onGo: (tab: string) => void }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2 [&>*]:min-w-0">
      <Card icon="target" title="O que faz">
        <ul className="space-y-2">
          {spec.does.map((d, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-fg">
              <Icon name="check-circle" size={15} className="mt-0.5 shrink-0 text-ok-ink" /> {d}
            </li>
          ))}
        </ul>
        {spec.inputs && (
          <p className="mt-4 text-sm text-fg-muted">
            <span className="font-medium text-fg">Recebe:</span> {spec.inputs}
          </p>
        )}
        {spec.examples.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">Exemplos de pedido</p>
            <div className="flex flex-wrap gap-1.5">
              {spec.examples.map((e) => (
                <span key={e} className="rounded-full bg-chip px-2.5 py-1 text-xs text-fg">
                  “{e}”
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card icon="sliders" title="Como roda" note="Definido em config.yaml. O Lab cria versões para testar outra configuração.">
        <dl className="grid grid-cols-2 gap-3">
          <Fact label="Modelo" value={spec.config.model} mono />
          <Fact label="Provedor" value={spec.config.provider} />
          <Fact label="Esforço" value={EFFORT_LABEL[spec.config.effort] ?? spec.config.effort} />
          <Fact label="Raciocínio" value={spec.config.thinking} />
          <Fact label="Limite de resposta" value={`${spec.config.max_tokens.toLocaleString("pt-BR")} tokens`} />
          <Fact label="Efeitos sensíveis" value={AUTH_LABEL[spec.authorization] ?? spec.authorization} />
        </dl>
      </Card>

      <Card icon="wrench" title="Ferramentas" note="Só estas ações são aceitas pelo executor para este agente (core/action_policy.py).">
        {spec.tools.length === 0 ? (
          <p className="text-sm text-fg-muted">Este agente não executa ações: ele planeja e entrega o trabalho para os outros.</p>
        ) : (
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {spec.tools.map((t) => (
              <li key={t.name} className="rounded-r2 border border-hairline bg-surface/40 px-2.5 py-1.5">
                <span className="font-mono text-[12.5px] text-fg">{t.name}</span>
                {t.params.length > 0 && <span className="mt-0.5 block truncate font-mono text-[11px] text-fg-muted">{t.params.join(", ")}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card icon="alert-triangle" title="Limites">
        <ul className="space-y-2">
          {spec.limits.map((l, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-fg">
              <Icon name="lock" size={14} className="mt-0.5 shrink-0 text-fg-muted" /> {l}
            </li>
          ))}
        </ul>
      </Card>

      <Card icon="shield-check" title="Políticas de aceite" note="Conferidas em código antes de qualquer passo rodar. O texto vem do Cérebro (20 Politicas)." wide>
        <Policies items={spec.policies} />
      </Card>

      <Card icon="layers" title="Skills do catálogo" note="Entram no prompt quando o pedido combina com elas." wide>
        {spec.skills.length === 0 ? (
          <p className="text-sm text-fg-muted">Nenhuma skill ligada a este agente.</p>
        ) : (
          <ul className="grid gap-2 md:grid-cols-2">
            {spec.skills.slice(0, 10).map((s) => (
              <li key={s.name} className="rounded-r2 border border-hairline px-3 py-2">
                <p className="text-sm font-medium text-fg">{s.name}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-fg-muted">{s.purpose}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="flex flex-wrap gap-2 xl:col-span-2">
        <Button icon="pen" onClick={() => onGo("instrucoes")}>
          Ajustar instruções
        </Button>
        <Button icon="brain" onClick={() => onGo("memoria")}>
          Editar memória
        </Button>
        <Button icon="link" onClick={() => onGo("contexto")}>
          Ligar notas
        </Button>
        <Button icon="code" onClick={() => onGo("codigo")}>
          Ver o código
        </Button>
      </div>
    </div>
  );
}

function Policies({ items }: { items: Spec["policies"] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!items.length) return <p className="text-sm text-fg-muted">Nenhuma política descrita no Cérebro.</p>;
  return (
    <ul className="divide-y divide-hairline overflow-hidden rounded-r3 border border-hairline">
      {items.map((p) => {
        const on = open === p.id;
        return (
          <li key={p.id}>
            <button type="button" aria-expanded={on} onClick={() => setOpen(on ? null : p.id)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-row-hover">
              <span className="w-[74px] shrink-0 rounded-[4px] bg-chip px-1.5 py-0.5 text-center font-mono text-[11px] text-fg">{p.id}</span>
              <span className="min-w-0 flex-1 truncate text-sm text-fg">{p.title}</span>
              {p.enforcement && <span className="hidden shrink-0 text-xs text-fg-muted sm:inline">{p.enforcement}</span>}
              <Icon name={on ? "chevron-up" : "chevron-down"} size={14} className="shrink-0 text-fg-muted" />
            </button>
            {on && <p className="animate-enter border-t border-hairline bg-surface/40 px-3 py-2.5 text-sm leading-relaxed text-fg">{p.rule || "Sem texto da regra."}</p>}
          </li>
        );
      })}
    </ul>
  );
}

function Card({ icon, title, note, wide, children }: { icon: IconName; title: string; note?: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <GlassPanel className={cn("p-5", wide && "xl:col-span-2")}>
      <h3 className="flex items-center gap-2 text-md font-semibold text-fg">
        <Icon name={icon} size={16} className="text-fg-muted" /> {title}
      </h3>
      {note && <p className="mt-1 text-sm text-fg-muted">{note}</p>}
      <div className="mt-4">{children}</div>
    </GlassPanel>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-r2 border border-hairline bg-surface/40 px-3 py-2">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className={cn("mt-0.5 text-sm text-fg", mono && "font-mono text-[12.5px]")}>{value || "—"}</dd>
    </div>
  );
}

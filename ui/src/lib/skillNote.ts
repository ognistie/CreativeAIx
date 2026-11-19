// Notas de skill do Cerebro (vault: 30 Skills/*.md), no formato que core/skills.py le:
//   frontmatter  tipo: skill · agentes: [CODE, DATA] · ativa_quando: palavra, palavra
//   > [!skill] O que faz \n > proposito
//   ## Como o agente aplica   - **Code Agent:** linha que vai para o prompt daquele agente
// Ligar uma skill a um agente = o agente entrar em `agentes` E ganhar uma linha em "Como o agente aplica" (sem a
// linha, core/skills.py ignora a skill para ele). Puro: testado em skillNote.test.ts.

export const SKILLS_DIR = "30 Skills";
/** Rotulo do agente nas linhas "**Rotulo:**" (o mesmo de core/skills.AGENT_LABEL; ExtCode usa o proprio id). */
export const AGENT_LABEL: Record<string, string> = {
  MAESTRO: "Maestro", WEB: "Web Agent", DESKTOP: "Desktop Agent", CODE: "Code Agent", DATA: "Data Agent",
  FILE: "File Agent", EXTCODE: "EXTCODE",
};

export function skillSlug(name: string): string {
  return name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
}

const listOf = (v: string) => v.replace(/^\[|\]$/g, "").split(",").map((x) => x.trim()).filter(Boolean);

/** Agentes do frontmatter (`agentes: [A, B]`). */
export function skillAgents(md: string): string[] {
  const fm = /^---\s*\n([\s\S]*?)\n---/.exec(md)?.[1] ?? "";
  const line = /^agentes:\s*(.*)$/m.exec(fm)?.[1] ?? "";
  return listOf(line).map((a) => a.toUpperCase());
}

/** O agente ja tem linha propria em "Como o agente aplica"? */
export function appliesTo(md: string, agent: string): boolean {
  const label = AGENT_LABEL[agent] ?? agent;
  const section = /^##\s+Como o agente aplica[^\n]*\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m.exec(md)?.[1] ?? "";
  return new RegExp(`^- \\*\\*${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:\\*\\*`, "mi").test(section);
}

/** Nota nova de skill para um agente. */
export function newSkillNote(o: { name: string; purpose: string; agent: string; line: string; triggers: string; today: string }): string {
  const label = AGENT_LABEL[o.agent] ?? o.agent;
  const triggers = o.triggers.split(",").map((t) => t.trim()).filter((t) => t.length >= 3).join(", ");
  return [
    "---", "tipo: skill", "origem: pessoal", `agentes: [${o.agent}]`, `ativa_quando: ${triggers}`, "tags: [skill]",
    "cssclasses: [skill-note]", `atualizado: ${o.today}`, "---",
    `# ${o.name.trim()}`, "", "> [!skill] O que faz", `> ${o.purpose.trim()}`, "",
    "## Como o agente aplica", `- **${label}:** ${o.line.trim()}`, "",
  ].join("\n");
}

/** Liga uma skill existente a mais um agente: entra em `agentes` e ganha a linha dele. Ja ligada: devolve igual. */
export function attachSkill(md: string, agent: string, line: string): string {
  const label = AGENT_LABEL[agent] ?? agent;
  let out = md;
  const agents = skillAgents(md);
  if (!agents.includes(agent)) {
    const fm = /^---\s*\n([\s\S]*?)\n---/.exec(out);
    if (fm && /^agentes:/m.test(fm[1]!)) {
      out = out.replace(/^agentes:\s*.*$/m, `agentes: [${[...agents, agent].join(", ")}]`);
    } else if (fm) {
      out = out.replace(/^---\s*\n/, `---\nagentes: [${agent}]\n`);
    }
  }
  if (appliesTo(out, agent)) return out;
  const bullet = `- **${label}:** ${line.trim()}`;
  const head = /^##\s+Como o agente aplica[^\n]*\n/m.exec(out);
  if (!head) return `${out.replace(/\s*$/, "")}\n\n## Como o agente aplica\n${bullet}\n`;
  // depois da ultima linha da secao (antes da proxima secao ##)
  const start = head.index + head[0].length;
  const next = out.slice(start).search(/^##\s/m);
  const end = next < 0 ? out.length : start + next;
  const body = out.slice(start, end).replace(/\s*$/, "");
  return `${out.slice(0, start)}${body ? body + "\n" : ""}${bullet}\n${next < 0 ? "" : "\n"}${out.slice(end)}`;
}

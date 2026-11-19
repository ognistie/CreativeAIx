import { describe, expect, it } from "vitest";
import { appliesTo, attachSkill, newSkillNote, skillAgents, skillSlug } from "./skillNote";

const NOTE = `---
tipo: skill
agentes: [DESKTOP, WEB]
ativa_quando: clica, abre
---
# ai-agent-engineer

> [!skill] O que faz
> Menor autonomia que resolve.

## Como o agente aplica
- **Desktop Agent:** Rotina pronta primeiro.
- **Web Agent:** Rota fixa quando basta.

## Regras
- Nunca chute.
`;

describe("skillNote", () => {
  it("le agentes e quem tem linha propria", () => {
    expect(skillAgents(NOTE)).toEqual(["DESKTOP", "WEB"]);
    expect(appliesTo(NOTE, "WEB")).toBe(true);
    expect(appliesTo(NOTE, "CODE")).toBe(false);
  });

  it("liga a skill a mais um agente sem mexer no resto", () => {
    const out = attachSkill(NOTE, "CODE", "Leia o arquivo antes de editar.");
    expect(skillAgents(out)).toEqual(["DESKTOP", "WEB", "CODE"]);
    expect(appliesTo(out, "CODE")).toBe(true);
    expect(out).toContain("- **Web Agent:** Rota fixa quando basta.\n- **Code Agent:** Leia o arquivo antes de editar.\n\n## Regras");
    expect(out).toContain("## Regras\n- Nunca chute.");
    expect(attachSkill(out, "CODE", "outra")).toBe(out);
  });

  it("nota nova no formato que core/skills.py le", () => {
    const md = newSkillNote({ name: "Revisar planilha", purpose: "Conferir totais.", agent: "DATA", line: "Some as colunas.", triggers: "planilha, ok, total", today: "2026-11-18" });
    expect(md).toMatch(/^---\ntipo: skill\n/);
    expect(skillAgents(md)).toEqual(["DATA"]);
    expect(appliesTo(md, "DATA")).toBe(true);
    expect(md).toContain("ativa_quando: planilha, total");
    expect(skillSlug("Revisão de Planilha!")).toBe("revisao-de-planilha");
  });
});

import { describe, expect, it } from "vitest";
import { parseSlash, slashMatches, withTool } from "./slash";

describe("comandos com barra", () => {
  it("abre o menu so com a palavra com barra no inicio", () => {
    expect(slashMatches("/").map((c) => c.tool)).toEqual(["claude", "codex"]);
    expect(slashMatches("/co").map((c) => c.tool)).toEqual(["codex"]);
    expect(slashMatches("/codex ")).toEqual([]);
    expect(slashMatches("crie /co")).toEqual([]);
  });

  it("reconhece o comando e o resto do pedido", () => {
    expect(parseSlash("/codex crie um site")).toEqual({ tool: "codex", rest: "crie um site" });
    expect(parseSlash("/Claude ")).toEqual({ tool: "claude", rest: "" });
    expect(parseSlash("/codexx")).toBeNull();
    expect(parseSlash("use o /codex")).toBeNull();
  });

  it("monta o pedido que o Maestro entende", () => {
    expect(withTool("crie um site", "codex")).toBe("crie um site com o Codex");
    expect(withTool("faça o README", "claude", "C:\\p\\x")).toBe("faça o README com o Claude Code na pasta C:\\p\\x");
    expect(withTool(" oi ", null)).toBe("oi");
  });
});

import { describe, expect, it } from "vitest";
import { applyAppearance } from "./appearance";

function fakeRoot() {
  const props: Record<string, string> = {};
  return {
    dataset: {} as Record<string, string>,
    style: { setProperty: (k: string, v: string) => (props[k] = v) },
    props,
  };
}

describe("applyAppearance", () => {
  it("maps the saved Harness appearance to html attributes", () => {
    const root = fakeRoot();
    applyAppearance({ mode: "claro", palette: "aurora", radius: "reto", motion: false, accent: "#AA3355" }, root as never);
    expect(root.dataset).toEqual({ theme: "claro", palette: "aurora", radius: "reto", motion: "off" });
    expect(root.props["--accent"]).toBe("#AA3355");
  });

  it("ignores values the QML would also reject", () => {
    const root = fakeRoot();
    applyAppearance({ mode: "neon", radius: "x", accent: "red; background: url(x)", palette: "a b" }, root as never);
    expect(root.dataset).toEqual({});
    expect(root.props).toEqual({});
  });
});

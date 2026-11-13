import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoreClient, CoreError, type SocketLike } from "./core";

class FakeSocket implements SocketLike {
  readyState = 0;
  sent: unknown[] = [];
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  constructor(readonly url: string) {}
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  // lado do servidor
  open() {
    this.readyState = 1;
    this.onopen?.({});
  }
  push(msg: unknown) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
  drop() {
    this.readyState = 3;
    this.onclose?.({ code: 1006 });
  }
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("CoreClient", () => {
  let sockets: FakeSocket[];
  let infos: number;
  let client: CoreClient;

  beforeEach(() => {
    sockets = [];
    infos = 0;
    client = new CoreClient({
      getInfo: async () => ({ port: 5000 + infos++, token: `tok${infos}` }),
      makeSocket: (url) => {
        const s = new FakeSocket(url);
        sockets.push(s);
        return s;
      },
      backoffMs: [1],
      callTimeoutMs: 200,
      openTimeoutMs: 200,
    });
  });

  afterEach(() => client.stop());

  async function connected(): Promise<FakeSocket> {
    client.start();
    await flush();
    const s = sockets.at(-1)!;
    s.open();
    s.push({ jsonrpc: "2.0", method: "hello", params: { protocol: 1 } });
    return s;
  }

  it("sends the token first and only then becomes open", async () => {
    const statuses: string[] = [];
    client.onStatus((s) => statuses.push(s));
    const s = await connected();
    expect(s.url).toBe("ws://127.0.0.1:5000");
    expect(s.sent[0]).toEqual({ token: "tok1" });
    expect(statuses).toEqual(["closed", "connecting", "open"]);
  });

  it("matches replies to calls by id", async () => {
    const s = await connected();
    const a = client.call("brainRead", "Notas/a.md");
    const b = client.call("uiSettings");
    await flush();
    const [ra, rb] = s.sent.slice(1) as Array<{ id: number; method: string; params: unknown[] }>;
    expect(ra).toMatchObject({ method: "brainRead", params: ["Notas/a.md"] });
    s.push({ jsonrpc: "2.0", id: rb!.id, result: { splash: true } });
    s.push({ jsonrpc: "2.0", id: ra!.id, error: { code: -32602, message: "tipo invalido" } });
    await expect(b).resolves.toEqual({ splash: true });
    await expect(a).rejects.toMatchObject({ code: -32602 });
  });

  it("delivers events to subscribers and lets them unsubscribe", async () => {
    const s = await connected();
    const got: unknown[] = [];
    const off = client.on("planReady", (p) => got.push(p));
    s.push({ jsonrpc: "2.0", method: "event", params: { name: "planReady", payload: { n: 1 } } });
    off();
    s.push({ jsonrpc: "2.0", method: "event", params: { name: "planReady", payload: { n: 2 } } });
    expect(got).toEqual([{ n: 1 }]);
  });

  it("a failing handler does not stop the others", async () => {
    const s = await connected();
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    const got: unknown[] = [];
    client.on("taskDone", () => {
      throw new Error("x");
    });
    client.on("taskDone", (p) => got.push(p));
    s.push({ jsonrpc: "2.0", method: "event", params: { name: "taskDone", payload: {} } });
    expect(got).toHaveLength(1);
    err.mockRestore();
  });

  it("calls made before the connection opens wait for it", async () => {
    client.start();
    const pending = client.call("uiSettings");
    await flush();
    const s = sockets[0]!;
    s.open();
    s.push({ jsonrpc: "2.0", method: "hello", params: { protocol: 1 } });
    await flush();
    const req = s.sent[1] as { id: number };
    s.push({ jsonrpc: "2.0", id: req.id, result: 1 });
    await expect(pending).resolves.toBe(1);
  });

  it("on drop, pending calls fail and it reconnects asking for fresh info", async () => {
    const s = await connected();
    const pending = client.call("loadHistory");
    await flush();
    s.drop();
    await expect(pending).rejects.toBeInstanceOf(CoreError);
    await new Promise((r) => setTimeout(r, 10));
    expect(sockets).toHaveLength(2);
    expect(sockets[1]!.url).toBe("ws://127.0.0.1:5001");
    sockets[1]!.open();
    expect(sockets[1]!.sent[0]).toEqual({ token: "tok2" });
  });

  it("times out a call with no reply", async () => {
    await connected();
    await expect(client.call("loadHistory")).rejects.toThrow(/sem resposta/);
  });
});

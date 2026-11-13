// Cliente do nucleo Python (desktop/server.py): JSON-RPC 2.0 por WebSocket local.
// Mesmo contrato do Bridge do QML: metodos = @Slots, eventos = Signals (ver contract.gen.ts).

import { PROTOCOL_VERSION, type EventName, type Events, type MethodName, type Methods } from "./contract.gen";

export type CoreStatus = "connecting" | "open" | "closed";

export interface CoreInfo {
  port: number;
  token: string;
}

/** O minimo de WebSocket que o cliente usa (o do navegador serve; os testes passam um falso). */
export interface SocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
}

export class CoreError extends Error {
  constructor(
    message: string,
    readonly code?: number,
  ) {
    super(message);
    this.name = "CoreError";
  }
}

interface Pending {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

type Handler = (payload: never) => void;

const OPEN = 1;

export interface CoreClientOptions {
  /** Porta e token do nucleo. Na casca Tauri: invoke("core_info"). Chamado de novo a cada reconexao. */
  getInfo: () => Promise<CoreInfo>;
  makeSocket?: (url: string) => SocketLike;
  callTimeoutMs?: number;
  openTimeoutMs?: number;
  backoffMs?: readonly number[];
}

export class CoreClient {
  private socket: SocketLike | null = null;
  private status: CoreStatus = "closed";
  private nextId = 1;
  private readonly pending = new Map<number, Pending>();
  private readonly handlers = new Map<string, Set<Handler>>();
  private readonly statusHandlers = new Set<(s: CoreStatus) => void>();
  private openWaiters: Array<() => void> = [];
  private stopped = true;
  private attempt = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly makeSocket: (url: string) => SocketLike;
  private readonly callTimeoutMs: number;
  private readonly openTimeoutMs: number;
  private readonly backoffMs: readonly number[];

  constructor(private readonly options: CoreClientOptions) {
    this.makeSocket = options.makeSocket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    this.callTimeoutMs = options.callTimeoutMs ?? 30_000;
    this.openTimeoutMs = options.openTimeoutMs ?? 15_000;
    this.backoffMs = options.backoffMs ?? [250, 500, 1000, 2000, 5000];
  }

  get state(): CoreStatus {
    return this.status;
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    void this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.socket?.close(1000, "fechando");
    this.socket = null;
    this.failPending(new CoreError("cliente encerrado"));
    this.setStatus("closed");
  }

  /** Chama um metodo do nucleo. Espera a conexao abrir (ate openTimeoutMs). */
  async call<M extends MethodName>(method: M, ...args: Methods[M][0]): Promise<Methods[M][1]> {
    await this.whenOpen();
    const socket = this.socket;
    if (!socket || socket.readyState !== OPEN) throw new CoreError("nucleo desconectado");
    const id = this.nextId++;
    return new Promise<Methods[M][1]>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new CoreError(`${method}: sem resposta do nucleo`));
      }, this.callTimeoutMs);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      socket.send(JSON.stringify({ jsonrpc: "2.0", id, method, params: args }));
    });
  }

  /** Assina um evento do nucleo. Devolve a funcao que cancela. */
  on<E extends EventName>(name: E, handler: (payload: Events[E]) => void): () => void {
    const set = this.handlers.get(name) ?? new Set<Handler>();
    this.handlers.set(name, set);
    set.add(handler as Handler);
    return () => {
      set.delete(handler as Handler);
    };
  }

  onStatus(handler: (s: CoreStatus) => void): () => void {
    this.statusHandlers.add(handler);
    handler(this.status);
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  // ── Conexao ──────────────────────────────────────────────────────
  private async connect(): Promise<void> {
    if (this.stopped) return;
    this.setStatus("connecting");
    let info: CoreInfo;
    try {
      info = await this.options.getInfo();
    } catch {
      this.scheduleRetry();
      return;
    }
    if (this.stopped) return;
    const socket = this.makeSocket(`ws://127.0.0.1:${info.port}`);
    this.socket = socket;
    let greeted = false;
    socket.onopen = () => socket.send(JSON.stringify({ token: info.token }));
    socket.onmessage = (ev) => {
      const msg = parse(ev.data);
      if (!msg) return;
      if (!greeted) {
        if (msg.method === "hello") {
          greeted = true;
          const protocol = (msg.params as { protocol?: number } | undefined)?.protocol;
          if (protocol !== PROTOCOL_VERSION) {
            console.warn(`[core] protocolo ${protocol}, esperado ${PROTOCOL_VERSION}`);
          }
          this.attempt = 0;
          this.setStatus("open");
          const waiters = this.openWaiters;
          this.openWaiters = [];
          waiters.forEach((w) => w());
        }
        return;
      }
      this.dispatch(msg);
    };
    socket.onerror = () => {};
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.failPending(new CoreError("conexao com o nucleo caiu"));
      this.setStatus("closed");
      this.scheduleRetry();
    };
  }

  private scheduleRetry(): void {
    if (this.stopped) return;
    const delay = this.backoffMs[Math.min(this.attempt, this.backoffMs.length - 1)] ?? 1000;
    this.attempt += 1;
    this.setStatus("connecting");
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.connect();
    }, delay);
  }

  private dispatch(msg: Message): void {
    if (typeof msg.id === "number" && this.pending.has(msg.id)) {
      const p = this.pending.get(msg.id)!;
      this.pending.delete(msg.id);
      clearTimeout(p.timer);
      if (msg.error) p.reject(new CoreError(msg.error.message, msg.error.code));
      else p.resolve(msg.result ?? null);
      return;
    }
    if (msg.method === "event") {
      const params = msg.params as { name?: string; payload?: unknown } | undefined;
      if (!params?.name) return;
      this.handlers.get(params.name)?.forEach((h) => {
        try {
          (h as (p: unknown) => void)(params.payload ?? null);
        } catch (err) {
          console.error(`[core] handler de ${params.name} falhou`, err);
        }
      });
    }
  }

  private whenOpen(): Promise<void> {
    if (this.status === "open" && this.socket?.readyState === OPEN) return Promise.resolve();
    if (this.stopped) return Promise.reject(new CoreError("cliente parado"));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.openWaiters = this.openWaiters.filter((w) => w !== done);
        reject(new CoreError("o nucleo nao respondeu a tempo"));
      }, this.openTimeoutMs);
      const done = () => {
        clearTimeout(timer);
        resolve();
      };
      this.openWaiters.push(done);
    });
  }

  private failPending(error: Error): void {
    this.pending.forEach((p) => {
      clearTimeout(p.timer);
      p.reject(error);
    });
    this.pending.clear();
  }

  private setStatus(status: CoreStatus): void {
    if (this.status === status) return;
    this.status = status;
    this.statusHandlers.forEach((h) => h(status));
  }
}

interface Message {
  id?: number | null;
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: { code: number; message: string };
}

function parse(data: unknown): Message | null {
  if (typeof data !== "string") return null;
  try {
    const value = JSON.parse(data) as unknown;
    return value && typeof value === "object" ? (value as Message) : null;
  } catch {
    return null;
  }
}

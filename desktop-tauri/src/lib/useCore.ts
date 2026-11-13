import { useEffect, useState } from "react";
import type { CoreStatus } from "./core";
import type { EventName, Events } from "./contract.gen";
import { core } from "./tauri";

export function useCoreStatus(): CoreStatus {
  const [status, setStatus] = useState<CoreStatus>(() => core().state);
  useEffect(() => core().onStatus(setStatus), []);
  return status;
}

/** Assina um evento do nucleo enquanto o componente estiver montado. */
export function useCoreEvent<E extends EventName>(name: E, handler: (payload: Events[E]) => void): void {
  useEffect(() => core().on(name, handler), [name, handler]);
}

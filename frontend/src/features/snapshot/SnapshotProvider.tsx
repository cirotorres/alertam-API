import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
} from "react";

import type { Pairing } from "../pairing/pairing";
import {
  type SnapshotFetcher,
  type SnapshotState,
  useSnapshotPolling,
} from "./useSnapshotPolling";

const SnapshotContext = createContext<SnapshotState | null>(null);

type SnapshotProviderProps = {
  pairing: Pairing;
  fetcher?: SnapshotFetcher;
  onAccessRevoked?: () => void;
  children: ReactNode;
};

type StaticSnapshotProviderProps = {
  state: SnapshotState;
  children: ReactNode;
};
export function SnapshotProvider({
  pairing,
  fetcher,
  onAccessRevoked,
  children,
}: SnapshotProviderProps) {
  const state = useSnapshotPolling(pairing, fetcher);

  useEffect(() => {
    if (state.status === "revoked") {
      onAccessRevoked?.();
    }
  }, [onAccessRevoked, state.status]);

  return (
    <SnapshotContext.Provider value={state}>
      {children}
    </SnapshotContext.Provider>
  );
}

export function StaticSnapshotProvider({
  state,
  children,
}: StaticSnapshotProviderProps) {
  return (
    <SnapshotContext.Provider value={state}>
      {children}
    </SnapshotContext.Provider>
  );
}

export function useSnapshotState(): SnapshotState {
  const state = useContext(SnapshotContext);
  if (state === null) {
    throw new Error("SnapshotProvider ausente.");
  }
  return state;
}

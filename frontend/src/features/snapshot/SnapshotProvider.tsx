import {
  createContext,
  type ReactNode,
  useContext,
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
  children: ReactNode;
};
export function SnapshotProvider({
  pairing,
  fetcher,
  children,
}: SnapshotProviderProps) {
  const state = useSnapshotPolling(pairing, fetcher);

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

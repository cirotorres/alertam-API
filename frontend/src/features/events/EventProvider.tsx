import {
  createContext,
  type ReactNode,
  useContext,
} from "react";

import type { EventFetcher, EventState } from "./useEventPolling";
import { useEventPolling } from "./useEventPolling";


const EventContext = createContext<EventState | null>(null);

type EventProviderProps = {
  sessionReady: boolean;
  fetcher?: EventFetcher;
  onAccessRevoked?: () => void;
  children: ReactNode;
};

export function EventProvider({
  sessionReady,
  fetcher,
  onAccessRevoked,
  children,
}: EventProviderProps) {
  const state = useEventPolling(
    sessionReady,
    fetcher,
    onAccessRevoked,
  );

  return (
    <EventContext.Provider value={state}>
      {children}
    </EventContext.Provider>
  );
}

export function useEventState(): EventState {
  const state = useContext(EventContext);
  if (state === null) {
    throw new Error("EventProvider ausente.");
  }
  return state;
}


type StaticEventProviderProps = {
  state: EventState;
  children: ReactNode;
};

export function StaticEventProvider({
  state,
  children,
}: StaticEventProviderProps) {
  return (
    <EventContext.Provider value={state}>
      {children}
    </EventContext.Provider>
  );
}

import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { ManeuverEventFeedResponse } from "../../api/contract";
import {
  EventProvider,
  useEventState,
} from "./EventProvider";


const EMPTY: ManeuverEventFeedResponse = {
  events: [],
  oldest_cursor: null,
  newest_cursor: null,
  has_more_before: false,
};

function Probe() {
  const state = useEventState();
  return <div>{state.status}:{state.events.length}</div>;
}

test("provider_waits_for_session_ready_before_fetching", async () => {
  const fetcher = vi.fn().mockResolvedValue(EMPTY);
  const { rerender } = render(
    <EventProvider
      sessionReady={false}
      fetcher={fetcher}
      onAccessRevoked={() => undefined}
    >
      <Probe />
    </EventProvider>,
  );

  expect(screen.getByText("idle:0")).toBeInTheDocument();
  expect(fetcher).not.toHaveBeenCalled();

  rerender(
    <EventProvider
      sessionReady
      fetcher={fetcher}
      onAccessRevoked={() => undefined}
    >
      <Probe />
    </EventProvider>,
  );

  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
});

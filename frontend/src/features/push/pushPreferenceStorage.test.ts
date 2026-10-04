import {
  PUSH_PREFERENCE_STORAGE_KEY,
  clearPushPreferenceSnapshot,
  loadPushPreferenceSnapshot,
  storePushPreferenceSnapshot,
} from "./pushPreferenceStorage";

const preferences = {
  confirmed: true,
  updated: false,
  completed: true,
  cancelled: false,
  anchored: false,
};

beforeEach(() => {
  localStorage.clear();
});

test("round trips non-sensitive push preference snapshot", () => {
  storePushPreferenceSnapshot({
    optedIn: true,
    preferences,
  });

  expect(loadPushPreferenceSnapshot()).toEqual({
    optedIn: true,
    preferences,
  });
});

test("invalid push preference snapshot is discarded", () => {
  localStorage.setItem(
    PUSH_PREFERENCE_STORAGE_KEY,
    JSON.stringify({
      optedIn: "yes",
      preferences,
    }),
  );

  expect(loadPushPreferenceSnapshot()).toBeNull();
  expect(localStorage.getItem(PUSH_PREFERENCE_STORAGE_KEY)).toBeNull();
});

test("clear removes push opt-in snapshot", () => {
  storePushPreferenceSnapshot({
    optedIn: true,
    preferences,
  });

  clearPushPreferenceSnapshot();

  expect(loadPushPreferenceSnapshot()).toBeNull();
});


test("legacy_four_flag_snapshot_defaults_anchorage_on", () => {
  localStorage.setItem(
    PUSH_PREFERENCE_STORAGE_KEY,
    JSON.stringify({
      optedIn: true,
      preferences: {
        confirmed: true,
        updated: false,
        completed: true,
        cancelled: false,
      },
    }),
  );

  expect(loadPushPreferenceSnapshot()).toEqual({
    optedIn: true,
    preferences: {
      confirmed: true,
      updated: false,
      completed: true,
      cancelled: false,
      anchored: true,
    },
  });
});

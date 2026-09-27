import { beforeEach, expect, test } from "vitest";

import type { VesselPhotoResponse } from "../../api/contract";
import {
  readVesselPhotoCache,
  writeVesselPhotoCache,
} from "./vesselPhotoCache";

const photo: VesselPhotoResponse = {
  imo: "1234567",
  photo_url: "https://upload.wikimedia.org/navio.jpg",
  author: "Autor",
  license: "CC BY-SA 4.0",
  source_url: "https://commons.wikimedia.org/wiki/File:Navio.jpg",
};

beforeEach(() => localStorage.clear());

test("reuses_cached_photo_before_expiration", () => {
  writeVesselPhotoCache(photo, 1_000);
  expect(readVesselPhotoCache("1234567", 2_000)).toEqual(photo);
});

test("expires_cached_photo_after_thirty_days", () => {
  writeVesselPhotoCache(photo, 1_000);
  const afterThirtyDays = 1_000 + 30 * 24 * 60 * 60 * 1_000 + 1;
  expect(readVesselPhotoCache("1234567", afterThirtyDays)).toBeNull();
});

import { detectDevicePlatform } from "./devicePlatform";

test.each([
  [
    { userAgent: "Mozilla/5.0 (iPhone)", platform: "iPhone", maxTouchPoints: 5 },
    "ios",
  ],
  [
    { userAgent: "Mozilla/5.0 (Linux; Android 15)", platform: "Linux armv8l", maxTouchPoints: 5 },
    "android",
  ],
  [
    { userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel", maxTouchPoints: 5 },
    "ios",
  ],
  [
    { userAgent: "Mozilla/5.0 (X11; Linux x86_64)", platform: "Linux x86_64", maxTouchPoints: 0 },
    "other",
  ],
])("detects coarse device platform", (navigatorLike, expected) => {
  expect(detectDevicePlatform(navigatorLike)).toBe(expected);
});

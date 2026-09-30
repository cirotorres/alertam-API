export type DevicePlatform = "ios" | "android" | "other";

export type NavigatorLike = {
  userAgent?: string;
  platform?: string;
  maxTouchPoints?: number;
};

export function detectDevicePlatform(
  navigatorLike: NavigatorLike = navigator,
): DevicePlatform {
  const userAgent = navigatorLike.userAgent ?? "";
  const platform = navigatorLike.platform ?? "";
  const maxTouchPoints = navigatorLike.maxTouchPoints ?? 0;

  if (/android/i.test(userAgent)) {
    return "android";
  }

  if (
    /iphone|ipad|ipod/i.test(userAgent) ||
    /iphone|ipad|ipod/i.test(platform) ||
    (platform === "MacIntel" && maxTouchPoints > 1)
  ) {
    return "ios";
  }

  return "other";
}

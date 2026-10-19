import { toQueryString } from "./bounds";
import type { Bounds, MapLocation } from "./types";

export async function fetchLocations(
  bounds: Bounds,
  signal?: AbortSignal
): Promise<MapLocation[]> {
  const res = await fetch(`/api/locations?${toQueryString(bounds)}`, {
    signal,
  });
  if (!res.ok) {
    throw new Error(`加载位置数据失败（HTTP ${res.status}）`);
  }
  return res.json();
}

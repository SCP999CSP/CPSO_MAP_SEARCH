import type { Bounds } from "./types";

/** 约 1m 精度；地图微小抖动不会产生新请求 */
const PRECISION = 5;

function round(value: number): number {
  return Number(value.toFixed(PRECISION));
}

export function fromLatLngBounds(bounds: google.maps.LatLngBounds): Bounds {
  const ne = bounds.getNorthEast();
  const sw = bounds.getSouthWest();
  return roundBounds({
    north: ne.lat(),
    south: sw.lat(),
    east: ne.lng(),
    west: sw.lng(),
  });
}

export function roundBounds(b: Bounds): Bounds {
  return {
    north: round(b.north),
    south: round(b.south),
    east: round(b.east),
    west: round(b.west),
  };
}

export function boundsKey(b: Bounds): string {
  const r = roundBounds(b);
  return `${r.north},${r.south},${r.east},${r.west}`;
}

export function toQueryString(b: Bounds): string {
  return new URLSearchParams({
    north: String(b.north),
    south: String(b.south),
    east: String(b.east),
    west: String(b.west),
  }).toString();
}

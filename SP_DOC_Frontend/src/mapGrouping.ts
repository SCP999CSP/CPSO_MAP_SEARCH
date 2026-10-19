import type { MapLocation } from "./types";

/** 网格大小（度），约 45m（多伦多纬度），网格内点位合并为一个数字标记 */
const GRID_SIZE = 0.0004;

export function gridKey(lat: number, lng: number): string {
  const cellLat = Math.floor(lat / GRID_SIZE) * GRID_SIZE;
  const cellLng = Math.floor(lng / GRID_SIZE) * GRID_SIZE;
  return `${cellLat.toFixed(6)},${cellLng.toFixed(6)}`;
}

export type LocationGroup = {
  key: string;
  latitude: number;
  longitude: number;
  records: MapLocation[];
};

export function groupByCoordinates(records: MapLocation[]): LocationGroup[] {
  const map = new Map<string, MapLocation[]>();
  for (const r of records) {
    const k = gridKey(r.latitude, r.longitude);
    const list = map.get(k);
    if (list) list.push(r);
    else map.set(k, [r]);
  }
  return [...map.entries()].map(([key, recs]) => ({
    key,
    latitude: recs.reduce((s, r) => s + r.latitude, 0) / recs.length,
    longitude: recs.reduce((s, r) => s + r.longitude, 0) / recs.length,
    records: recs,
  }));
}

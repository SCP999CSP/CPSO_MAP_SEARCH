import type { DoctorAddressRecord } from "./types";
import { KNOWN_LOCATIONS } from "./knownLocations";

/**
 * 网格大小（度），约 55m，用于将一定范围内的点位合并为一个簇
 * 0.0005° ≈ 55m（多伦多纬度）
 */
const GRID_SIZE = 0.0004;

/** 同一坐标（约 1m 内）视为同一点，用于精确匹配 */
const PRECISION = 5;

export function coordKey(lat: number, lng: number): string {
  return `${lat.toFixed(PRECISION)},${lng.toFixed(PRECISION)}`;
}

/** 网格 key，用于将邻近点位合并 */
export function gridKey(lat: number, lng: number): string {
  const cellLat = Math.floor(lat / GRID_SIZE) * GRID_SIZE;
  const cellLng = Math.floor(lng / GRID_SIZE) * GRID_SIZE;
  return `${cellLat.toFixed(6)},${cellLng.toFixed(6)}`;
}

export type LocationGroup = {
  key: string;
  latitude: number;
  longitude: number;
  records: DoctorAddressRecord[];
  /** 已知机构名称（覆盖默认显示） */
  displayLabel?: string;
  /** 已知机构医生数（覆盖 records.length） */
  displayCount?: number;
  /** 仅已知机构，无导出记录 */
  isKnownOnly?: boolean;
};

export function groupByCoordinates(
  records: DoctorAddressRecord[]
): LocationGroup[] {
  const map = new Map<string, DoctorAddressRecord[]>();
  for (const r of records) {
    const k = gridKey(r.latitude, r.longitude);
    const list = map.get(k);
    if (list) list.push(r);
    else map.set(k, [r]);
  }
  const groups: LocationGroup[] = [...map.entries()].map(([key, recs]) => ({
    key,
    latitude: recs.reduce((s, r) => s + r.latitude, 0) / recs.length,
    longitude: recs.reduce((s, r) => s + r.longitude, 0) / recs.length,
    records: recs,
  }));

  // 合并已知机构：匹配网格的增强显示，无匹配的补充为单独点位
  for (const kl of KNOWN_LOCATIONS) {
    const k = gridKey(kl.lat, kl.lng);
    const g = groups.find((gr) => gr.key === k);
    if (g) {
      g.displayLabel = kl.label;
      g.displayCount = Math.max(g.records.length, kl.count);
    } else {
      groups.push({
        key: `known-${k}`,
        latitude: kl.lat,
        longitude: kl.lng,
        records: [],
        displayLabel: kl.label,
        displayCount: kl.count,
        isKnownOnly: true,
      });
    }
  }
  return groups;
}

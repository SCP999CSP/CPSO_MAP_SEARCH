import type { DoctorAddressRecord } from "./types";
import { KNOWN_LOCATIONS } from "./knownLocations";

/** 同一坐标（约 1m 内）视为同一点，避免重叠圆点看起来「丢数据」 */
const PRECISION = 5;

export function coordKey(lat: number, lng: number): string {
  return `${lat.toFixed(PRECISION)},${lng.toFixed(PRECISION)}`;
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
    const k = coordKey(r.latitude, r.longitude);
    const list = map.get(k);
    if (list) list.push(r);
    else map.set(k, [r]);
  }
  const groups: LocationGroup[] = [...map.entries()].map(([key, recs]) => ({
    key,
    latitude: recs[0].latitude,
    longitude: recs[0].longitude,
    records: recs,
  }));

  // 合并已知机构：匹配坐标的增强显示，无匹配的补充为单独点位
  for (const kl of KNOWN_LOCATIONS) {
    const k = coordKey(kl.lat, kl.lng);
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

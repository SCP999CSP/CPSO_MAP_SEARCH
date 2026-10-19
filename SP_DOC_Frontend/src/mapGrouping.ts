import {
  doctorCategory,
  isListedSpecialty,
  SPECIALTIES,
  type Specialty,
} from "./specialty";
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

/** 同一网格里按专科拆开的点；多专科、未分类不显示 */
export type SpecialtyMarker = {
  key: string;
  latitude: number;
  longitude: number;
  specialty: Specialty;
  /** 同一地点里从左到右的序号 */
  slot: number;
  slotCount: number;
  records: MapLocation[];
};

export function markersBySpecialty(records: MapLocation[]): SpecialtyMarker[] {
  const visible = records.filter((r) =>
    isListedSpecialty(doctorCategory(r.specialties))
  );
  const markers: SpecialtyMarker[] = [];
  for (const cell of groupByCoordinates(visible)) {
    const bySpec = new Map<Specialty, MapLocation[]>();
    for (const r of cell.records) {
      const category = doctorCategory(r.specialties);
      if (!isListedSpecialty(category)) continue;
      const list = bySpec.get(category);
      if (list) list.push(r);
      else bySpec.set(category, [r]);
    }
    const specs = SPECIALTIES.filter((s) => bySpec.has(s));
    specs.forEach((specialty, slot) => {
      const recs = bySpec.get(specialty);
      if (!recs) return;
      markers.push({
        key: `${cell.key}:${specialty}`,
        latitude: cell.latitude,
        longitude: cell.longitude,
        specialty,
        slot,
        slotCount: specs.length,
        records: recs,
      });
    });
  }
  return markers;
}

/** 同一地点的不同专科并排，放大后能分开，缩小时不甩出网格 */
const SLOT_SPACING_PX = 28;
const MAX_SLOT_SPACING_M = 18;

export function slotPosition(
  lat: number,
  lng: number,
  slot: number,
  slotCount: number,
  zoom: number
): { lat: number; lng: number } {
  if (slotCount <= 1) return { lat, lng };
  const metersPerPx =
    (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
  const spacingM = Math.min(SLOT_SPACING_PX * metersPerPx, MAX_SLOT_SPACING_M);
  const metersPerDegLng = 111320 * Math.cos((lat * Math.PI) / 180);
  const dx = (slot - (slotCount - 1) / 2) * spacingM;
  return { lat, lng: lng + dx / metersPerDegLng };
}

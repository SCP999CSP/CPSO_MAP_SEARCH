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

/** 达到该级别后，同一地点的不同专科才拆成并排的点 */
export const SPLIT_ZOOM = 16;

/** 拆开后的点并排，间距随缩放变大，但不超过约一个街区 */
const SLOT_SPACING_PX = 32;
const MAX_SLOT_SPACING_M = 40;

export type SiteMarker = {
  kind: "site";
  key: string;
  latitude: number;
  longitude: number;
  records: MapLocation[];
};

export type DisplayMarker = ({ kind: "specialty" } & SpecialtyMarker) | SiteMarker;

/** 未放大时，多种专科合成一个点；放大到 SPLIT_ZOOM 后再按专科分开 */
export function markersForZoom(
  markers: SpecialtyMarker[],
  zoom: number
): DisplayMarker[] {
  if (zoom >= SPLIT_ZOOM) {
    return markers.map((marker) => ({ kind: "specialty", ...marker }));
  }

  const sites = new Map<string, SpecialtyMarker[]>();
  for (const marker of markers) {
    if (marker.slotCount <= 1) continue;
    const siteKey = marker.key.slice(0, marker.key.lastIndexOf(":"));
    const list = sites.get(siteKey);
    if (list) list.push(marker);
    else sites.set(siteKey, [marker]);
  }

  const out: DisplayMarker[] = [];
  const emitted = new Set<string>();
  for (const marker of markers) {
    if (marker.slotCount <= 1) {
      out.push({ kind: "specialty", ...marker });
      continue;
    }
    const siteKey = marker.key.slice(0, marker.key.lastIndexOf(":"));
    if (emitted.has(siteKey)) continue;
    emitted.add(siteKey);
    const parts = sites.get(siteKey) ?? [];
    out.push({
      kind: "site",
      key: siteKey,
      latitude: parts[0]?.latitude ?? marker.latitude,
      longitude: parts[0]?.longitude ?? marker.longitude,
      records: parts.flatMap((part) => part.records),
    });
  }
  return out;
}

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

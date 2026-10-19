import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  GoogleMap,
  InfoWindowF,
  MarkerF,
  useJsApiLoader,
} from "@react-google-maps/api";
import { fetchLocations } from "./api";
import { boundsKey, fromLatLngBounds } from "./bounds";
import { markersBySpecialty, markersForZoom, slotPosition } from "./mapGrouping";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  matchSpecialties,
  SPECIALTIES,
  type Specialty,
} from "./specialty";
import type { MapLocation } from "./types";

const TORONTO_CENTER = { lat: 43.65, lng: -79.38 };
const MAP_CONTAINER_STYLE = { width: "100%", height: "100%" };
/** 与后端 MAX_LOCATIONS 一致 */
const MAX_LOCATIONS = 1000;

const MAP_OPTIONS: google.maps.MapOptions = {
  minZoom: 9,
  restriction: {
    latLngBounds: { north: 44.5, south: 43.0, east: -78.5, west: -80.5 },
    strictBounds: false,
  },
  styles: [
    {
      featureType: "poi.business",
      stylers: [{ visibility: "off" }],
    },
    {
      featureType: "poi.attraction",
      stylers: [{ visibility: "off" }],
    },
    {
      featureType: "poi.park",
      stylers: [{ visibility: "off" }],
    },
    {
      featureType: "transit",
      elementType: "labels.icon",
      stylers: [{ visibility: "off" }],
    },
  ],
};

const SITE_COLOR = "#334155";

function getSiteIcon() {
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: 18,
    fillColor: SITE_COLOR,
    fillOpacity: 1,
    strokeColor: "white",
    strokeWeight: 2,
  };
}

function getIcon(category: Specialty, isGroup: boolean) {
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: isGroup ? 18 : 10,
    fillColor: CATEGORY_COLORS[category],
    fillOpacity: isGroup ? 1 : 0.9,
    strokeColor: "white",
    strokeWeight: 2,
  };
}

function getDoctorUrl(cpsoNumber: string): string {
  return `https://register.cpso.on.ca/physician-info/?cpsonum=${encodeURIComponent(cpsoNumber)}`;
}

function openDoctor(cpsoNumber: string) {
  window.open(getDoctorUrl(cpsoNumber), "_blank", "noopener,noreferrer");
}

function formatAddress(r: MapLocation): string | null {
  if (r.full_address) return r.full_address;
  const parts = [r.city, r.province, r.postal_code].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

function SpecialtyLine({ r }: { r: MapLocation }) {
  const matched = matchSpecialties(r.specialties);
  if (matched.length !== 1) return null;
  const color = CATEGORY_COLORS[matched[0]];
  return (
    <div style={{ fontSize: 15, lineHeight: 1.45, color, fontWeight: 600 }}>
      {matched.join(" | ")}
    </div>
  );
}

function DoctorProfileFields({ r }: { r: MapLocation }) {
  const lineStyle = { fontSize: 15, lineHeight: 1.45 } as const;
  return (
    <>
      {r.gender && <div style={lineStyle}>Gender: {r.gender}</div>}
      {r.medical_school && (
        <div style={lineStyle}>Medical school: {r.medical_school}</div>
      )}
      {r.languages_spoken && (
        <div style={lineStyle}>Languages: {r.languages_spoken}</div>
      )}
      {r.graduate_data && (
        <div style={lineStyle}>Graduated: {r.graduate_data}</div>
      )}
    </>
  );
}

function ContactFields({ r }: { r: MapLocation }) {
  const address = formatAddress(r);
  return (
    <>
      {r.phone && (
        <div style={{ fontSize: 15, marginTop: 4 }}>Phone: {r.phone}</div>
      )}
      {r.fax && <div style={{ fontSize: 15, marginTop: 4 }}>Fax: {r.fax}</div>}
      {address && (
        <div style={{ fontSize: 15, marginTop: 4, color: "#4b5563" }}>
          {address}
        </div>
      )}
    </>
  );
}

export default function MapPage() {
  const mapRef = useRef<google.maps.Map | null>(null);
  const lastKeyRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [locations, setLocations] = useState<MapLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [zoom, setZoom] = useState(11);

  const { isLoaded, loadError } = useJsApiLoader({
    id: "google-map-script",
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? "",
  });

  const groups = useMemo(() => markersBySpecialty(locations), [locations]);
  const displayMarkers = useMemo(
    () => markersForZoom(groups, zoom),
    [groups, zoom]
  );

  const shownCount = useMemo(
    () => groups.reduce((sum, g) => sum + g.records.length, 0),
    [groups]
  );

  const categoryCounts = useMemo(() => {
    const counts = new Map<Specialty, number>();
    for (const g of groups) {
      counts.set(g.specialty, (counts.get(g.specialty) ?? 0) + g.records.length);
    }
    return counts;
  }, [groups]);

  const onIdle = useCallback(() => {
    const latLngBounds = mapRef.current?.getBounds();
    if (!latLngBounds) return;

    const z = mapRef.current?.getZoom();
    if (typeof z === "number") setZoom(z);

    const bounds = fromLatLngBounds(latLngBounds);
    const key = boundsKey(bounds);
    if (key === lastKeyRef.current) return;
    lastKeyRef.current = key;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);

    fetchLocations(bounds, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setLocations(data);
        setError(null);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        lastKeyRef.current = null;
        setError(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => {
        if (abortRef.current === controller) setLoading(false);
      });
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
  }, []);

  const onUnmount = useCallback(() => {
    mapRef.current = null;
  }, []);

  if (loadError) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#b91c1c" }}>
        <h2>Google 地图加载失败</h2>
        <p>请检查 API Key 或网络连接</p>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        正在加载 Google 地图…
      </div>
    );
  }

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <div
        style={{
          position: "absolute",
          top: 8,
          left: 8,
          zIndex: 1000,
          background: "rgba(255,255,255,0.92)",
          padding: "10px 16px",
          borderRadius: 8,
          fontSize: 16,
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
          maxWidth: 360,
        }}
      >
        <div>
          当前范围 <strong>{shownCount}</strong> 条地址 · 地图{" "}
          <strong>{displayMarkers.length}</strong> 个点位
          {loading && <span style={{ marginLeft: 8 }}>加载中…</span>}
        </div>
        {locations.length >= MAX_LOCATIONS && (
          <div style={{ color: "#1d4ed8", fontSize: 14 }}>
            已达 {MAX_LOCATIONS} 条上限，放大查看更多
          </div>
        )}
        {error && (
          <div style={{ color: "#b91c1c", marginTop: 4 }}>{error}</div>
        )}
        <div style={{ marginTop: 6, color: "#4b5563", fontSize: 13 }}>
          同一地点有多种专科时先合成一个点，放大后分开。
        </div>
        <div
          style={{
            marginTop: 8,
            display: "grid",
            gridTemplateColumns: "auto 1fr auto",
            columnGap: 8,
            rowGap: 2,
            fontSize: 14,
            alignItems: "center",
          }}
        >
          {SPECIALTIES.map((c) => (
            <LegendRow
              key={c}
              color={CATEGORY_COLORS[c]}
              label={CATEGORY_LABELS[c]}
              count={categoryCounts.get(c) ?? 0}
            />
          ))}
        </div>
      </div>
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={TORONTO_CENTER}
        zoom={11}
        options={MAP_OPTIONS}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onIdle={onIdle}
        onZoomChanged={() => {
          const z = mapRef.current?.getZoom();
          if (typeof z === "number") setZoom(z);
        }}
        onClick={() => setSelectedKey(null)}
      >
        {displayMarkers.map((g) => {
          if (g.kind === "site") {
            const n = g.records.length;
            const isSelected = selectedKey === g.key;
            const toggle = () => setSelectedKey(isSelected ? null : g.key);
            return (
              <MarkerF
                key={g.key}
                position={{ lat: g.latitude, lng: g.longitude }}
                icon={getSiteIcon()}
                label={{
                  text: String(n),
                  color: "white",
                  fontSize: "12px",
                  fontWeight: "bold",
                }}
                title={`同一地点 ${n} 位医生\n放大后按专科分开`}
                onClick={toggle}
              >
                {isSelected && (
                  <InfoWindowF onCloseClick={() => setSelectedKey(null)}>
                    <DoctorList
                      title={`同一地点 · ${n} 位`}
                      note="放大后按专科分开显示。"
                      records={g.records}
                    />
                  </InfoWindowF>
                )}
              </MarkerF>
            );
          }

          const pos = slotPosition(
            g.latitude,
            g.longitude,
            g.slot,
            g.slotCount,
            zoom
          );
          const isSelected = selectedKey === g.key;
          const toggle = () => setSelectedKey(isSelected ? null : g.key);
          const category = g.specialty;

          if (g.records.length === 1) {
            const r = g.records[0];
            return (
              <MarkerF
                key={g.key}
                position={pos}
                icon={getIcon(category, false)}
                title={`${r.full_name}\n点击查看详情`}
                onClick={toggle}
              >
                {isSelected && (
                  <InfoWindowF onCloseClick={() => setSelectedKey(null)}>
                    <div
                      style={{ fontSize: 16, lineHeight: 1.5, maxWidth: 320 }}
                    >
                      <strong style={{ fontSize: 17 }}>{r.full_name}</strong>
                      <div style={{ marginTop: 6, fontSize: 15 }}>
                        CPSO: {r.cpso_number}
                      </div>
                      <SpecialtyLine r={r} />
                      <DoctorProfileFields r={r} />
                      <ContactFields r={r} />
                      <button
                        type="button"
                        onClick={() => openDoctor(r.cpso_number)}
                        style={{
                          marginTop: 12,
                          cursor: "pointer",
                          fontSize: 15,
                          padding: "6px 12px",
                        }}
                      >
                        查看医生详情
                      </button>
                    </div>
                  </InfoWindowF>
                )}
              </MarkerF>
            );
          }

          const n = g.records.length;
          return (
            <MarkerF
              key={g.key}
              position={pos}
              icon={getIcon(category, true)}
              label={{
                text: String(n),
                color: "white",
                fontSize: "12px",
                fontWeight: "bold",
              }}
              title={`${CATEGORY_LABELS[category]} ${n} 位\n${g.records
                .slice(0, 3)
                .map((r) => r.full_name)
                .join("；")}${n > 3 ? "…" : ""}\n点击圆点打开列表`}
              onClick={toggle}
            >
              {isSelected && (
                <InfoWindowF onCloseClick={() => setSelectedKey(null)}>
                  <DoctorList
                    title={`${CATEGORY_LABELS[category]} · ${n} 位`}
                    note="约 45m 范围内同专科的地址已合并。"
                    records={g.records}
                  />
                </InfoWindowF>
              )}
            </MarkerF>
          );
        })}
      </GoogleMap>
    </div>
  );
}

function DoctorList({
  title,
  note,
  records,
}: {
  title: string;
  note: string;
  records: MapLocation[];
}) {
  return (
    <div
      style={{
        maxHeight: 320,
        overflowY: "auto",
        minWidth: 260,
        textAlign: "left",
        fontSize: 15,
        lineHeight: 1.45,
      }}
    >
      <strong style={{ fontSize: 17 }}>{title}</strong>
      <p style={{ fontSize: 14, margin: "8px 0 12px", color: "#4b5563" }}>
        {note}
      </p>
      {records.map((r) => (
        <div
          key={r.id}
          style={{ borderTop: "1px solid #e5e7eb", padding: "10px 0" }}
        >
          <div style={{ fontWeight: 600, fontSize: 16 }}>{r.full_name}</div>
          <div style={{ fontSize: 15, marginTop: 4 }}>CPSO: {r.cpso_number}</div>
          <SpecialtyLine r={r} />
          <DoctorProfileFields r={r} />
          <ContactFields r={r} />
          <button
            type="button"
            onClick={() => openDoctor(r.cpso_number)}
            style={{
              marginTop: 8,
              cursor: "pointer",
              fontSize: 15,
              padding: "5px 10px",
            }}
          >
            查看详情
          </button>
        </div>
      ))}
    </div>
  );
}

function LegendRow({
  color,
  label,
  count,
}: {
  color: string;
  label: string;
  count?: number;
}) {
  return (
    <>
      <span
        style={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          background: color,
          border: "1px solid white",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.15)",
        }}
      />
      <span style={{ textAlign: "left" }}>{label}</span>
      <span style={{ textAlign: "right", color: "#4b5563" }}>
        {count ?? ""}
      </span>
    </>
  );
}

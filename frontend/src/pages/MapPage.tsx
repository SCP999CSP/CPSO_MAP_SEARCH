import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  GoogleMap,
  useJsApiLoader,
  Marker,
  InfoWindow,
} from "@react-google-maps/api";
import { fetchDoctorAddresses } from "../data";
import type { DoctorAddressRecord } from "../types";
import { groupByCoordinates } from "../mapGrouping";

const TORONTO_CENTER = { lat: 43.65, lng: -79.38 };
const MAP_CONTAINER_STYLE = { width: "100%", height: "100%" };

function getClusterIcon() {
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: 18,
    fillColor: "#1d4ed8",
    fillOpacity: 1,
    strokeColor: "white",
    strokeWeight: 2,
  };
}

function getSingleIcon() {
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: 10,
    fillColor: "#3b82f6",
    fillOpacity: 0.9,
    strokeColor: "#2563eb",
    strokeWeight: 2,
  };
}

function getSearchResultIcon() {
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: 14,
    fillColor: "#dc2626",
    fillOpacity: 0.9,
    strokeColor: "#fff",
    strokeWeight: 3,
  };
}

function getDoctorUrl(cpsoNumber: string): string {
  return `https://register.cpso.on.ca/physician-info/?cpsonum=${encodeURIComponent(cpsoNumber)}`;
}

const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
const SEARCH_USER_AGENT = "CPSO-Map-Search/1.0";

interface GeocodeResult {
  lat: number;
  lng: number;
  displayName: string;
}

async function geocodeAddress(query: string): Promise<GeocodeResult | null> {
  const params = new URLSearchParams({
    q: query,
    format: "json",
    limit: "1",
  });
  const res = await fetch(`${NOMINATIM_URL}?${params}`, {
    headers: { "User-Agent": SEARCH_USER_AGENT },
  });
  if (!res.ok) return null;
  const data = await res.json();
  if (!Array.isArray(data) || data.length === 0) return null;
  const item = data[0];
  return {
    lat: parseFloat(item.lat),
    lng: parseFloat(item.lon),
    displayName: item.display_name ?? query,
  };
}

export default function MapPage() {
  const mapRef = useRef<google.maps.Map | null>(null);
  const [records, setRecords] = useState<DoctorAddressRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<GeocodeResult | null>(null);

  const { isLoaded, loadError } = useJsApiLoader({
    id: "google-map-script",
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? "",
  });

  const groups = useMemo(() => groupByCoordinates(records), [records]);

  const handleMarkerClick = useCallback((r: DoctorAddressRecord) => {
    window.open(getDoctorUrl(r.cpso_number), "_blank", "noopener,noreferrer");
  }, []);

  const handleSearch = useCallback(async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setSearchLoading(true);
    setSearchError(null);
    setSearchResult(null);
    try {
      const result = await geocodeAddress(q);
      if (result) {
        setSearchResult(result);
        if (mapRef.current) {
          mapRef.current.panTo({ lat: result.lat, lng: result.lng });
          mapRef.current.setZoom(15);
        }
      } else {
        setSearchError("未找到该地址");
      }
    } catch {
      setSearchError("搜索失败，请稍后重试");
    } finally {
      setSearchLoading(false);
    }
  }, [searchQuery]);

  const onMapLoad = useCallback(
    (map: google.maps.Map) => {
      mapRef.current = map;
      if (groups.length === 0) return;
      const bounds = new google.maps.LatLngBounds();
      for (const g of groups) {
        bounds.extend({ lat: g.latitude, lng: g.longitude });
      }
      if (groups.length === 1) {
        map.setCenter({ lat: groups[0].latitude, lng: groups[0].longitude });
        map.setZoom(12);
      } else {
        map.fitBounds(bounds, { top: 48, right: 48, bottom: 48, left: 48 });
        const listener = google.maps.event.addListener(map, "idle", () => {
          const z = map.getZoom();
          if (z && z > 15) map.setZoom(15);
          google.maps.event.removeListener(listener);
        });
      }
    },
    [groups]
  );

  const onMapUnmount = useCallback(() => {
    mapRef.current = null;
  }, []);

  useEffect(() => {
    fetchDoctorAddresses()
      .then(setRecords)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (mapRef.current && groups.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      for (const g of groups) {
        bounds.extend({ lat: g.latitude, lng: g.longitude });
      }
      if (groups.length === 1) {
        mapRef.current.setCenter({
          lat: groups[0].latitude,
          lng: groups[0].longitude,
        });
        mapRef.current.setZoom(12);
      } else {
        mapRef.current.fitBounds(bounds, {
          top: 48,
          right: 48,
          bottom: 48,
          left: 48,
        });
      }
    }
  }, [groups]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        正在加载医生数据…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#b91c1c" }}>
        <h2>数据加载失败</h2>
        <p>{error}</p>
        <p style={{ marginTop: 16, fontSize: "0.9em" }}>
          请先在 CPSO_WEB_DATA 目录运行：
          <br />
          <code>python3 export_to_json.py</code>
        </p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#b91c1c" }}>
        <h2>Google 地图加载失败</h2>
        <p>请检查 API Key 或网络连接</p>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        暂无带经纬度的医生地址数据。请运行 geocode.py 后重新导出。
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
    <div style={{ height: "100vh", width: "100%", position: "relative" }}>
      <div
        style={{
          position: "absolute",
          top: 8,
          left: 8,
          right: 8,
          zIndex: 1000,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
        }}
      >
        <div
          style={{
            background: "rgba(255,255,255,0.92)",
            padding: "8px 14px",
            borderRadius: 8,
            fontSize: 14,
            boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
          }}
        >
          已加载 <strong>{records.length}</strong> 条地址 · 地图{" "}
          <strong>{groups.length}</strong> 个点位
          {groups.length < records.length && (
            <span style={{ color: "#1d4ed8" }}>
              （多笔在同一坐标已合并为数字标记）
            </span>
          )}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "rgba(255,255,255,0.92)",
            padding: "6px 10px",
            borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
          }}
        >
          <input
            type="text"
            placeholder="输入地址搜索，如 Toronto ON 或邮编 M5A 4P5"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSearchError(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            style={{
              width: 260,
              padding: "6px 10px",
              border: "1px solid #e5e7eb",
              borderRadius: 6,
              fontSize: 14,
              outline: "none",
            }}
          />
          <button
            type="button"
            onClick={handleSearch}
            disabled={searchLoading || !searchQuery.trim()}
            style={{
              padding: "6px 14px",
              background: "#1d4ed8",
              color: "white",
              border: "none",
              borderRadius: 6,
              cursor: searchLoading ? "wait" : "pointer",
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            {searchLoading ? "搜索中…" : "定位"}
          </button>
          {searchError && (
            <span style={{ fontSize: 13, color: "#b91c1c" }}>{searchError}</span>
          )}
        </div>
      </div>
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={TORONTO_CENTER}
        zoom={10}
        onLoad={onMapLoad}
        onUnmount={onMapUnmount}
      >
        {groups.map((g) => {
          const n = g.displayCount ?? g.records.length;
          const first = g.records[0];
          const label = g.displayLabel;
          const isKnownOnly = g.isKnownOnly;
          const pos = { lat: g.latitude, lng: g.longitude };

          const markerLabel =
            g.displayCount && g.displayCount > g.records.length
              ? `${g.displayCount}+`
              : String(n);

          const tooltipText =
            isKnownOnly && g.records.length === 0
              ? `${label}\n${n}+ 位医生`
              : g.records.length === 1
                ? `${label ?? first.full_name}\n${first.phone ? `Phone: ${first.phone}\n` : ""}${first.fax ? `Fax: ${first.fax}` : ""}\n点击查看详情`
                : `${label ?? "同一地址"} ${n} 位医生\n${g.records.slice(0, 3).map((r) => r.full_name).join("；")}${g.records.length > 3 ? "…" : ""}\n点击圆点打开列表`;

          const isSelected = selectedKey === g.key;

          if (isKnownOnly && g.records.length === 0) {
            return (
              <Marker
                key={g.key}
                position={pos}
                icon={getClusterIcon()}
                label={{
                  text: markerLabel,
                  color: "white",
                  fontSize: "12px",
                  fontWeight: "bold",
                }}
                title={tooltipText}
                onClick={() => setSelectedKey(isSelected ? null : g.key)}
              >
                {isSelected && (
                  <InfoWindow onCloseClick={() => setSelectedKey(null)}>
                    <div style={{ minWidth: 200, textAlign: "left" }}>
                      <strong>{label}</strong>
                      <p style={{ margin: "8px 0 0", fontSize: "0.9em" }}>
                        {n}+ 位医生在此机构执业
                      </p>
                      <p
                        style={{
                          margin: "8px 0 0",
                          fontSize: "0.8em",
                          color: "#666",
                        }}
                      >
                        详细列表待后端接口补充
                      </p>
                    </div>
                  </InfoWindow>
                )}
              </Marker>
            );
          }

          if (g.records.length === 1) {
            return (
              <Marker
                key={g.key}
                position={pos}
                icon={getSingleIcon()}
                title={tooltipText}
                onClick={() => setSelectedKey(isSelected ? null : g.key)}
              >
                {isSelected && (
                  <InfoWindow onCloseClick={() => setSelectedKey(null)}>
                    <div>
                      <strong>{label ?? first.full_name}</strong>
                      <br />
                      CPSO: {first.cpso_number}
                      {first.phone && (
                        <>
                          <br />
                          Phone: {first.phone}
                        </>
                      )}
                      {first.fax && (
                        <>
                          <br />
                          Fax: {first.fax}
                        </>
                      )}
                      {first.full_address && (
                        <>
                          <br />
                          {first.full_address}
                        </>
                      )}
                      <br />
                      <button
                        type="button"
                        onClick={() => handleMarkerClick(first)}
                        style={{ marginTop: 8, cursor: "pointer" }}
                      >
                        查看医生详情
                      </button>
                    </div>
                  </InfoWindow>
                )}
              </Marker>
            );
          }

          return (
            <Marker
              key={g.key}
              position={pos}
              icon={getClusterIcon()}
              label={{
                text: markerLabel,
                color: "white",
                fontSize: "12px",
                fontWeight: "bold",
              }}
              title={tooltipText}
              onClick={() => setSelectedKey(isSelected ? null : g.key)}
            >
              {isSelected && (
                <InfoWindow onCloseClick={() => setSelectedKey(null)}>
                  <div
                    style={{
                      maxHeight: 280,
                      overflowY: "auto",
                      minWidth: 220,
                      textAlign: "left",
                    }}
                  >
                    <strong>
                      {label ?? "同一坐标"} {n} 条记录
                    </strong>
                    <p style={{ fontSize: "0.85em", margin: "6px 0 10px" }}>
                      多条地址 geocode 到相同位置，故合并显示。
                    </p>
                    {g.records.map((r) => (
                      <div
                        key={r.id}
                        style={{
                          borderTop: "1px solid #e5e7eb",
                          padding: "8px 0",
                        }}
                      >
                        <div style={{ fontWeight: 600 }}>{r.full_name}</div>
                        <div style={{ fontSize: "0.85em" }}>
                          CPSO: {r.cpso_number}
                        </div>
                        {r.phone && (
                          <div style={{ fontSize: "0.85em" }}>
                            Phone: {r.phone}
                          </div>
                        )}
                        {r.fax && (
                          <div style={{ fontSize: "0.85em" }}>
                            Fax: {r.fax}
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={() => handleMarkerClick(r)}
                          style={{ marginTop: 6, cursor: "pointer" }}
                        >
                          查看详情
                        </button>
                      </div>
                    ))}
                  </div>
                </InfoWindow>
              )}
            </Marker>
          );
        })}
        {searchResult && (
          <Marker
            key="search-result"
            position={{ lat: searchResult.lat, lng: searchResult.lng }}
            icon={getSearchResultIcon()}
            title={`搜索定位：${searchResult.displayName}`}
            zIndex={1000}
          />
        )}
      </GoogleMap>
    </div>
  );
}

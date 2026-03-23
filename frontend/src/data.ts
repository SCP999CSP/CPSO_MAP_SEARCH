import type { DoctorAddressRecord } from "./types";

let cache: DoctorAddressRecord[] | null = null;

export async function fetchDoctorAddresses(): Promise<DoctorAddressRecord[]> {
  if (cache) return cache;
  // 开发时避免浏览器一直用旧 JSON；生产构建仍走静态文件缓存策略
  const url =
    import.meta.env.DEV
      ? `/doctors-addresses.json?t=${Date.now()}`
      : "/doctors-addresses.json";
  let res = await fetch(url);
  let data: DoctorAddressRecord[];
  if (!res.ok) {
    const sampleRes = await fetch("/doctors-addresses.sample.json");
    if (sampleRes.ok) {
      data = await sampleRes.json();
    } else {
      throw new Error(
        `Failed to load doctors data. Run: cd CPSO_WEB_DATA && python3 export_to_json.py`
      );
    }
  } else {
    data = await res.json();
  }
  cache = Array.isArray(data) ? data : [];
  return cache;
}

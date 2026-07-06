import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchDoctorAddresses } from "../data";
import type { DoctorAddressRecord } from "../types";

export default function DoctorPage() {
  const { cpso_number } = useParams<{ cpso_number: string }>();
  const [records, setRecords] = useState<DoctorAddressRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cpso_number) return;
    fetchDoctorAddresses()
      .then((all) => all.filter((r) => r.cpso_number === cpso_number))
      .then(setRecords)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [cpso_number]);

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        加载中…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, color: "#b91c1c" }}>
        {error}
        <br />
        <Link to="/">返回地图</Link>
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        未找到 CPSO 号为 {cpso_number} 的医生
        <br />
        <Link to="/">返回地图</Link>
      </div>
    );
  }

  const doctor = records[0];

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 640,
        fontSize: 17,
        lineHeight: 1.55,
      }}
    >
      <Link
        to="/"
        style={{ marginBottom: 16, display: "inline-block", fontSize: 16 }}
      >
        ← 返回地图
      </Link>
      <h1 style={{ fontSize: "1.75rem", marginBottom: 12 }}>
        {doctor.full_name}
      </h1>
      <p style={{ fontSize: 17, margin: "8px 0" }}>
        <strong>CPSO 注册号:</strong> {doctor.cpso_number}
      </p>
      {(doctor.gender ||
        doctor.medical_school ||
        doctor.languages ||
        doctor.graduate_data) && (
        <div
          style={{
            marginTop: 12,
            padding: "14px 16px",
            background: "#f9fafb",
            borderRadius: 8,
            fontSize: 16,
          }}
        >
          {doctor.gender && (
            <p style={{ margin: "0 0 8px" }}>
              <strong>Gender:</strong> {doctor.gender}
            </p>
          )}
          {doctor.medical_school && (
            <p style={{ margin: "0 0 8px" }}>
              <strong>Medical school:</strong> {doctor.medical_school}
            </p>
          )}
          {doctor.languages && (
            <p style={{ margin: "0 0 8px" }}>
              <strong>Languages:</strong> {doctor.languages}
            </p>
          )}
          {doctor.graduate_data && (
            <p style={{ margin: 0 }}>
              <strong>Graduated:</strong> {doctor.graduate_data}
            </p>
          )}
        </div>
      )}
      <h2 style={{ fontSize: "1.35rem", marginTop: 24 }}>地址与联系方式</h2>
      {records.map((r, i) => (
        <div
          key={r.id}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
          }}
        >
          {records.length > 1 && <h3>地址 {i + 1}</h3>}
          {r.full_address && <p>{r.full_address}</p>}
          {r.city && (
            <p>
              {r.city}
              {r.province && `, ${r.province}`}
              {r.postal_code && ` ${r.postal_code}`}
            </p>
          )}
          {r.phone && (
            <p>
              <strong>电话:</strong> {r.phone}
            </p>
          )}
          {r.fax && (
            <p>
              <strong>传真:</strong> {r.fax}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

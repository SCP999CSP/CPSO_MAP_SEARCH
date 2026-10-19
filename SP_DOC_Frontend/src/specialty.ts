export const SPECIALTIES = [
  "Hematology",
  "Neurology",
  "Rheumatology",
  "Dermatology",
  "Gastroenterology",
] as const;

export type Specialty = (typeof SPECIALTIES)[number];

/** 单一专科、命中 2 个及以上关键词、一个都没命中 */
export type DoctorCategory = Specialty | "multi" | "none";

/** 合并点位里的医生分类不一致时 */
export type GroupCategory = DoctorCategory | "mixed";

export const CATEGORY_COLORS: Record<GroupCategory, string> = {
  Hematology: "#dc2626",
  Neurology: "#7c3aed",
  Rheumatology: "#ea580c",
  Dermatology: "#db2777",
  Gastroenterology: "#16a34a",
  multi: "#0f172a",
  none: "#9ca3af",
  mixed: "#1d4ed8",
};

export const CATEGORY_LABELS: Record<GroupCategory, string> = {
  Hematology: "Hematology",
  Neurology: "Neurology",
  Rheumatology: "Rheumatology",
  Dermatology: "Dermatology",
  Gastroenterology: "Gastroenterology",
  multi: "多专科",
  none: "未分类",
  mixed: "混合点位",
};

/** 只认 5 个关键词（不区分大小写），Family Medicine 等其他专科忽略 */
export function matchSpecialties(raw: string | null | undefined): Specialty[] {
  if (!raw) return [];
  const text = raw.toLowerCase();
  return SPECIALTIES.filter((s) => text.includes(s.toLowerCase()));
}

export function doctorCategory(raw: string | null | undefined): DoctorCategory {
  const matched = matchSpecialties(raw);
  if (matched.length === 0) return "none";
  if (matched.length === 1) return matched[0];
  return "multi";
}

export function groupCategory(
  raws: (string | null | undefined)[]
): GroupCategory {
  const categories = new Set(raws.map(doctorCategory));
  if (categories.size === 1) return [...categories][0];
  return "mixed";
}

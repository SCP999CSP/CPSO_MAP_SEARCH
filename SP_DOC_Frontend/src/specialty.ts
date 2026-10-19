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

export const CATEGORY_COLORS: Record<Specialty, string> = {
  Hematology: "rgb(245, 12, 12)",
  Neurology: "rgba(0, 255, 21, 0.76)",
  Rheumatology: "rgb(0, 32, 173)",
  Dermatology: "rgb(255, 217, 0)",
  Gastroenterology: "rgba(0, 0, 0, 0.64)",
};

export const CATEGORY_LABELS: Record<Specialty, string> = {
  Hematology: "Hematology",
  Neurology: "Neurology",
  Rheumatology: "Rheumatology",
  Dermatology: "Dermatology",
  Gastroenterology: "Gastroenterology",
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

export function isListedSpecialty(
  category: DoctorCategory
): category is Specialty {
  return category !== "multi" && category !== "none";
}

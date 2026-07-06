export interface DoctorAddressRecord {
  id: string;
  cpso_number: string;
  full_name: string;
  /** 来自 doctors.gender（旧版 JSON 可能无此键） */
  gender?: string | null;
  /** 来自 doctors.medical_school */
  medical_school?: string | null;
  /** 来自 doctors.languages_spoken */
  languages?: string | null;
  /** 来自 doctors.graduate_data */
  graduate_data?: string | null;
  latitude: number;
  longitude: number;
  phone: string | null;
  fax: string | null;
  full_address: string | null;
  city: string | null;
  province: string | null;
  postal_code: string | null;
}

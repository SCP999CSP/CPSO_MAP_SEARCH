export interface Bounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

/** 与后端 LocationRead 一致 */
export interface MapLocation {
  id: string;
  cpso_number: string;
  full_name: string;
  specialties: string | null;
  gender: string | null;
  medical_school: string | null;
  languages_spoken: string | null;
  graduate_data: string | null;
  full_address: string | null;
  city: string | null;
  province: string | null;
  postal_code: string | null;
  phone: string | null;
  fax: string | null;
  latitude: number;
  longitude: number;
}

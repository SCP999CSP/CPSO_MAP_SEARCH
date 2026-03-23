export interface DoctorAddressRecord {
  id: string;
  cpso_number: string;
  full_name: string;
  latitude: number;
  longitude: number;
  phone: string | null;
  fax: string | null;
  full_address: string | null;
  city: string | null;
  province: string | null;
  postal_code: string | null;
}

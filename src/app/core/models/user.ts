export interface User {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at?: string | null;
  auth_provider?: string | null;
  azure_oid?: string | null;
}

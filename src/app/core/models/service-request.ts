export type RequestUrgency = 'NORMAL' | 'URGENT';
export type RequestStatus =
  | 'CREATED'
  | 'MATCHING'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'DONE'
  | 'CANCELED';

export type ContactPref = 'WHATSAPP' | 'CALL' | 'CHAT';

export interface ServiceRequestCreate {
  category: string;
  title: string;
  description: string;

  urgency?: RequestUrgency;

  city?: string | null;
  neighborhood?: string | null;
  address?: string | null;
  address_ref?: string | null;

  // ✅ GEO
  lat?: number | null;
  lng?: number | null;
  accuracy_m?: number | null;

  schedule_date?: string | null; // YYYY-MM-DD
  time_window?: string | null;

  budget_min?: number | null;
  budget_max?: number | null;

  contact_name?: string | null;
  contact_phone?: string | null;
  contact_pref?: ContactPref | null;
}

export interface ServiceRequest {
  id: number;
  user_id: number;

  category: string;
  title: string;
  description: string;

  urgency: RequestUrgency;

  city?: string | null;
  neighborhood?: string | null;
  address?: string | null;
  address_ref?: string | null;

  // ✅ GEO
  lat?: number | null;
  lng?: number | null;
  accuracy_m?: number | null;

  schedule_date?: string | null;
  time_window?: string | null;

  budget_min?: number | null;
  budget_max?: number | null;

  contact_name?: string | null;
  contact_phone?: string | null;
  contact_pref?: ContactPref | null;

  status: RequestStatus;
  created_at?: string;
  updated_at?: string;
}

// ✅ Antes era Pick<...> (resumen). Ahora: trae TODO.
export type ServiceRequestListItem = ServiceRequest;

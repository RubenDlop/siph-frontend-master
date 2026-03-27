export type RequestUrgency = 'NORMAL' | 'URGENT';
export type RequestStatus =
  | 'CREATED'
  | 'MATCHING'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'DONE'
  | 'CANCELED';

export type ContactPref = 'WHATSAPP' | 'CALL' | 'CHAT';

export interface RequestUserLite {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface ServiceRequestCreate {
  category: string;
  title: string;
  description: string;

  urgency?: RequestUrgency;

  city?: string | null;
  neighborhood?: string | null;
  address?: string | null;
  address_ref?: string | null;

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
}

export interface ServiceRequest {
  id: number;
  user_id: number;
  assigned_worker_id?: number | null;

  category: string;
  title: string;
  description: string;

  urgency: RequestUrgency;

  city?: string | null;
  neighborhood?: string | null;
  address?: string | null;
  address_ref?: string | null;

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

  assigned_at?: string | null;
  accepted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;

  created_at?: string | null;
  updated_at?: string | null;

  customer?: RequestUserLite | null;
  assigned_worker?: RequestUserLite | null;

  client_name?: string | null;
  client_email?: string | null;
  assigned_worker_name?: string | null;
  assigned_worker_email?: string | null;
}

export type ServiceRequestListItem = ServiceRequest;

export interface RequestMessageCreate {
  body: string;
}

export interface RequestMessage {
  id: number;
  request_id: number;
  sender_user_id: number;
  body: string;
  created_at: string;
  read_at?: string | null;

  sender?: RequestUserLite | null;

  sender_name?: string | null;
  sender_role?: string | null;
  is_mine?: boolean;
}

export interface RequestEvent {
  id: number;
  request_id: number;
  actor_user_id?: number | null;
  event_type: string;
  title: string;
  message?: string | null;
  status_from?: string | null;
  status_to?: string | null;
  meta?: Record<string, any>;
  created_at: string;
  actor?: RequestUserLite | null;
}

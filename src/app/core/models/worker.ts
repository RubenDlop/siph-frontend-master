export interface WorkerPublicDocument {
  id: number;
  doc_type: string;
  label: string;
  original_name?: string | null;
  content_type?: string | null;
  has_file?: boolean;
  file_url?: string | null;
}

export interface Worker {
  id: number;
  user_id: number;
  public_name: string;

  photo_url?: string | null;
  city?: string | null;
  specialty?: string | null;
  years_experience?: number | null;
  bio?: string | null;

  categories: string[];
  badge_level: 'BASIC' | 'TRUST' | 'PRO' | 'PAY';
  verification_status:
    | 'UNVERIFIED'
    | 'PENDING'
    | 'IN_REVIEW'
    | 'VERIFIED'
    | 'REJECTED';

  is_verified: boolean;
  visible_documents: WorkerPublicDocument[];

  // ✅ calificación pública real
  average_rating?: number | null;
  reviews_count?: number | null;
}

export interface ReviewUserLite {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface RequestReviewCreate {
  rating: number;
  comment?: string | null;
}

export interface RequestReview {
  id: number;
  request_id: number;
  reviewer_user_id: number;
  reviewee_user_id: number;
  reviewer_role: 'CUSTOMER' | 'WORKER';
  rating: number;
  comment?: string | null;
  created_at: string;
  updated_at: string;
  reviewer?: ReviewUserLite | null;
  reviewee?: ReviewUserLite | null;
}

export interface RequestReviewSummary {
  request_id: number;
  status: string;

  customer_review_done: boolean;
  worker_review_done: boolean;

  can_review_as_customer: boolean;
  can_review_as_worker: boolean;

  my_review?: RequestReview | null;
  customer_review?: RequestReview | null;
  worker_review?: RequestReview | null;
}

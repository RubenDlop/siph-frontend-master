import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  RequestReview,
  RequestReviewCreate,
  RequestReviewSummary,
} from '../models/review';

@Injectable({ providedIn: 'root' })
export class ReviewsService {
  private readonly baseUrl = (environment.apiUrl || 'http://localhost:8000').replace(/\/+$/, '');

  constructor(private http: HttpClient) {}

  getRequestSummary(requestId: number): Observable<RequestReviewSummary> {
    return this.http.get<RequestReviewSummary>(`${this.baseUrl}/reviews/request/${requestId}/summary`);
  }

  saveRequestReview(requestId: number, payload: RequestReviewCreate): Observable<RequestReview> {
    return this.http.post<RequestReview>(`${this.baseUrl}/reviews/request/${requestId}`, payload);
  }

  getPublicWorkerReviews(workerId: number): Observable<{
    worker_id: number;
    average_rating: number | null;
    reviews_count: number;
    items: Array<{
      id: number;
      rating: number;
      comment?: string | null;
      created_at: string;
      reviewer?: any;
    }>;
  }> {
    return this.http.get<{
      worker_id: number;
      average_rating: number | null;
      reviews_count: number;
      items: Array<{
        id: number;
        rating: number;
        comment?: string | null;
        created_at: string;
        reviewer?: any;
      }>;
    }>(`${this.baseUrl}/reviews/worker/${workerId}/public`);
  }
}

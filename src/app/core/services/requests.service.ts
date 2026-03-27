import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import {
  ServiceRequest,
  ServiceRequestCreate,
  ServiceRequestListItem,
  RequestMessage,
  RequestMessageCreate,
  RequestUserLite,
  RequestEvent,
} from '../models/service-request';

interface RawRequestMessage {
  id: number;
  request_id: number;
  sender_user_id: number;
  body: string;
  created_at: string;
  read_at?: string | null;
  sender?: RequestUserLite | null;
  is_mine?: boolean;
}

@Injectable({ providedIn: 'root' })
export class RequestsService {
  private readonly baseUrl = (environment.apiUrl || 'http://localhost:8000').replace(/\/+$/, '');

  constructor(private http: HttpClient) {}

  private mapMessage(msg: RawRequestMessage): RequestMessage {
    return {
      id: msg.id,
      request_id: msg.request_id,
      sender_user_id: msg.sender_user_id,
      body: msg.body,
      created_at: msg.created_at,
      read_at: msg.read_at ?? null,
      sender: msg.sender ?? null,
      sender_name: msg.sender
        ? `${msg.sender.first_name || ''} ${msg.sender.last_name || ''}`.trim()
        : null,
      sender_role: msg.sender?.role ?? null,
      is_mine: !!msg.is_mine,
    };
  }

  create(payload: ServiceRequestCreate): Observable<ServiceRequest> {
    return this.http.post<ServiceRequest>(`${this.baseUrl}/requests`, payload);
  }

  myRequests(): Observable<ServiceRequestListItem[]> {
    return this.http.get<ServiceRequestListItem[]>(`${this.baseUrl}/requests/me`);
  }

  getRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.get<ServiceRequest>(`${this.baseUrl}/requests/${requestId}`);
  }

  cancelRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(`${this.baseUrl}/requests/${requestId}/cancel`, {});
  }

  cancelAcceptance(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(
      `${this.baseUrl}/requests/${requestId}/cancel-acceptance`,
      {}
    );
  }

  cancel(requestId: number): Observable<ServiceRequest> {
    return this.cancelRequest(requestId);
  }

  getEvents(requestId: number): Observable<RequestEvent[]> {
    return this.http.get<RequestEvent[]>(`${this.baseUrl}/requests/${requestId}/events`);
  }

  getMessages(requestId: number): Observable<RequestMessage[]> {
    return this.http
      .get<RawRequestMessage[]>(`${this.baseUrl}/requests/${requestId}/messages`)
      .pipe(map((rows: RawRequestMessage[]) => rows.map((row) => this.mapMessage(row))));
  }

  sendMessage(requestId: number, payload: RequestMessageCreate): Observable<RequestMessage> {
    return this.http
      .post<RawRequestMessage>(`${this.baseUrl}/requests/${requestId}/messages`, payload)
      .pipe(map((msg: RawRequestMessage) => this.mapMessage(msg)));
  }
}

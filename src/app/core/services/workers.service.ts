import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import {
  RequestMessage,
  RequestUserLite,
  ServiceRequest,
} from '../models/service-request';
import { Worker } from '../models/worker';

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

@Injectable({
  providedIn: 'root',
})
export class WorkersService {
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

  private mapWorker(worker: Worker): Worker {
    return {
      ...worker,
      photo_url: worker.photo_url || null,
      visible_documents: (worker.visible_documents || []).map((doc) => ({
        ...doc,
        file_url: doc.file_url
          ? `${this.baseUrl}${doc.file_url.startsWith('/') ? '' : '/'}${doc.file_url}`
          : null,
      })),
    };
  }

  // =========================
  // Público: catálogo de trabajadores
  // =========================
  listWorkers(filters?: {
    q?: string;
    city?: string;
    category?: string;
  }): Observable<Worker[]> {
    let params = new HttpParams();

    if (filters?.q?.trim()) {
      params = params.set('q', filters.q.trim());
    }
    if (filters?.city?.trim()) {
      params = params.set('city', filters.city.trim());
    }
    if (filters?.category?.trim()) {
      params = params.set('category', filters.category.trim());
    }

    return this.http
      .get<Worker[]>(`${this.baseUrl}/workers`, { params })
      .pipe(map((rows: Worker[]) => rows.map((row) => this.mapWorker(row))));
  }

  getWorker(workerId: number): Observable<Worker> {
    return this.http
      .get<Worker>(`${this.baseUrl}/workers/${workerId}`)
      .pipe(map((row: Worker) => this.mapWorker(row)));
  }

  // =========================
  // Panel del trabajador
  // =========================
  getAvailableRequests(): Observable<ServiceRequest[]> {
    return this.http.get<ServiceRequest[]>(`${this.baseUrl}/worker/requests/available`);
  }

  getMyJobs(): Observable<ServiceRequest[]> {
    return this.http.get<ServiceRequest[]>(`${this.baseUrl}/worker/requests/my-jobs`);
  }

  getMyJobsAlt(): Observable<ServiceRequest[]> {
    return this.http.get<ServiceRequest[]>(`${this.baseUrl}/worker/requests/mine`);
  }

  getRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.get<ServiceRequest>(`${this.baseUrl}/worker/requests/${requestId}`);
  }

  acceptRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(
      `${this.baseUrl}/worker/requests/${requestId}/accept`,
      {}
    );
  }

  releaseRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(
      `${this.baseUrl}/worker/requests/${requestId}/release`,
      {}
    );
  }

  startRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(
      `${this.baseUrl}/worker/requests/${requestId}/start`,
      {}
    );
  }

  completeRequest(requestId: number): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(
      `${this.baseUrl}/worker/requests/${requestId}/complete`,
      {}
    );
  }

  getMessages(requestId: number): Observable<RequestMessage[]> {
    return this.http
      .get<RawRequestMessage[]>(`${this.baseUrl}/requests/${requestId}/messages`)
      .pipe(map((rows: RawRequestMessage[]) => rows.map((row) => this.mapMessage(row))));
  }

  sendMessage(requestId: number, body: string): Observable<RequestMessage> {
    return this.http
      .post<RawRequestMessage>(
        `${this.baseUrl}/requests/${requestId}/messages`,
        { body }
      )
      .pipe(map((msg: RawRequestMessage) => this.mapMessage(msg)));
  }
}

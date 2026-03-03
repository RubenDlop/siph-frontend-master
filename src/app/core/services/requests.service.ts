// src/app/core/services/requests.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { ServiceRequest, ServiceRequestCreate } from '../models/service-request';

@Injectable({ providedIn: 'root' })
export class RequestsService {
  private base = environment.apiUrl || 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  create(payload: ServiceRequestCreate) {
    return this.http.post<ServiceRequest>(`${this.base}/requests`, payload);
  }

  // ✅ COMPLETO
  myRequests() {
    return this.http.get<ServiceRequest[]>(`${this.base}/requests/me`);
  }

  cancel(id: number) {
    return this.http.patch<ServiceRequest>(`${this.base}/requests/${id}/cancel`, {});
  }
}

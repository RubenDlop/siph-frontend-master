import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export type TechLevel = 'BASIC' | 'TRUST' | 'PRO' | 'PAY';
export type TechStatus = 'PENDING' | 'IN_REVIEW' | 'VERIFIED' | 'REJECTED';

export interface AdminCaseDoc {
  id: number;
  docType: string;
  receivedAt: string | null;
  verifiedResult: 'ok' | 'fail' | 'unknown' | null;
  verifiedAt: string | null;
  meta: any;
  originalName?: string | null;
  contentType?: string | null;
  hasFile?: boolean;
}

export interface AdminCaseDetail {
  caseId: number;
  techId: number;
  status: TechStatus;
  targetLevel: TechLevel;
  createdAt: string;
  tech: {
    publicName: string;
    city: string;
    specialty: string;
    userId?: number | null;
  };
  documents: AdminCaseDoc[];
}

@Injectable({ providedIn: 'root' })
export class AdminTechVerificationService {
  private http = inject(HttpClient);
  private base = environment.apiUrl || 'http://localhost:8000';


  latestCaseByUser(userId: number) {
    return this.http.get<AdminCaseDetail | { hasCase: false }>(
      `${this.base}/admin/tech/verification/cases/by-user/${userId}`
      );
  }


  downloadDoc(caseId: number, docId: number) {
    return this.http.get(`${this.base}/admin/tech/verification/cases/${caseId}/documents/${docId}/file`, {
      responseType: 'blob',
    });
  }
}

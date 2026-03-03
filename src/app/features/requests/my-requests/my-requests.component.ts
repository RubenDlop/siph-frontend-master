import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { RequestsService } from '../../../core/services/requests.service';
import { ServiceRequest, RequestStatus } from '../../../core/models/service-request';

type StatusFilter = RequestStatus | 'ALL';

@Component({
  selector: 'app-my-requests',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './my-requests.component.html',
  styleUrl: './my-requests.component.scss',
})
export class MyRequestsComponent implements OnInit {
  items: ServiceRequest[] = [];
  filtered: ServiceRequest[] = [];

  loading = true;
  errorMsg = '';

  q = '';
  status: StatusFilter = 'ALL';

  expandedId: number | null = null;

  constructor(private requests: RequestsService) {}

  ngOnInit(): void {
    this.reload();
  }

  // ✅ Para chips
  setStatus(s: StatusFilter) {
    this.status = s;
    this.applyFilters();
  }

  // ✅ KPIs (solo lectura)
  get countDone() {
    return (this.items || []).filter((x) => x.status === 'DONE').length;
  }

  get countCanceled() {
    return (this.items || []).filter((x) => x.status === 'CANCELED').length;
  }

  get countActive() {
    return (this.items || []).filter((x) => x.status !== 'DONE' && x.status !== 'CANCELED').length;
  }

  reload() {
    this.loading = true;
    this.errorMsg = '';

    this.requests.myRequests().subscribe({
      next: (rows) => {
        this.items = rows || [];
        this.applyFilters();
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.errorMsg = 'No se pudieron cargar tus solicitudes. Revisa el backend.';
      },
    });
  }

  applyFilters() {
    const term = (this.q || '').trim().toLowerCase();

    this.filtered = (this.items || []).filter((r) => {
      const statusOk = this.status === 'ALL' ? true : r.status === this.status;

      const hayTerm =
        !term ||
        [
          r.title,
          r.category,
          r.description,
          r.city,
          r.neighborhood,
          r.address,
          r.address_ref,
          r.contact_name,
          r.contact_phone,
          r.contact_pref,
          r.urgency,
          r.status,
        ]
          .filter(Boolean)
          .some((x) => String(x).toLowerCase().includes(term));

      return statusOk && hayTerm;
    });
  }

  toggle(id: number) {
    this.expandedId = this.expandedId === id ? null : id;
  }

  canCancel(r: ServiceRequest) {
    return r.status !== 'DONE' && r.status !== 'CANCELED';
  }

  cancel(r: ServiceRequest) {
    if (!this.canCancel(r)) return;

    this.requests.cancel(r.id).subscribe({
      next: (updated) => {
        this.items = this.items.map((x) => (x.id === updated.id ? updated : x));
        this.applyFilters();
      },
      error: () => {
        this.errorMsg = 'No se pudo cancelar la solicitud.';
      },
    });
  }

  fmtMoney(n?: number | null) {
    if (n == null) return '—';
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(n);
  }

  fmtMoneyRange(min?: number | null, max?: number | null) {
    if (min == null && max == null) return '—';
    if (min != null && max == null) return `${this.fmtMoney(min)} a —`;
    if (min == null && max != null) return `— a ${this.fmtMoney(max)}`;
    return `${this.fmtMoney(min)} a ${this.fmtMoney(max)}`;
  }

  fmtDate(s?: string | null) {
    if (!s) return '—';
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;
    return d.toLocaleString('es-CO', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  statusLabel(s: RequestStatus) {
    switch (s) {
      case 'CREATED':
        return 'Creada';
      case 'MATCHING':
        return 'Buscando';
      case 'ASSIGNED':
        return 'Asignada';
      case 'IN_PROGRESS':
        return 'En progreso';
      case 'DONE':
        return 'Finalizada';
      case 'CANCELED':
        return 'Cancelada';
      default:
        return s;
    }
  }

  statusClass(s: RequestStatus) {
    switch (s) {
      case 'DONE':
        return 'border-emerald-200 bg-emerald-50 text-emerald-800';
      case 'IN_PROGRESS':
        return 'border-sky-200 bg-sky-50 text-sky-800';
      case 'ASSIGNED':
        return 'border-indigo-200 bg-indigo-50 text-indigo-800';
      case 'MATCHING':
        return 'border-amber-200 bg-amber-50 text-amber-800';
      case 'CANCELED':
        return 'border-rose-200 bg-rose-50 text-rose-800';
      case 'CREATED':
      default:
        return 'border-slate-200 bg-slate-50 text-slate-800';
    }
  }

  urgencyClass(u: any) {
    return u === 'URGENT'
      ? 'border-rose-200 bg-rose-50 text-rose-800'
      : 'border-slate-200 bg-slate-50 text-slate-800';
  }

  trackById = (_: number, r: ServiceRequest) => r.id;
}

import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { RequestsService } from '../../../core/services/requests.service';
import { ReviewsService } from '../../../core/services/reviews.service';

import {
  RequestEvent,
  RequestStatus,
  ServiceRequest,
} from '../../../core/models/service-request';

import {
  RequestReviewSummary,
} from '../../../core/models/review';

type StatusFilter = RequestStatus | 'ALL';
type NotificationTone = 'info' | 'success' | 'warning' | 'danger';

type UiNotification = {
  id: string;
  requestId: number;
  title: string;
  message: string;
  tone: NotificationTone;
  createdAt: number;
  read: boolean;
};

type ReviewDraft = {
  rating: number;
  comment: string;
  saving: boolean;
  error: string;
};

@Component({
  selector: 'app-my-requests',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './my-requests.component.html',
  styleUrl: './my-requests.component.scss',
})
export class MyRequestsComponent implements OnInit, OnDestroy {
  items: ServiceRequest[] = [];
  filtered: ServiceRequest[] = [];
  eventsByRequest: Record<number, RequestEvent[]> = {};

  notifications: UiNotification[] = [];

  reviewSummaryByRequest: Record<number, RequestReviewSummary> = {};
  reviewDraftByRequest: Record<number, ReviewDraft> = {};

  loading = true;
  loadingEvents = false;
  silentRefreshing = false;
  errorMsg = '';

  q = '';
  status: StatusFilter = 'ALL';
  expandedId: number | null = null;

  private pollHandle: ReturnType<typeof setInterval> | null = null;
  private readonly notificationsStorageKey = 'siph_my_requests_notifications';

  constructor(
    private requests: RequestsService,
    private reviews: ReviewsService
  ) {}

  ngOnInit(): void {
    this.loadStoredNotifications();
    this.reload(true, false);
    this.startPolling();
  }

  ngOnDestroy(): void {
    if (this.pollHandle) {
      clearInterval(this.pollHandle);
      this.pollHandle = null;
    }
  }

  get countDone(): number {
    return (this.items || []).filter((x) => x.status === 'DONE').length;
  }

  get countCanceled(): number {
    return (this.items || []).filter((x) => x.status === 'CANCELED').length;
  }

  get countActive(): number {
    return (this.items || []).filter(
      (x) => x.status !== 'DONE' && x.status !== 'CANCELED'
    ).length;
  }

  get unreadNotificationsCount(): number {
    return this.notifications.filter((n) => !n.read).length;
  }

  get expandedRequest(): ServiceRequest | null {
    if (this.expandedId == null) return null;
    return this.items.find((x) => x.id === this.expandedId) || null;
  }

  startPolling(): void {
    this.pollHandle = setInterval(() => {
      this.reload(false, true);
    }, 12000);
  }

  reload(resetLoading = true, silent = false): void {
    if (resetLoading) {
      this.loading = true;
    }
    if (silent) {
      this.silentRefreshing = true;
    }

    this.requests.myRequests().subscribe({
      next: (rows: ServiceRequest[]) => {
        const nextRows = (rows || []).slice().sort((a, b) => {
          const ta = new Date(a.updated_at || a.created_at || 0).getTime();
          const tb = new Date(b.updated_at || b.created_at || 0).getTime();
          return tb - ta;
        });

        if (!this.loading && silent) {
          this.detectChanges(this.items, nextRows);
        }

        this.items = nextRows;
        this.applyFilters();

        if (this.expandedId != null) {
          this.loadEvents(this.expandedId, true);
          this.loadReviewSummary(this.expandedId, true);
        }

        this.loading = false;
        this.silentRefreshing = false;
      },
      error: () => {
        this.loading = false;
        this.silentRefreshing = false;
        this.errorMsg = 'No se pudieron cargar tus solicitudes. Revisa el backend.';
      },
    });
  }

  applyFilters(): void {
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
          r.assigned_worker_name,
          r.assigned_worker_email,
        ]
          .filter(Boolean)
          .some((x) => String(x).toLowerCase().includes(term));

      return statusOk && hayTerm;
    });
  }

  setStatus(s: StatusFilter): void {
    this.status = s;
    this.applyFilters();
  }

  toggle(id: number): void {
    this.expandedId = this.expandedId === id ? null : id;

    if (this.expandedId != null) {
      this.loadEvents(this.expandedId);
      this.loadReviewSummary(this.expandedId);
    }
  }

  loadEvents(requestId: number, silent = false): void {
    if (!silent) {
      this.loadingEvents = true;
    }

    this.requests.getEvents(requestId).subscribe({
      next: (rows: RequestEvent[]) => {
        this.eventsByRequest[requestId] = rows || [];
        this.loadingEvents = false;
      },
      error: () => {
        this.loadingEvents = false;
      },
    });
  }

  getEventsFor(requestId: number): RequestEvent[] {
    return this.eventsByRequest[requestId] || [];
  }

  loadReviewSummary(requestId: number, silent = false): void {
    this.reviews.getRequestSummary(requestId).subscribe({
      next: (summary: RequestReviewSummary) => {
        this.reviewSummaryByRequest[requestId] = summary;

        if (!this.reviewDraftByRequest[requestId]) {
          this.reviewDraftByRequest[requestId] = {
            rating: summary.my_review?.rating || 5,
            comment: summary.my_review?.comment || '',
            saving: false,
            error: '',
          };
        } else {
          this.reviewDraftByRequest[requestId].rating =
            summary.my_review?.rating || this.reviewDraftByRequest[requestId].rating || 5;
          this.reviewDraftByRequest[requestId].comment =
            summary.my_review?.comment || this.reviewDraftByRequest[requestId].comment || '';
          this.reviewDraftByRequest[requestId].saving = false;
        }
      },
      error: () => {
        if (!silent) {
          // silencioso para no romper UX
        }
      },
    });
  }

  getReviewSummary(requestId: number): RequestReviewSummary | null {
    return this.reviewSummaryByRequest[requestId] || null;
  }

  getReviewDraft(requestId: number): ReviewDraft {
    if (!this.reviewDraftByRequest[requestId]) {
      this.reviewDraftByRequest[requestId] = {
        rating: 5,
        comment: '',
        saving: false,
        error: '',
      };
    }
    return this.reviewDraftByRequest[requestId];
  }

  canCancel(r: ServiceRequest): boolean {
    return ['CREATED', 'MATCHING', 'ASSIGNED'].includes(r.status);
  }

  canCancelAcceptance(r: ServiceRequest): boolean {
    return r.status === 'ASSIGNED' && !!r.assigned_worker_id && !r.started_at;
  }

  cancel(r: ServiceRequest): void {
    if (!this.canCancel(r)) return;

    const ok = window.confirm(
      '¿Seguro que quieres cancelar completamente esta solicitud?'
    );
    if (!ok) return;

    this.requests.cancel(r.id).subscribe({
      next: (updated: ServiceRequest) => {
        this.items = this.items.map((x) => (x.id === updated.id ? updated : x));
        this.applyFilters();

        if (this.expandedId === updated.id) {
          this.loadEvents(updated.id);
          this.loadReviewSummary(updated.id, true);
        }

        this.pushNotification({
          requestId: updated.id,
          title: 'Solicitud cancelada',
          message: `La solicitud "${updated.title}" fue cancelada.`,
          tone: 'danger',
        });
      },
      error: () => {
        this.errorMsg = 'No se pudo cancelar la solicitud.';
      },
    });
  }

  cancelAcceptance(r: ServiceRequest): void {
    if (!this.canCancelAcceptance(r)) return;

    const ok = window.confirm(
      '¿Deseas cancelar la aceptación del técnico y volver esta solicitud a búsqueda?'
    );
    if (!ok) return;

    this.requests.cancelAcceptance(r.id).subscribe({
      next: (updated: ServiceRequest) => {
        this.items = this.items.map((x) => (x.id === updated.id ? updated : x));
        this.applyFilters();

        if (this.expandedId === updated.id) {
          this.loadEvents(updated.id);
          this.loadReviewSummary(updated.id, true);
        }

        this.pushNotification({
          requestId: updated.id,
          title: 'Aceptación cancelada',
          message: `La solicitud "${updated.title}" volvió a búsqueda de técnico.`,
          tone: 'warning',
        });
      },
      error: () => {
        this.errorMsg = 'No se pudo cancelar la aceptación del técnico.';
      },
    });
  }

  saveCustomerReview(r: ServiceRequest): void {
    const draft = this.getReviewDraft(r.id);
    draft.error = '';
    draft.saving = true;

    this.reviews.saveRequestReview(r.id, {
      rating: draft.rating,
      comment: draft.comment || null,
    }).subscribe({
      next: () => {
        draft.saving = false;
        this.loadReviewSummary(r.id);
        this.reload(false, true);

        this.pushNotification({
          requestId: r.id,
          title: 'Calificación guardada',
          message: `Tu reseña para "${r.title}" fue guardada correctamente.`,
          tone: 'success',
        });
      },
      error: (err) => {
        draft.saving = false;
        draft.error = err?.error?.detail || 'No se pudo guardar la calificación.';
      },
    });
  }

  dismissNotification(id: string): void {
    this.notifications = this.notifications.filter((n) => n.id !== id);
    this.persistNotifications();
  }

  markAllNotificationsRead(): void {
    this.notifications = this.notifications.map((n) => ({ ...n, read: true }));
    this.persistNotifications();
  }

  private detectChanges(previousRows: ServiceRequest[], nextRows: ServiceRequest[]): void {
    const previousMap = new Map<number, ServiceRequest>(
      (previousRows || []).map((r) => [r.id, r])
    );

    for (const next of nextRows) {
      const prev = previousMap.get(next.id);
      if (!prev) continue;

      if (
        prev.status === next.status &&
        prev.assigned_worker_id === next.assigned_worker_id &&
        prev.updated_at === next.updated_at
      ) {
        continue;
      }

      const notification = this.buildNotificationFromDiff(prev, next);
      if (notification) {
        this.pushNotification(notification);
      }
    }
  }

  private buildNotificationFromDiff(
    prev: ServiceRequest,
    next: ServiceRequest
  ): Omit<UiNotification, 'id' | 'createdAt' | 'read'> | null {
    if (prev.status !== next.status) {
      switch (next.status) {
        case 'ASSIGNED':
          return {
            requestId: next.id,
            title: 'Técnico asignado',
            message:
              next.assigned_worker_name
                ? `${next.assigned_worker_name} aceptó tu solicitud "${next.title}".`
                : `Un técnico aceptó tu solicitud "${next.title}".`,
            tone: 'success',
          };

        case 'MATCHING':
          return {
            requestId: next.id,
            title: 'Solicitud nuevamente en búsqueda',
            message: `La solicitud "${next.title}" volvió a búsqueda de técnico.`,
            tone: 'warning',
          };

        case 'IN_PROGRESS':
          return {
            requestId: next.id,
            title: 'Servicio iniciado',
            message: `El servicio de "${next.title}" ya fue marcado como iniciado.`,
            tone: 'info',
          };

        case 'DONE':
          return {
            requestId: next.id,
            title: 'Servicio finalizado',
            message: `La solicitud "${next.title}" fue finalizada. Ya puedes calificar al técnico.`,
            tone: 'success',
          };

        case 'CANCELED':
          return {
            requestId: next.id,
            title: 'Solicitud cancelada',
            message: `La solicitud "${next.title}" fue cancelada.`,
            tone: 'danger',
          };
      }
    }

    if (
      prev.assigned_worker_id !== next.assigned_worker_id &&
      !prev.assigned_worker_id &&
      next.assigned_worker_id
    ) {
      return {
        requestId: next.id,
        title: 'Asignación actualizada',
        message:
          next.assigned_worker_name
            ? `Tu solicitud "${next.title}" ahora está asignada a ${next.assigned_worker_name}.`
            : `Tu solicitud "${next.title}" tiene una nueva asignación.`,
        tone: 'success',
      };
    }

    return {
      requestId: next.id,
      title: 'Solicitud actualizada',
      message: `La solicitud "${next.title}" tuvo un cambio reciente.`,
      tone: 'info',
    };
  }

  private pushNotification(
    payload: Omit<UiNotification, 'id' | 'createdAt' | 'read'>
  ): void {
    const notification: UiNotification = {
      id: `${payload.requestId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      requestId: payload.requestId,
      title: payload.title,
      message: payload.message,
      tone: payload.tone,
      createdAt: Date.now(),
      read: false,
    };

    this.notifications = [notification, ...this.notifications].slice(0, 18);
    this.persistNotifications();
  }

  private loadStoredNotifications(): void {
    if (typeof window === 'undefined') return;

    try {
      const raw = localStorage.getItem(this.notificationsStorageKey);
      if (!raw) return;
      this.notifications = JSON.parse(raw) as UiNotification[];
    } catch {
      this.notifications = [];
    }
  }

  private persistNotifications(): void {
    if (typeof window === 'undefined') return;

    localStorage.setItem(
      this.notificationsStorageKey,
      JSON.stringify(this.notifications)
    );
  }

  fmtMoney(n?: number | null): string {
    if (n == null) return '—';
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(n);
  }

  fmtMoneyRange(min?: number | null, max?: number | null): string {
    if (min == null && max == null) return '—';
    if (min != null && max == null) return `${this.fmtMoney(min)} a —`;
    if (min == null && max != null) return `— a ${this.fmtMoney(max)}`;
    return `${this.fmtMoney(min)} a ${this.fmtMoney(max)}`;
  }

  fmtDate(s?: string | null): string {
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

  statusLabel(s: RequestStatus): string {
    switch (s) {
      case 'CREATED':
        return 'Creada';
      case 'MATCHING':
        return 'Buscando técnico';
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

  statusClass(s: RequestStatus): string {
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

  urgencyClass(u: string | null | undefined): string {
    return u === 'URGENT'
      ? 'border-rose-200 bg-rose-50 text-rose-800'
      : 'border-slate-200 bg-slate-50 text-slate-800';
  }

  notificationClass(tone: NotificationTone): string {
    switch (tone) {
      case 'success':
        return 'border-emerald-200 bg-emerald-50 text-emerald-900';
      case 'warning':
        return 'border-amber-200 bg-amber-50 text-amber-900';
      case 'danger':
        return 'border-rose-200 bg-rose-50 text-rose-900';
      case 'info':
      default:
        return 'border-sky-200 bg-sky-50 text-sky-900';
    }
  }

  eventBadgeClass(evt: RequestEvent): string {
    const statusTo = (evt.status_to || '').toUpperCase();

    if (statusTo === 'DONE') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
    if (statusTo === 'IN_PROGRESS') return 'border-sky-200 bg-sky-50 text-sky-800';
    if (statusTo === 'ASSIGNED') return 'border-indigo-200 bg-indigo-50 text-indigo-800';
    if (statusTo === 'MATCHING') return 'border-amber-200 bg-amber-50 text-amber-800';
    if (statusTo === 'CANCELED') return 'border-rose-200 bg-rose-50 text-rose-800';

    return 'border-slate-200 bg-slate-50 text-slate-800';
  }

  actorName(evt: RequestEvent): string {
    if (!evt.actor) return 'Sistema';
    return `${evt.actor.first_name} ${evt.actor.last_name}`.trim();
  }

  trackById = (_: number, r: ServiceRequest) => r.id;
  trackByNotification = (_: number, n: UiNotification) => n.id;
  trackByEvent = (_: number, e: RequestEvent) => e.id;
}

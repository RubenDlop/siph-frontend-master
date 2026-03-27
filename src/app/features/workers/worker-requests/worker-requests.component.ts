import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs/operators';

import { WorkersService } from '../../../core/services/workers.service';
import { StorageService } from '../../../core/services/storage.service';
import { ReviewsService } from '../../../core/services/reviews.service';

import {
  RequestMessage,
  ServiceRequest,
} from '../../../core/models/service-request';

import {
  RequestReviewSummary,
} from '../../../core/models/review';

type WorkerTab = 'available' | 'mine';

@Component({
  selector: 'app-worker-requests',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './worker-requests.component.html',
  styleUrls: ['./worker-requests.component.scss'],
})
export class WorkerRequestsComponent implements OnInit {
  private workersService = inject(WorkersService);
  private storage = inject(StorageService);
  private reviews = inject(ReviewsService);

  currentUser = this.storage.getUser();

  activeTab: WorkerTab = 'available';

  availableRequests: ServiceRequest[] = [];
  myJobs: ServiceRequest[] = [];

  selectedRequest: ServiceRequest | null = null;
  messages: RequestMessage[] = [];

  reviewSummary: RequestReviewSummary | null = null;
  reviewDraft = {
    rating: 5,
    comment: '',
    saving: false,
    error: '',
  };

  loadingAvailable = false;
  loadingMyJobs = false;
  loadingMessages = false;
  sendingMessage = false;
  actionLoadingId: number | null = null;

  error = '';
  chatError = '';
  messageText = '';

  readonly progressSteps = [
    'Solicitud',
    'Asignada',
    'En progreso',
    'Finalizada',
  ];

  ngOnInit(): void {
    this.loadAll();
  }

  loadAll(): void {
    this.loadAvailableRequests();
    this.loadMyJobs();
  }

  loadAvailableRequests(): void {
    this.loadingAvailable = true;
    this.error = '';

    this.workersService
      .getAvailableRequests()
      .pipe(finalize(() => (this.loadingAvailable = false)))
      .subscribe({
        next: (rows: ServiceRequest[]) => {
          this.availableRequests = rows || [];

          if (
            this.activeTab === 'available' &&
            (!this.selectedRequest ||
              !this.availableRequests.some(
                (r: ServiceRequest) => r.id === this.selectedRequest?.id
              ))
          ) {
            this.selectedRequest = this.availableRequests[0] || null;
            this.loadMessagesIfAllowed();
            this.loadReviewSummaryIfNeeded();
          }
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          this.error =
            err?.error?.detail ||
            'No se pudieron cargar las solicitudes disponibles.';
        },
      });
  }

  loadMyJobs(): void {
    this.loadingMyJobs = true;
    this.error = '';

    this.workersService
      .getMyJobs()
      .pipe(finalize(() => (this.loadingMyJobs = false)))
      .subscribe({
        next: (rows: ServiceRequest[]) => {
          this.myJobs = rows || [];

          if (
            this.activeTab === 'mine' &&
            (!this.selectedRequest ||
              !this.myJobs.some(
                (r: ServiceRequest) => r.id === this.selectedRequest?.id
              ))
          ) {
            this.selectedRequest = this.myJobs[0] || null;
            this.loadMessagesIfAllowed();
            this.loadReviewSummaryIfNeeded();
          }
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          this.error =
            err?.error?.detail || 'No se pudieron cargar tus trabajos.';
        },
      });
  }

  setTab(tab: WorkerTab): void {
    this.activeTab = tab;
    this.selectedRequest =
      tab === 'available'
        ? this.availableRequests[0] || null
        : this.myJobs[0] || null;

    this.loadMessagesIfAllowed();
    this.loadReviewSummaryIfNeeded();
  }

  selectRequest(req: ServiceRequest): void {
    this.selectedRequest = req;
    this.loadMessagesIfAllowed();
    this.loadReviewSummaryIfNeeded();
  }

  loadMessagesIfAllowed(): void {
    this.chatError = '';
    this.messages = [];

    if (!this.selectedRequest) return;
    if (!this.selectedRequest.assigned_worker_id) return;

    this.loadingMessages = true;

    this.workersService
      .getMessages(this.selectedRequest.id)
      .pipe(finalize(() => (this.loadingMessages = false)))
      .subscribe({
        next: (rows: RequestMessage[]) => {
          this.messages = rows || [];
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          this.chatError =
            err?.error?.detail || 'No se pudieron cargar los mensajes.';
        },
      });
  }

  loadReviewSummaryIfNeeded(): void {
    this.reviewSummary = null;
    this.reviewDraft = {
      rating: 5,
      comment: '',
      saving: false,
      error: '',
    };

    if (!this.selectedRequest?.id || this.selectedRequest.status !== 'DONE') return;

    this.reviews.getRequestSummary(this.selectedRequest.id).subscribe({
      next: (summary: RequestReviewSummary) => {
        this.reviewSummary = summary;
        this.reviewDraft.rating = summary.my_review?.rating || 5;
        this.reviewDraft.comment = summary.my_review?.comment || '';
      },
      error: () => {
        this.reviewSummary = null;
      },
    });
  }

  saveWorkerReview(): void {
    if (!this.selectedRequest?.id) return;

    this.reviewDraft.error = '';
    this.reviewDraft.saving = true;

    this.reviews.saveRequestReview(this.selectedRequest.id, {
      rating: this.reviewDraft.rating,
      comment: this.reviewDraft.comment || null,
    }).subscribe({
      next: () => {
        this.reviewDraft.saving = false;
        this.loadReviewSummaryIfNeeded();
        alert('Tu calificación al cliente fue guardada.');
        this.loadMyJobs();
      },
      error: (err) => {
        this.reviewDraft.saving = false;
        this.reviewDraft.error =
          err?.error?.detail || 'No se pudo guardar la calificación.';
      },
    });
  }

  accept(req: ServiceRequest): void {
    if (!req?.id) return;

    this.actionLoadingId = req.id;

    this.workersService
      .acceptRequest(req.id)
      .pipe(finalize(() => (this.actionLoadingId = null)))
      .subscribe({
        next: (updated: ServiceRequest) => {
          this.activeTab = 'mine';
          this.selectedRequest = updated;
          this.loadAvailableRequests();
          this.loadMyJobs();
          this.loadMessagesIfAllowed();
          this.loadReviewSummaryIfNeeded();
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          alert(err?.error?.detail || 'No se pudo aceptar la solicitud.');
        },
      });
  }

  release(req: ServiceRequest): void {
    if (!req?.id) return;

    const ok = window.confirm(
      '¿Seguro que deseas liberar esta solicitud para que otro trabajador pueda tomarla?'
    );
    if (!ok) return;

    this.actionLoadingId = req.id;

    this.workersService
      .releaseRequest(req.id)
      .pipe(finalize(() => (this.actionLoadingId = null)))
      .subscribe({
        next: (_updated: ServiceRequest) => {
          this.selectedRequest = null;
          this.messages = [];
          this.reviewSummary = null;
          this.loadAvailableRequests();
          this.loadMyJobs();
          this.activeTab = 'available';
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          alert(err?.error?.detail || 'No se pudo liberar la solicitud.');
        },
      });
  }

  start(req: ServiceRequest): void {
    if (!req?.id) return;

    this.actionLoadingId = req.id;

    this.workersService
      .startRequest(req.id)
      .pipe(finalize(() => (this.actionLoadingId = null)))
      .subscribe({
        next: (updated: ServiceRequest) => {
          this.replaceMyJob(updated);
          this.selectedRequest = updated;
          this.loadReviewSummaryIfNeeded();
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          alert(err?.error?.detail || 'No se pudo iniciar la solicitud.');
        },
      });
  }

  complete(req: ServiceRequest): void {
    if (!req?.id) return;

    const ok = window.confirm('¿Confirmas que el servicio ya fue completado?');
    if (!ok) return;

    this.actionLoadingId = req.id;

    this.workersService
      .completeRequest(req.id)
      .pipe(finalize(() => (this.actionLoadingId = null)))
      .subscribe({
        next: (updated: ServiceRequest) => {
          this.replaceMyJob(updated);
          this.selectedRequest = updated;
          this.loadReviewSummaryIfNeeded();
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          alert(err?.error?.detail || 'No se pudo finalizar la solicitud.');
        },
      });
  }

  sendMessage(): void {
    const body = (this.messageText || '').trim();
    if (!body || !this.selectedRequest?.id) return;

    if (!this.selectedRequest.assigned_worker_id) {
      alert('Debes aceptar la solicitud antes de usar el chat.');
      return;
    }

    this.sendingMessage = true;
    this.chatError = '';

    this.workersService
      .sendMessage(this.selectedRequest.id, body)
      .pipe(finalize(() => (this.sendingMessage = false)))
      .subscribe({
        next: (msg: RequestMessage) => {
          this.messageText = '';
          this.messages = [...this.messages, msg];
        },
        error: (err: HttpErrorResponse) => {
          console.error(err);
          this.chatError =
            err?.error?.detail || 'No se pudo enviar el mensaje.';
        },
      });
  }

  onMessageKeydown(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      this.sendMessage();
    }
  }

  canAccept(req: ServiceRequest | null): boolean {
    return (
      !!req &&
      !req.assigned_worker_id &&
      ['CREATED', 'MATCHING'].includes(req.status)
    );
  }

  canRelease(req: ServiceRequest | null): boolean {
    return (
      !!req &&
      req.assigned_worker_id === this.currentUser?.id &&
      ['ASSIGNED'].includes(req.status)
    );
  }

  canStart(req: ServiceRequest | null): boolean {
    return (
      !!req &&
      req.assigned_worker_id === this.currentUser?.id &&
      req.status === 'ASSIGNED'
    );
  }

  canComplete(req: ServiceRequest | null): boolean {
    return (
      !!req &&
      req.assigned_worker_id === this.currentUser?.id &&
      req.status === 'IN_PROGRESS'
    );
  }

  statusLabel(status: string | null | undefined): string {
    switch ((status || '').toUpperCase()) {
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
        return status || 'Sin estado';
    }
  }

  statusClass(status: string | null | undefined): string {
    switch ((status || '').toUpperCase()) {
      case 'CREATED':
      case 'MATCHING':
        return 'bg-amber-50 text-amber-700 ring-amber-200';
      case 'ASSIGNED':
        return 'bg-sky-50 text-sky-700 ring-sky-200';
      case 'IN_PROGRESS':
        return 'bg-violet-50 text-violet-700 ring-violet-200';
      case 'DONE':
        return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
      case 'CANCELED':
        return 'bg-rose-50 text-rose-700 ring-rose-200';
      default:
        return 'bg-slate-100 text-slate-700 ring-slate-200';
    }
  }

  urgencyClass(urgency: string | null | undefined): string {
    const value = (urgency || '').toLowerCase();

    if (value.includes('alta') || value.includes('urgente')) {
      return 'bg-rose-50 text-rose-700 ring-rose-200';
    }

    if (value.includes('media')) {
      return 'bg-amber-50 text-amber-700 ring-amber-200';
    }

    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }

  budgetLabel(req: ServiceRequest | null): string {
    if (!req) return 'Sin presupuesto';

    const min = req.budget_min;
    const max = req.budget_max;

    if (!min && !max) return 'Sin presupuesto';

    if (min && max) {
      return `${this.formatCurrency(min)} - ${this.formatCurrency(max)}`;
    }

    return this.formatCurrency(min || max || 0);
  }

  locationLabel(req: ServiceRequest | null): string {
    if (!req) return 'Ubicación no definida';
    return [req.neighborhood, req.city].filter(Boolean).join(', ') || 'Ubicación no definida';
  }

  customerInitials(name: string | null | undefined): string {
    const safe = (name || 'Cliente').trim();
    const parts = safe.split(/\s+/).slice(0, 2);
    return parts.map((p) => p.charAt(0).toUpperCase()).join('');
  }

  contactPreferenceLabel(value: string | null | undefined): string {
    return value || 'No definida';
  }

  get availableCount(): number {
    return this.availableRequests.length;
  }

  get myJobsCount(): number {
    return this.myJobs.length;
  }

  get listLoading(): boolean {
    return this.activeTab === 'available'
      ? this.loadingAvailable
      : this.loadingMyJobs;
  }

  get listToRender(): ServiceRequest[] {
    return this.activeTab === 'available' ? this.availableRequests : this.myJobs;
  }

  get listTitle(): string {
    return this.activeTab === 'available'
      ? 'Solicitudes disponibles'
      : 'Mis servicios';
  }

  get listSubtitle(): string {
    return this.activeTab === 'available'
      ? 'Toma una solicitud y empieza rápido'
      : 'Administra los trabajos que ya aceptaste';
  }

  get emptyTitle(): string {
    return this.activeTab === 'available'
      ? 'No hay solicitudes disponibles'
      : 'Aún no tienes servicios tomados';
  }

  get emptyDescription(): string {
    return this.activeTab === 'available'
      ? 'Cuando aparezcan nuevas solicitudes, las verás aquí.'
      : 'Acepta una solicitud disponible para verla en esta pestaña.';
  }

  get chatEnabled(): boolean {
    return !!this.selectedRequest?.assigned_worker_id;
  }

  get nextActionText(): string {
    const req = this.selectedRequest;
    if (!req) return 'Selecciona una solicitud para comenzar';

    if (this.canAccept(req)) return 'Siguiente paso: aceptar solicitud';
    if (this.canStart(req)) return 'Siguiente paso: iniciar servicio';
    if (this.canComplete(req)) return 'Siguiente paso: finalizar servicio';
    if (this.canRelease(req)) return 'Puedes liberar esta solicitud si no la tomarás';
    if (req.status === 'DONE') return 'Servicio finalizado. Ya puedes calificar al cliente.';
    return 'Revisa los detalles del servicio';
  }

  progressIndex(req: ServiceRequest | null): number {
    const status = (req?.status || '').toUpperCase();

    switch (status) {
      case 'CREATED':
      case 'MATCHING':
        return 0;
      case 'ASSIGNED':
        return 1;
      case 'IN_PROGRESS':
        return 2;
      case 'DONE':
        return 3;
      default:
        return 0;
    }
  }

  isProgressDone(req: ServiceRequest | null, index: number): boolean {
    return this.progressIndex(req) >= index;
  }

  replaceMyJob(updated: ServiceRequest): void {
    const exists = this.myJobs.some((item: ServiceRequest) => item.id === updated.id);

    if (!exists) {
      this.myJobs = [updated, ...this.myJobs];
      return;
    }

    this.myJobs = this.myJobs.map((item: ServiceRequest) =>
      item.id === updated.id ? updated : item
    );
  }

  trackByRequestId(_: number, item: ServiceRequest): number {
    return item.id;
  }

  trackByMessageId(_: number, item: RequestMessage): number {
    return item.id;
  }

  private formatCurrency(value: number): string {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(value);
  }
}

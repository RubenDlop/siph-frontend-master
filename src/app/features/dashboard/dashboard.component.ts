import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError, finalize, map } from 'rxjs/operators';

import { AuthService } from '../../core/services/auth.service';
import { RequestsService } from '../../core/services/requests.service';
import { WorkersService } from '../../core/services/workers.service';
import { ReviewsService } from '../../core/services/reviews.service';

type SlideKpi = {
  label: string;
  value: number | string;
  hint?: string;
  icon: string;
};

type RequestItem = {
  id?: number | string;
  title?: string;
  description?: string;
  status?: string;
  created_at?: string;
};

type VisibleDocument = {
  id?: number | string;
  label?: string;
  has_file?: boolean;
  file_url?: string | null;
  original_name?: string | null;
  content_type?: string | null;
};

type WorkerItem = {
  id?: number | string;
  public_name?: string;
  photo_url?: string | null;
  specialty?: string | null;
  city?: string | null;
  years_experience?: number | null;
  bio?: string | null;
  categories?: string[];
  badge_level?: string | null;
  is_verified?: boolean;
  visible_documents?: VisibleDocument[];
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit {
  private router = inject(Router);

  private auth = inject(AuthService);
  private requests = inject(RequestsService);
  private workers = inject(WorkersService);
  private reviews = inject(ReviewsService);

  loading = true;
  errorMsg = '';

  greetingName = 'Usuario';
  role = 'USER';

  kpis: SlideKpi[] = [
    { label: 'Solicitudes activas', value: 0, hint: 'Pendientes o en proceso', icon: '⚡' },
    { label: 'Finalizadas', value: 0, hint: 'Servicios completados', icon: '✅' },
    { label: 'Reseñas', value: 0, hint: 'Historial de valoraciones', icon: '⭐' },
    { label: 'Expertos sugeridos', value: 0, hint: 'Perfiles visibles', icon: '🧰' },
  ];

  recentRequests: RequestItem[] = [];
  topWorkers: WorkerItem[] = [];

  readonly requestSkeleton = Array.from({ length: 4 });
  readonly workerSkeleton = Array.from({ length: 4 });

  ngOnInit(): void {
    this.loadDashboard();
  }

  loadDashboard(): void {
    this.loading = true;
    this.errorMsg = '';

    try {
      const anyAuth = this.auth as any;
      const u =
        anyAuth?.currentUser ||
        anyAuth?.user ||
        anyAuth?.getUser?.() ||
        null;

      if (u?.first_name) this.greetingName = u.first_name;
      if (u?.role) this.role = u.role;
    } catch {}

    const anyReq = this.requests as any;
    const anyWorkers = this.workers as any;
    const anyReviews = this.reviews as any;

    const myReq$ =
      (anyReq.myRequests?.() ||
        anyReq.getMyRequests?.() ||
        anyReq.listMyRequests?.() ||
        anyReq.getMine?.() ||
        of([])).pipe(
        catchError(() => of([])),
        map((res: any) =>
          Array.isArray(res) ? res : res?.resultado ?? res?.items ?? res?.data ?? []
        )
      );

    const workers$ =
      (anyWorkers.listWorkers?.({}) ||
        anyWorkers.getWorkers?.() ||
        anyWorkers.getAll?.() ||
        of([])).pipe(
        catchError(() => of([])),
        map((res: any) =>
          Array.isArray(res) ? res : res?.resultado ?? res?.items ?? res?.data ?? []
        )
      );

    const reviews$ =
      (anyReviews.myReviews?.() ||
        anyReviews.getMyReviews?.() ||
        anyReviews.listMyReviews?.() ||
        of([])).pipe(
        catchError(() => of([])),
        map((res: any) =>
          Array.isArray(res) ? res : res?.resultado ?? res?.items ?? res?.data ?? []
        )
      );

    forkJoin({
      myReq: myReq$,
      workers: workers$,
      reviews: reviews$,
    })
      .pipe(
        finalize(() => (this.loading = false)),
        catchError(() => {
          this.errorMsg = 'No se pudo cargar el dashboard. Intenta recargar.';
          return of({ myReq: [], workers: [], reviews: [] });
        })
      )
      .subscribe(({ myReq, workers, reviews }: any) => {
        const reqs: RequestItem[] = (myReq ?? []).map((r: any) => ({
          id: r?.id ?? r?._id,
          title: r?.title ?? r?.titulo ?? 'Solicitud',
          description: r?.description ?? r?.descripcion ?? '',
          status: r?.status ?? r?.estado ?? 'CREATED',
          created_at: r?.created_at ?? r?.createdAt ?? '',
        }));

        const wk: WorkerItem[] = (workers ?? []).map((w: any) => ({
          id: w?.id ?? w?._id,
          public_name:
            w?.public_name ||
            `${w?.first_name ?? w?.firstName ?? w?.nombre ?? 'Experto'} ${w?.last_name ?? w?.lastName ?? w?.apellido ?? ''}`.trim(),
          photo_url: w?.photo_url ?? w?.avatar_url ?? w?.avatar ?? null,
          specialty:
            w?.specialty ?? w?.oficio ?? w?.job ?? w?.especialidad ?? 'Servicio del hogar',
          city: w?.city ?? w?.ciudad ?? null,
          years_experience: Number(w?.years_experience ?? w?.jobs_done ?? w?.trabajos ?? 0) || 0,
          bio: w?.bio ?? '',
          categories: this.normalizeStringArray(w?.categories),
          badge_level: w?.badge_level ?? 'BASIC',
          is_verified: !!w?.is_verified,
          visible_documents: Array.isArray(w?.visible_documents) ? w.visible_documents : [],
        }));

        const activeCount = reqs.filter((r) =>
          ['CREATED', 'ASSIGNED', 'IN_PROGRESS', 'ACEPTADA', 'EN_PROCESO', 'ASIGNADA', 'MATCHING'].includes(
            (r.status ?? '').toUpperCase()
          )
        ).length;

        const doneCount = reqs.filter((r) =>
          ['DONE', 'FINISHED', 'FINALIZADA', 'COMPLETED'].includes(
            (r.status ?? '').toUpperCase()
          )
        ).length;

        this.recentRequests = [...reqs]
          .sort((a, b) => this.dateValue(b.created_at) - this.dateValue(a.created_at))
          .slice(0, 5);

        this.topWorkers = [...wk]
          .sort((a, b) => this.workerScore(b) - this.workerScore(a))
          .slice(0, 4);

        this.kpis = [
          { label: 'Solicitudes activas', value: activeCount, hint: 'Pendientes o en proceso', icon: '⚡' },
          { label: 'Finalizadas', value: doneCount, hint: 'Servicios completados', icon: '✅' },
          { label: 'Reseñas', value: Array.isArray(reviews) ? reviews.length : 0, hint: 'Historial de valoraciones', icon: '⭐' },
          { label: 'Expertos sugeridos', value: this.topWorkers.length, hint: 'Perfiles visibles', icon: '🧰' },
        ];
      });
  }

  private normalizeStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value
      .map((item) => String(item ?? '').trim())
      .filter(Boolean);
  }

  private dateValue(value?: string): number {
    if (!value) return 0;
    const t = new Date(value).getTime();
    return Number.isNaN(t) ? 0 : t;
  }

  private badgeWeight(level?: string | null): number {
    switch ((level || '').toUpperCase()) {
      case 'PAY':
        return 40;
      case 'PRO':
        return 28;
      case 'TRUST':
        return 18;
      default:
        return 8;
    }
  }

  private workerScore(worker: WorkerItem): number {
    const verified = worker.is_verified ? 40 : 0;
    const badge = this.badgeWeight(worker.badge_level);
    const docs = Math.min(this.totalDocs(worker) * 6, 24);
    const docsAvailable = Math.min(this.availableDocs(worker) * 8, 24);
    const years = Math.min(Number(worker.years_experience ?? 0), 20);
    const categories = Math.min((worker.categories?.length ?? 0) * 2, 10);
    const photo = worker.photo_url ? 6 : 0;

    return verified + badge + docs + docsAvailable + years + categories + photo;
  }

  go(path: string): void {
    this.router.navigate([path]);
  }

  goWorker(worker: WorkerItem): void {
    if (!worker?.id) {
      this.go('/workers');
      return;
    }

    this.router.navigate(['/workers', worker.id]);
  }

  statusLabel(status?: string): string {
    const v = (status ?? '').toUpperCase();

    if (v === 'CREATED') return 'Creada';
    if (v === 'MATCHING') return 'Buscando técnico';
    if (['ASSIGNED', 'ACEPTADA', 'ASIGNADA'].includes(v)) return 'Asignada';
    if (['IN_PROGRESS', 'EN_PROCESO'].includes(v)) return 'En proceso';
    if (['DONE', 'FINISHED', 'FINALIZADA', 'COMPLETED'].includes(v)) return 'Finalizada';
    if (['CANCELLED', 'CANCELADA', 'CANCELED'].includes(v)) return 'Cancelada';

    return status || '—';
  }

  statusTone(status?: string): string {
    const v = (status ?? '').toUpperCase();

    if (v === 'CREATED') {
      return 'bg-amber-50 text-amber-700 ring-1 ring-amber-200';
    }

    if (v === 'MATCHING') {
      return 'bg-violet-50 text-violet-700 ring-1 ring-violet-200';
    }

    if (['ASSIGNED', 'ACEPTADA', 'ASIGNADA'].includes(v)) {
      return 'bg-sky-50 text-sky-700 ring-1 ring-sky-200';
    }

    if (['IN_PROGRESS', 'EN_PROCESO'].includes(v)) {
      return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200';
    }

    if (['DONE', 'FINISHED', 'FINALIZADA', 'COMPLETED'].includes(v)) {
      return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200';
    }

    if (['CANCELLED', 'CANCELADA', 'CANCELED'].includes(v)) {
      return 'bg-rose-50 text-rose-700 ring-1 ring-rose-200';
    }

    return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200';
  }

  badgeLabel(level?: string | null): string {
    switch ((level || '').toUpperCase()) {
      case 'PAY':
        return 'Elite';
      case 'PRO':
        return 'Pro';
      case 'TRUST':
        return 'Trust';
      default:
        return 'Básico';
    }
  }

  badgeTone(level?: string | null): string {
    switch ((level || '').toUpperCase()) {
      case 'PAY':
        return 'bg-amber-400/95 text-slate-950 ring-1 ring-amber-200 shadow-lg shadow-amber-500/20';
      case 'PRO':
        return 'bg-sky-500/95 text-white ring-1 ring-sky-300/40 shadow-lg shadow-sky-500/20';
      case 'TRUST':
        return 'bg-emerald-500/95 text-white ring-1 ring-emerald-300/40 shadow-lg shadow-emerald-500/20';
      default:
        return 'bg-white/95 text-slate-900 ring-1 ring-white/70 shadow-lg shadow-slate-950/10';
    }
  }

  verificationLabel(worker: WorkerItem | null): string {
    return worker?.is_verified ? 'Verificado' : 'Perfil activo';
  }

  verificationTone(worker: WorkerItem | null): string {
    return worker?.is_verified
      ? 'bg-emerald-500/15 text-emerald-50 ring-1 ring-emerald-300/30 backdrop-blur-md'
      : 'bg-white/15 text-white ring-1 ring-white/20 backdrop-blur-md';
  }

  initials(name?: string | null): string {
    const parts = (name || '').trim().split(/\s+/).filter(Boolean);

    if (!parts.length) return 'T';
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();

    return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
  }

  specialtyLabel(worker: WorkerItem | null): string {
    return worker?.specialty || 'Técnico de servicios del hogar';
  }

  cityLabel(worker: WorkerItem | null): string {
    return worker?.city || 'Ciudad no definida';
  }

  experienceLabel(worker: WorkerItem | null): string {
    const years = Number(worker?.years_experience ?? 0);

    if (!years) {
      return 'Experiencia validada en plataforma';
    }

    return years === 1 ? '1 año de experiencia' : `${years} años de experiencia`;
  }

  safeBio(worker: WorkerItem | null): string {
    const text = (
      worker?.bio ||
      'Perfil profesional visible en SIPH con información pública segura para el usuario.'
    ).trim();

    return text.length > 150 ? `${text.slice(0, 147)}...` : text;
  }

  visibleDocuments(worker: WorkerItem | null): VisibleDocument[] {
    return (worker?.visible_documents || []) as VisibleDocument[];
  }

  totalDocs(worker: WorkerItem | null): number {
    return this.visibleDocuments(worker).length;
  }

  availableDocs(worker: WorkerItem | null): number {
    return this.visibleDocuments(worker).filter((doc) => !!doc.has_file && !!doc.file_url).length;
  }

  previewDocs(worker: WorkerItem | null): string[] {
    return this.visibleDocuments(worker)
      .slice(0, 2)
      .map((doc) => doc.label || 'Documento público');
  }

  extraDocs(worker: WorkerItem | null): number {
    return Math.max(this.totalDocs(worker) - 2, 0);
  }

  topCategories(worker: WorkerItem | null): string[] {
    return (worker?.categories || []).slice(0, 3);
  }

  extraCategories(worker: WorkerItem | null): number {
    return Math.max((worker?.categories?.length || 0) - 3, 0);
  }

  formatRequestDate(value?: string): string {
    if (!value) return 'Fecha no disponible';

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return 'Fecha no disponible';

    return new Intl.DateTimeFormat('es-CO', {
      dateStyle: 'medium',
    }).format(date);
  }

  trackByKpi(index: number, item: SlideKpi): string {
    return `${index}-${item.label}`;
  }

  trackByRequest(_: number, item: RequestItem): number | string {
    return item.id ?? _;
  }

  trackByWorker(_: number, item: WorkerItem): number | string {
    return item.id ?? _;
  }

  trackByDoc(index: number, label: string): string {
    return `${index}-${label}`;
  }
}

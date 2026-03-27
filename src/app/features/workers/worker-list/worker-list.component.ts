import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { WorkersService } from '../../../core/services/workers.service';
import { Worker } from '../../../core/models/worker';

@Component({
  selector: 'app-worker-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './worker-list.component.html',
  styleUrls: ['./worker-list.component.scss'],
})
export class WorkerListComponent implements OnInit {
  private workersService = inject(WorkersService);

  workers: Worker[] = [];
  loading = false;
  error = '';

  search = '';
  city = '';
  selectedCategory = 'all';

  categories: string[] = [];
  readonly stars = [1, 2, 3, 4, 5];

  ngOnInit(): void {
    this.loadWorkers();
  }

  loadWorkers(): void {
    this.loading = true;
    this.error = '';

    this.workersService
      .listWorkers({
        q: this.search || undefined,
        city: this.city || undefined,
        category:
          this.selectedCategory !== 'all' ? this.selectedCategory : undefined,
      })
      .subscribe({
        next: (rows: Worker[]) => {
          this.workers = rows || [];
          this.categories = Array.from(
            new Set(this.workers.flatMap((w: Worker) => w.categories || []))
          ).sort((a, b) => a.localeCompare(b));
          this.loading = false;
        },
        error: (err) => {
          console.error(err);
          this.error =
            err?.error?.detail ||
            'No se pudo cargar el listado de trabajadores.';
          this.loading = false;
        },
      });
  }

  applyFilters(): void {
    this.loadWorkers();
  }

  clearFilters(): void {
    this.search = '';
    this.city = '';
    this.selectedCategory = 'all';
    this.loadWorkers();
  }

  selectCategory(category: string): void {
    this.selectedCategory = category;
    this.loadWorkers();
  }

  badgeLabel(level: string): string {
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

  badgeTone(level: string): string {
    switch ((level || '').toUpperCase()) {
      case 'PAY':
        return 'bg-amber-400/90 text-slate-950 ring-1 ring-amber-200 shadow-lg shadow-amber-500/20';
      case 'PRO':
        return 'bg-sky-500/90 text-white ring-1 ring-sky-300/40 shadow-lg shadow-sky-500/20';
      case 'TRUST':
        return 'bg-emerald-500/90 text-white ring-1 ring-emerald-300/40 shadow-lg shadow-emerald-500/20';
      default:
        return 'bg-white/90 text-slate-900 ring-1 ring-white/60 shadow-lg shadow-slate-950/10';
    }
  }

  verificationLabel(worker: Worker): string {
    return worker.is_verified ? 'Verificado' : 'Perfil activo';
  }

  verificationTone(worker: Worker): string {
    return worker.is_verified
      ? 'bg-emerald-500/15 text-emerald-50 ring-1 ring-emerald-300/30 backdrop-blur-md'
      : 'bg-white/15 text-white ring-1 ring-white/20 backdrop-blur-md';
  }

  initials(name: string): string {
    const parts = (name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return 'T';
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
    return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
  }

  previewDocs(worker: Worker): string[] {
    return (worker.visible_documents || []).slice(0, 3).map((d) => d.label);
  }

  totalDocs(worker: Worker): number {
    return worker.visible_documents?.length || 0;
  }

  extraDocs(worker: Worker): number {
    return Math.max(this.totalDocs(worker) - 3, 0);
  }

  extraCategories(worker: Worker): number {
    return Math.max((worker.categories?.length || 0) - 3, 0);
  }

  specialtyLabel(worker: Worker): string {
    return worker.specialty || 'Especialista en servicios del hogar';
  }

  cityLabel(worker: Worker): string {
    return worker.city || 'Ciudad no definida';
  }

  experienceLabel(worker: Worker): string {
    const years = Number(worker.years_experience ?? 0);

    if (!years) {
      return 'Experiencia validada en plataforma';
    }

    return years === 1
      ? '1 año de experiencia'
      : `${years} años de experiencia`;
  }

  shortBio(worker: Worker): string {
    const text = (
      worker.bio ||
      'Perfil profesional visible en SIPH con información pública segura para el usuario.'
    ).trim();

    return text.length > 180 ? `${text.slice(0, 177)}...` : text;
  }

  publicDocsLabel(worker: Worker): string {
    const total = this.totalDocs(worker);

    if (total === 0) return 'Sin documentos públicos';
    if (total === 1) return '1 documento público';

    return `${total} documentos públicos`;
  }

  averageRating(worker: Worker): number | null {
    const raw = Number(
      (worker as any).average_rating ??
      (worker as any).averageRating ??
      NaN
    );

    return Number.isFinite(raw) && raw > 0 ? raw : null;
  }

  roundedRating(worker: Worker): number {
    const avg = this.averageRating(worker);
    if (avg == null) return 0;
    return Math.max(0, Math.min(5, Math.round(avg)));
  }

  ratingText(worker: Worker): string {
    const avg = this.averageRating(worker);
    return avg == null ? 'Nuevo' : avg.toFixed(1);
  }

  reviewsCount(worker: Worker): number {
    const raw = Number(
      (worker as any).reviews_count ??
      (worker as any).reviewsCount ??
      0
    );

    return Number.isFinite(raw) && raw > 0 ? raw : 0;
  }

  reviewsLabel(worker: Worker): string {
    const total = this.reviewsCount(worker);

    if (total === 0) return 'Sin reseñas aún';
    if (total === 1) return '1 reseña';

    return `${total} reseñas`;
  }

  ratingSummary(worker: Worker): string {
    return this.reviewsCount(worker) > 0
      ? 'Basado en reseñas reales de clientes finalizados.'
      : 'Aún no hay reseñas públicas visibles para este trabajador.';
  }

  get totalWorkers(): number {
    return this.workers.length;
  }

  get verifiedWorkers(): number {
    return this.workers.filter((worker: Worker) => !!worker.is_verified).length;
  }

  get visibleDocumentsCount(): number {
    return this.workers.reduce(
      (acc: number, worker: Worker) =>
        acc + (worker.visible_documents?.length || 0),
      0
    );
  }

  get specialtiesCount(): number {
    return this.categories.length;
  }

  get quickCategories(): string[] {
    return this.categories.slice(0, 8);
  }

  get hasActiveFilters(): boolean {
    return (
      !!this.search.trim() ||
      !!this.city.trim() ||
      this.selectedCategory !== 'all'
    );
  }

  trackByWorker(_: number, worker: Worker): number {
    return worker.id;
  }

  trackByCategory(_: number, category: string): string {
    return category;
  }
}

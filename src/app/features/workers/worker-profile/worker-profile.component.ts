import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { WorkersService } from '../../../core/services/workers.service';
import { Worker } from '../../../core/models/worker';

type ViewerKind = 'pdf' | 'image' | 'other';

type VisibleDocument = {
  id?: number;
  label: string;
  has_file?: boolean;
  file_url?: string | null;
  original_name?: string | null;
  content_type?: string | null;
};

@Component({
  selector: 'app-worker-profile',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './worker-profile.component.html',
  styleUrls: ['./worker-profile.component.scss'],
})
export class WorkerProfileComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private workersService = inject(WorkersService);
  private sanitizer = inject(DomSanitizer);

  worker: Worker | null = null;
  loading = false;
  error = '';

  viewerOpen = false;
  selectedDoc: VisibleDocument | null = null;
  viewerKind: ViewerKind = 'other';
  viewerUrl: string | null = null;
  viewerSafeUrl: SafeResourceUrl | null = null;

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));

    if (!id) {
      this.error = 'Trabajador no válido.';
      return;
    }

    this.loadWorker(id);
  }

  ngOnDestroy(): void {
    document.body.style.overflow = '';
  }

  loadWorker(id: number): void {
    this.loading = true;
    this.error = '';

    this.workersService.getWorker(id).subscribe({
      next: (row: Worker) => {
        this.worker = row;
        this.loading = false;
      },
      error: (err) => {
        console.error(err);
        this.error =
          err?.error?.detail || 'No se pudo cargar el perfil del trabajador.';
        this.loading = false;
      },
    });
  }

  initials(name?: string | null): string {
    const parts = (name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return 'T';
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
    return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
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
        return 'bg-white/90 text-slate-900 ring-1 ring-white/60 shadow-lg shadow-slate-950/10';
    }
  }

  verificationLabel(worker: Worker | null): string {
    return worker?.is_verified ? 'Verificado' : 'Perfil activo';
  }

  verificationTone(worker: Worker | null): string {
    return worker?.is_verified
      ? 'bg-emerald-500/15 text-emerald-50 ring-1 ring-emerald-300/30 backdrop-blur-md'
      : 'bg-white/15 text-white ring-1 ring-white/20 backdrop-blur-md';
  }

  specialtyLabel(worker: Worker | null): string {
    return worker?.specialty || 'Técnico de servicios del hogar';
  }

  cityLabel(worker: Worker | null): string {
    return worker?.city || 'Ciudad no definida';
  }

  experienceLabel(worker: Worker | null): string {
    const years = Number(worker?.years_experience ?? 0);

    if (!years) {
      return 'Experiencia validada en plataforma';
    }

    return years === 1 ? '1 año de experiencia' : `${years} años de experiencia`;
  }

  safeBio(worker: Worker | null): string {
    const text = (worker?.bio || '').trim();

    if (!text) {
      return 'Perfil profesional activo en SIPH con información pública visible y segura para el usuario.';
    }

    return text;
  }

  visibleDocuments(worker: Worker | null): VisibleDocument[] {
    return (worker?.visible_documents || []) as VisibleDocument[];
  }

  totalDocs(worker: Worker | null): number {
    return this.visibleDocuments(worker).length;
  }

  availableDocs(worker: Worker | null): number {
    return this.visibleDocuments(worker).filter((doc) => !!doc.has_file && !!doc.file_url).length;
  }

  unavailableDocs(worker: Worker | null): number {
    return Math.max(this.totalDocs(worker) - this.availableDocs(worker), 0);
  }

  hasCategories(worker: Worker | null): boolean {
    return !!worker?.categories?.length;
  }

  hasVisibleDocs(worker: Worker | null): boolean {
    return this.totalDocs(worker) > 0;
  }

  publicDocName(doc: VisibleDocument): string {
    return doc.original_name || doc.label || 'Documento público';
  }

  publicDocType(doc: VisibleDocument): string {
    return doc.content_type || 'Documento verificado del perfil';
  }

  docStatusLabel(doc: VisibleDocument): string {
    return doc.has_file ? 'Disponible' : 'Sin archivo público';
  }

  docStatusTone(doc: VisibleDocument): string {
    return doc.has_file
      ? 'bg-sky-50 text-sky-700 ring-1 ring-sky-200'
      : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200';
  }

  docIconTone(doc: VisibleDocument): string {
    return doc.has_file
      ? 'bg-emerald-500/10 text-emerald-700 ring-1 ring-emerald-200'
      : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200';
  }

  profileCompletionLabel(worker: Worker | null): string {
    const docs = this.totalDocs(worker);
    const verified = worker?.is_verified ? 1 : 0;
    const categories = worker?.categories?.length ? 1 : 0;
    const photo = worker?.photo_url ? 1 : 0;

    const score = docs > 0 ? 1 : 0;
    const total = verified + categories + photo + score;

    if (total >= 4) return 'Perfil público destacado';
    if (total >= 2) return 'Perfil público sólido';
    return 'Perfil público activo';
  }

  trackByCategory(index: number, category: string): string {
    return `${index}-${category}`;
  }

  trackByDoc(index: number, doc: VisibleDocument): string {
    return `${index}-${doc.id || index}-${doc.label}-${doc.original_name || ''}`;
  }

  canOpenViewer(doc: VisibleDocument): boolean {
    return !!doc.has_file && !!doc.file_url;
  }

  viewerKindFromDoc(doc: VisibleDocument): ViewerKind {
    const ct = (doc.content_type || '').toLowerCase().trim();

    if (ct.includes('pdf')) return 'pdf';
    if (ct.startsWith('image/')) return 'image';

    const url = (doc.file_url || '').toLowerCase();
    if (url.endsWith('.pdf')) return 'pdf';
    if (/\.(png|jpg|jpeg|webp|gif|bmp|svg)$/.test(url)) return 'image';

    return 'other';
  }

  openDocViewer(doc: VisibleDocument): void {
    if (!this.canOpenViewer(doc)) return;

    const url = doc.file_url || null;
    this.selectedDoc = doc;
    this.viewerUrl = url;
    this.viewerKind = this.viewerKindFromDoc(doc);
    this.viewerSafeUrl = url
      ? this.sanitizer.bypassSecurityTrustResourceUrl(url)
      : null;

    this.viewerOpen = true;
    document.body.style.overflow = 'hidden';
  }

  closeDocViewer(): void {
    this.viewerOpen = false;
    this.selectedDoc = null;
    this.viewerKind = 'other';
    this.viewerUrl = null;
    this.viewerSafeUrl = null;
    document.body.style.overflow = '';
  }

  onBackdropClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (target?.classList.contains('doc-viewer-backdrop')) {
      this.closeDocViewer();
    }
  }
}

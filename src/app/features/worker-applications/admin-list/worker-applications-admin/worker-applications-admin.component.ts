import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { forkJoin, of, catchError } from 'rxjs';

import {
  WorkerApplicationService,
  AdminWorkerApplication,
  WorkerAppStatus,
} from '../../../../core/services/worker-application.service';

// UI Components
import { AdminShellComponent } from './ui/admin-shell/admin-shell.component';
import { AdminHeroHeaderComponent } from './ui/admin-hero-header/admin-hero-header.component';
import { AdminAlertsComponent } from './ui/admin-alerts/admin-alerts.component';
import { AdminKpisComponent } from './ui/admin-kpis/admin-kpis.component';
import { AdminToolbarComponent } from './ui/admin-toolbar/admin-toolbar.component';
import { AdminAppsTableComponent } from './ui/admin-apps-table/admin-apps-table.component';

type FilterStatus = WorkerAppStatus | 'ALL';
type Decision = 'APPROVE' | 'REJECT';

@Component({
  selector: 'app-worker-applications-admin',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AdminShellComponent,
    AdminHeroHeaderComponent,
    AdminAlertsComponent,
    AdminKpisComponent,
    AdminToolbarComponent,
    AdminAppsTableComponent,
  ],
  templateUrl: './worker-applications-admin.component.html',
  styleUrl: './worker-applications-admin.component.scss',
})
export class WorkerApplicationsAdminComponent implements OnInit {
  apps: AdminWorkerApplication[] = [];

  loading = false;
  errorMsg = '';
  toastMsg = '';

  statusFilter: FilterStatus = 'ALL';

  notesById: Record<number, string> = {};
  busyById: Record<number, boolean> = {};

  // búsqueda / orden
  searchTerm = '';
  sortKey: 'updated_at' | 'name' | 'status' | 'years_experience' = 'updated_at';
  sortDir: 'asc' | 'desc' = 'desc';

  // selección
  selectedIds = new Set<number>();
  bulkBusy = false;

  constructor(private api: WorkerApplicationService, private router: Router) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.errorMsg = '';
    this.toastMsg = '';

    const status = this.statusFilter === 'ALL' ? undefined : this.statusFilter;

    this.api.adminList(status).subscribe({
      next: (data) => {
        this.apps = data ?? [];

        for (const a of this.apps) {
          if (this.notesById[a.id] == null) {
            this.notesById[a.id] = a.admin_notes ?? '';
          }
        }

        this.selectedIds.clear();
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg =
          err?.error?.detail ||
          'No se pudieron cargar las solicitudes. Revisa el backend y tu sesión.';
      },
    });
  }

  // KPIs
  get counts() {
    const pending = this.apps.filter((a) => a.status === 'PENDING').length;
    const approved = this.apps.filter((a) => a.status === 'APPROVED').length;
    const rejected = this.apps.filter((a) => a.status === 'REJECTED').length;
    return { pending, approved, rejected };
  }

  // listado filtrado/ordenado
  get viewApps(): AdminWorkerApplication[] {
    const q = (this.searchTerm || '').trim().toLowerCase();
    let list = [...(this.apps ?? [])];

    if (q) {
      list = list.filter((a) => {
        const name = this.userName(a).toLowerCase();
        const email = (a.user?.email || '').toLowerCase();
        const city = (a.city || '').toLowerCase();
        const spec = (a.specialty || '').toLowerCase();
        const bio = (a.bio || '').toLowerCase();
        return (
          name.includes(q) ||
          email.includes(q) ||
          city.includes(q) ||
          spec.includes(q) ||
          bio.includes(q)
        );
      });
    }

    const dir = this.sortDir === 'asc' ? 1 : -1;

    list.sort((a, b) => {
      switch (this.sortKey) {
        case 'name':
          return this.userName(a).localeCompare(this.userName(b)) * dir;

        case 'status':
          return ((a.status || '') as string).localeCompare((b.status || '') as string) * dir;

        case 'years_experience':
          return ((a.years_experience ?? 0) - (b.years_experience ?? 0)) * dir;

        default: {
          const da = new Date(a.updated_at).getTime() || 0;
          const db = new Date(b.updated_at).getTime() || 0;
          return (da - db) * dir;
        }
      }
    });

    return list;
  }

  clearSearch(): void {
    this.searchTerm = '';
  }

  toggleSortDir(): void {
    this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
  }

  // selección
  get selectedCount(): number {
    return this.selectedIds.size;
  }

  get isAllSelected(): boolean {
    const ids = this.viewApps.map((a) => a.id);
    return ids.length > 0 && ids.every((id) => this.selectedIds.has(id));
  }

  onToggleSelect(ev: { id: number; checked: boolean }): void {
    if (ev.checked) this.selectedIds.add(ev.id);
    else this.selectedIds.delete(ev.id);
  }

  onToggleSelectAll(checked: boolean): void {
    const ids = this.viewApps.map((a) => a.id);
    if (checked) ids.forEach((id) => this.selectedIds.add(id));
    else ids.forEach((id) => this.selectedIds.delete(id));
  }

  clearSelection(): void {
    this.selectedIds.clear();
  }

  bulkDecide(decision: Decision): void {
    if (this.selectedIds.size === 0) return;

    this.toastMsg = '';
    this.errorMsg = '';
    this.bulkBusy = true;

    const ids = Array.from(this.selectedIds);

    const requests = ids.map((id) => {
      const notes = (this.notesById[id] || '').trim();
      return this.api
        .adminDecide(id, { decision, admin_notes: notes || undefined })
        .pipe(catchError(() => of(null)));
    });

    forkJoin(requests).subscribe({
      next: (results: any[]) => {
        let ok = 0;
        let fail = 0;

        for (const res of results) {
          if (!res) {
            fail++;
            continue;
          }
          ok++;

          const idx = this.apps.findIndex((x) => x.id === res.id);
          if (idx >= 0) this.apps[idx] = res;

          this.notesById[res.id] = res.admin_notes ?? this.notesById[res.id] ?? '';
          this.selectedIds.delete(res.id);
        }

        this.bulkBusy = false;

        if (fail > 0) {
          this.errorMsg = `Algunas acciones fallaron (${fail}). Las demás se aplicaron (${ok}).`;
        } else {
          this.toastMsg =
            decision === 'APPROVE'
              ? `✅ Lote aprobado (${ok}).`
              : `✅ Lote rechazado (${ok}).`;
        }
      },
      error: () => {
        this.bulkBusy = false;
        this.errorMsg = 'No se pudo procesar el lote.';
      },
    });
  }

  decide(app: AdminWorkerApplication, decision: Decision): void {
    if (!app?.id) return;

    this.toastMsg = '';
    this.errorMsg = '';
    this.busyById[app.id] = true;

    const notes = (this.notesById[app.id] || '').trim();

    this.api.adminDecide(app.id, { decision, admin_notes: notes || undefined }).subscribe({
      next: (updated) => {
        const idx = this.apps.findIndex((x) => x.id === app.id);
        if (idx >= 0) this.apps[idx] = updated;

        this.notesById[app.id] = updated.admin_notes ?? notes ?? '';
        this.busyById[app.id] = false;

        this.toastMsg =
          decision === 'APPROVE'
            ? '✅ Solicitud aprobada (el usuario pasa a WORKER).'
            : '✅ Solicitud rechazada.';
      },
      error: (err) => {
        this.busyById[app.id] = false;
        this.errorMsg =
          err?.error?.detail ||
          'No se pudo tomar la decisión. Verifica permisos y el endpoint.';
      },
    });
  }

  // ✅ FIX RUTA: según app.routes.ts -> /admin/worker-applications/:id
  goDetail(app: AdminWorkerApplication): void {
    if (!app?.id) return;
    this.router.navigate(['/admin/worker-applications', app.id]);
  }

  // util
  copyEmail(email?: string): void {
    if (!email) return;

    const okToast = () => {
      this.toastMsg = `📋 Email copiado: ${email}`;
      setTimeout(() => (this.toastMsg = ''), 1800);
    };

    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(email).then(okToast).catch(() => {
        this.fallbackCopy(email);
        okToast();
      });
      return;
    }

    this.fallbackCopy(email);
    okToast();
  }

  private fallbackCopy(text: string) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
    } finally {
      document.body.removeChild(ta);
    }
  }

  userName(app: AdminWorkerApplication): string {
    const u: any = app?.user ?? {};
    const fn = (u.first_name ?? u.firstName ?? '').toString().trim();
    const ln = (u.last_name ?? u.lastName ?? '').toString().trim();
    const full = `${fn} ${ln}`.trim();
    return full || (u.email ?? 'Usuario');
  }
}

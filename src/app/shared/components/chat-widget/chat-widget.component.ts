import { CommonModule } from '@angular/common';
import { Component, HostListener, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';

import { StorageService } from '../../../core/services/storage.service';

@Component({
  selector: 'app-chat-widget',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './chat-widget.component.html',
  styleUrl: './chat-widget.component.scss',
})
export class ChatWidgetComponent {
  private sanitizer = inject(DomSanitizer);
  private storage = inject(StorageService);
  private router = inject(Router);

  /** ✅ PON AQUÍ TU URL REAL DE GRADIO
   *  - Si tienes proxy: usa '/ai-local'
   *  - Si NO tienes proxy: usa 'http://127.0.0.1:7860'
   */
  gradioUrl = 'http://127.0.0.1:7860';

  open = false;
  safeUrl: SafeResourceUrl | null = null;

  // Para ocultarlo en /auth (opcional)
  hideFab = false;

  constructor() {
    // Si quieres ocultar el botón en login/register:
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        const url = e.urlAfterRedirects || '';
        this.hideFab = url.startsWith('/auth/');
        // Si navega y estaba abierto, ciérralo (opcional)
        // if (this.open) this.close();
      });
  }

  get isLoggedIn(): boolean {
    return !!this.storage.getToken();
  }

  get userName(): string {
    const u = this.storage.getUser();
    const full = [u?.first_name, u?.last_name].filter(Boolean).join(' ').trim();
    return full || 'Usuario';
  }

  get userRole(): string {
    return this.storage.getUser()?.role || 'USER';
  }

  get initials(): string {
    const name = this.userName.trim();
    if (!name) return 'AI';
    const parts = name.split(' ').filter(Boolean);
    const a = parts[0]?.[0] || 'A';
    const b = parts[1]?.[0] || 'I';
    return (a + b).toUpperCase();
  }

  toggle() {
    if (this.open) this.close();
    else this.openPanel();
  }

  openPanel() {
    // Si quieres obligar login:
    // if (!this.isLoggedIn) { this.router.navigate(['/auth/login']); return; }

    // ✅ OJO: aquí NO cargamos /assistant (Angular). Cargamos Gradio directamente.
    const url = this.gradioUrl; // puedes agregar ?__theme=dark si quieres
    this.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
    this.open = true;

    // bloquea scroll del body
    document.documentElement.classList.add('cw-lock');
    document.body.classList.add('cw-lock');
  }

  close() {
    this.open = false;
    this.safeUrl = null;

    document.documentElement.classList.remove('cw-lock');
    document.body.classList.remove('cw-lock');
  }

  closeOnBackdrop(ev: MouseEvent) {
    // cerrar solo si das click en el fondo (no en el panel)
    const target = ev.target as HTMLElement;
    if (target?.classList?.contains('cw-overlay')) this.close();
  }

  openNewTab() {
    window.open(this.gradioUrl, '_blank', 'noopener,noreferrer');
  }

  @HostListener('document:keydown.escape')
  onEsc() {
    if (this.open) this.close();
  }
}

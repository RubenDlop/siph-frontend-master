import { CommonModule, isPlatformBrowser } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  PLATFORM_ID,
  ViewChild,
  inject,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AuthService } from '../../../core/services/auth.service';
import { AuthUser } from '../../../core/services/storage.service';
import { environment } from '../../../../environments/environment';

type Slide = { src: string; title: string; subtitle: string };

declare global {
  interface Window {
    google?: any;
  }
}

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements AfterViewInit, OnDestroy {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private auth = inject(AuthService);
  private platformId = inject(PLATFORM_ID);

  @ViewChild('gsiBtn', { static: false }) gsiBtn?: ElementRef<HTMLDivElement>;

  loading = false;
  errorMsg = '';
  showPass = false;
  year = new Date().getFullYear();

  googleReady = false;
  private googleClientId = '';
  private gsiRendered = false;

  private azureInProgress = false;
  private timer: any = null;

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  get f() {
    return this.form.controls;
  }

  slides: Slide[] = [
    {
      src: 'assets/siph_carousel_1.png',
      title: 'Encuentra expertos verificados',
      subtitle: 'Perfiles, reseñas y disponibilidad real.',
    },
    {
      src: 'assets/siph_carousel_2.png',
      title: 'Solicita un servicio en minutos',
      subtitle: 'Publica tu necesidad y recibe propuestas.',
    },
    {
      src: 'assets/siph_carousel_3.png',
      title: 'Seguimiento claro del servicio',
      subtitle: 'Estados en tiempo real y trazabilidad.',
    },
    {
      src: 'assets/siph_carousel_4.png',
      title: 'Califica y mejora la confianza',
      subtitle: 'Reseñas para tomar mejores decisiones.',
    },
  ];

  active = 0;

  get currentSlide(): Slide {
    return this.slides[this.active] ?? this.slides[0];
  }

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.timer = setInterval(() => this.next(), 5500);
    this.initGoogle();
    this.auth.initMicrosoftSession();
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  goTo(i: number) {
    this.active = i;
    this.resetTimer();
  }

  next() {
    this.active = (this.active + 1) % this.slides.length;
  }

  private resetTimer() {
    if (!isPlatformBrowser(this.platformId)) return;
    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(() => this.next(), 5500);
  }

  private navigateAfterLogin(user: AuthUser) {
    const redirect = this.route.snapshot.queryParamMap.get('redirect');
    if (redirect) {
      this.router.navigateByUrl(redirect);
      return;
    }

    const role = (user?.role || 'USER').toUpperCase();

    if (role === 'ADMIN') {
      this.router.navigateByUrl('/admin/worker-applications');
      return;
    }

    if (role === 'WORKER') {
      this.router.navigateByUrl('/dashboard');
      return;
    }

    this.router.navigateByUrl('/dashboard');
  }

  submit() {
    if (this.loading) return;

    this.errorMsg = '';

    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;

    const payload = {
      email: this.f.email.value!.trim().toLowerCase(),
      password: this.f.password.value!,
    };

    this.auth.login(payload).subscribe({
      next: (user) => {
        this.loading = false;
        this.navigateAfterLogin(user);
      },
      error: (err: any) => {
        this.loading = false;
        this.errorMsg =
          err?.error?.detail ||
          err?.error?.message ||
          err?.message ||
          'No se pudo iniciar sesión. Verifica tus credenciales.';
      },
    });
  }

  loginAzure() {
    if (this.loading || this.azureInProgress) return;

    this.loading = true;
    this.azureInProgress = true;
    this.errorMsg = '';

    this.auth.loginWithAzure().subscribe({
      next: (user) => {
        this.loading = false;
        this.azureInProgress = false;
        this.navigateAfterLogin(user);
      },
      error: (err: any) => {
        this.loading = false;
        this.azureInProgress = false;

        const rawMessage =
          err?.error?.detail ||
          err?.error?.message ||
          err?.message ||
          'No se pudo iniciar con Microsoft. Intenta de nuevo.';

        if (String(rawMessage).includes('interaction_in_progress')) {
          this.errorMsg =
            'Ya hay un inicio de sesión de Microsoft en curso. Espera unos segundos y vuelve a intentarlo.';
          return;
        }

        this.errorMsg = rawMessage;
      },
    });
  }

  private getClientId(): string {
    return (
      (environment as any).googleClientId ||
      (environment as any).google_client_id ||
      (environment as any).GOOGLE_CLIENT_ID ||
      ''
    );
  }

  private async initGoogle() {
    const clientId = this.getClientId();

    if (!clientId) {
      this.googleReady = false;
      return;
    }

    this.googleClientId = clientId;

    try {
      await this.loadGoogleScript();
    } catch {
      this.googleReady = false;
      return;
    }

    const google = window.google;
    if (!google?.accounts?.id) {
      this.googleReady = false;
      return;
    }

    google.accounts.id.initialize({
      client_id: this.googleClientId,
      callback: (resp: any) => this.onGoogleCredential(resp),
      ux_mode: 'popup',
      auto_select: false,
      cancel_on_tap_outside: true,
    });

    this.googleReady = true;
    this.renderGoogleButtonSafe();
  }

  private renderGoogleButtonSafe() {
    if (!isPlatformBrowser(this.platformId)) return;
    if (!this.googleReady) return;
    if (this.gsiRendered) return;

    if (!this.gsiBtn?.nativeElement) {
      setTimeout(() => this.renderGoogleButtonSafe(), 0);
      return;
    }

    const google = window.google;
    if (!google?.accounts?.id?.renderButton) return;

    this.gsiBtn.nativeElement.innerHTML = '';

    google.accounts.id.renderButton(this.gsiBtn.nativeElement, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'continue_with',
      shape: 'pill',
      width: Math.min(380, this.gsiBtn.nativeElement.clientWidth || 380),
      locale: 'es',
    });

    this.gsiRendered = true;
  }

  private loadGoogleScript(): Promise<void> {
    return new Promise((resolve, reject) => {
      const id = 'google-gsi';

      if (document.getElementById(id)) {
        resolve();
        return;
      }

      const s = document.createElement('script');
      s.id = id;
      s.src = 'https://accounts.google.com/gsi/client';
      s.async = true;
      s.defer = true;
      s.onload = () => resolve();
      s.onerror = () => reject();
      document.head.appendChild(s);
    });
  }

  private onGoogleCredential(resp: any) {
    if (this.loading) return;

    const credential = resp?.credential;

    if (!credential) {
      this.errorMsg =
        'No se pudo obtener el token de Google. Intenta nuevamente.';
      return;
    }

    this.loading = true;
    this.errorMsg = '';

    this.auth.loginWithGoogle(credential).subscribe({
      next: (user) => {
        this.loading = false;
        this.navigateAfterLogin(user);
      },
      error: (err: any) => {
        this.loading = false;
        this.errorMsg =
          err?.error?.detail ||
          err?.error?.message ||
          err?.message ||
          'No se pudo iniciar con Google. Intenta de nuevo.';
      },
    });
  }
}

import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';

import { NavbarComponent } from './shared/components/navbar/navbar.component';
import { FooterComponent } from './shared/components/footer/footer.component';
import { ChatWidgetComponent } from './shared/components/chat-widget/chat-widget.component';

import { AuthService } from './core/services/auth.service';
import { AuthUser } from './core/services/storage.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    NavbarComponent,
    FooterComponent,
    ChatWidgetComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private auth = inject(AuthService);
  private router = inject(Router);

  async ngOnInit(): Promise<void> {
    try {
      const user = await this.auth.completeAzureRedirectIfNeeded();
      if (user) {
        this.navigateByRole(user);
      }
    } catch (error) {
      console.error('Error completando login de Microsoft:', error);
    }
  }

  private navigateByRole(user: AuthUser): void {
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
}

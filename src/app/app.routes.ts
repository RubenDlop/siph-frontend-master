import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  // ✅ HOME (Landing)
  {
    path: '',
    loadComponent: () =>
      import('./features/home/home.component').then((m) => m.HomeComponent),
  },

  // ✅ DASHBOARD
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then(
        (m) => m.DashboardComponent
      ),
  },

  // ✅ AUTH
  {
    path: 'auth/login',
    loadComponent: () =>
      import('./features/auth/login/login.component').then(
        (m) => m.LoginComponent
      ),
  },
  {
    path: 'auth/register',
    loadComponent: () =>
      import('./features/auth/register/register.component').then(
        (m) => m.RegisterComponent
      ),
  },

  // ✅ Alias
  { path: 'login', redirectTo: 'auth/login', pathMatch: 'full' },
  { path: 'register', redirectTo: 'auth/register', pathMatch: 'full' },

  // ✅ Workers (listado / perfil público)
  {
    path: 'workers',
    loadComponent: () =>
      import('./features/workers/worker-list/worker-list.component').then(
        (m) => m.WorkerListComponent
      ),
  },
  {
    path: 'workers/:id',
    loadComponent: () =>
      import('./features/workers/worker-profile/worker-profile.component').then(
        (m) => m.WorkerProfileComponent
      ),
  },

  // ✅ Requests
  {
    path: 'requests/new',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/requests/request-create/request-create.component').then(
        (m) => m.RequestCreateComponent
      ),
  },
  {
    path: 'my-requests',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/requests/my-requests/my-requests.component').then(
        (m) => m.MyRequestsComponent
      ),
  },

  // ✅ Reviews
  {
    path: 'reviews',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/reviews/review-list/review-list.component').then(
        (m) => m.ReviewListComponent
      ),
  },

  // ✅ 🤖 Asistente IA Local (Gradio) - pantalla completa (opcional)
  // URL: /assistant
  {
    path: 'assistant',
    canActivate: [authGuard], // ✅ quita authGuard si lo quieres público
    loadComponent: () =>
      import('./features/assistant/assistant.component').then(
        (m) => m.AssistantComponent
      ),
  },

  // ✅ 👷‍♂️ Solicitud para trabajar como Técnico (SOLO USER)
  {
    path: 'work/apply',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['USER'] },
    loadComponent: () =>
      import(
        './features/worker-applications/apply/worker-apply/worker-apply.component'
      ).then((m) => m.WorkerApplyComponent),
  },

  // ✅ 🛡️ Admin: revisar solicitudes (SOLO ADMIN)
  // ✅ LISTADO: /admin/worker-applications
  // ✅ DETALLE FULL: /admin/worker-applications/:id
  {
    path: 'admin/worker-applications',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMIN'] },
    children: [
      {
        path: '',
        loadComponent: () =>
          import(
            './features/worker-applications/admin-list/worker-applications-admin/worker-applications-admin.component'
          ).then((m) => m.WorkerApplicationsAdminComponent),
      },
      {
        path: ':id',
        loadComponent: () =>
          import(
            './features/worker-applications/admin-detail/worker-application-admin-detail/worker-application-admin-detail.component'
          ).then((m) => m.WorkerApplicationAdminDetailComponent),
      },
    ],
  },

  // ✅ Not Found
  {
    path: '**',
    loadComponent: () =>
      import('./shared/components/not-found/not-found.component').then(
        (m) => m.NotFoundComponent
      ),
  },
];

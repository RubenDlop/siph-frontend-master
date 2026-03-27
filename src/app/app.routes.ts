import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/home/home.component').then((m) => m.HomeComponent),
  },

  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then(
        (m) => m.DashboardComponent
      ),
  },

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

  { path: 'login', redirectTo: 'auth/login', pathMatch: 'full' },
  { path: 'register', redirectTo: 'auth/register', pathMatch: 'full' },

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

  {
    path: 'worker/requests',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['WORKER', 'ADMIN'] },
    loadComponent: () =>
      import('./features/workers/worker-requests/worker-requests.component').then(
        (m) => m.WorkerRequestsComponent
      ),
  },

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

  {
    path: 'reviews',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/reviews/review-list/review-list.component').then(
        (m) => m.ReviewListComponent
      ),
  },

  {
    path: 'assistant',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/assistant/assistant.component').then(
        (m) => m.AssistantComponent
      ),
  },

  {
    path: 'work/apply',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['USER'] },
    loadComponent: () =>
      import(
        './features/worker-applications/apply/worker-apply/worker-apply.component'
      ).then((m) => m.WorkerApplyComponent),
  },

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

  {
    path: '**',
    loadComponent: () =>
      import('./shared/components/not-found/not-found.component').then(
        (m) => m.NotFoundComponent
      ),
  },
];

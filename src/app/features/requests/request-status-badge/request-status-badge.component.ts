import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RequestStatus } from '../../../core/models/service-request';

@Component({
  selector: 'app-request-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="badge" [class]="statusClass(status)">
      {{ label(status) }}
    </span>
  `,
  styleUrl: './request-status-badge.component.scss',
})
export class RequestStatusBadgeComponent {
  @Input({ required: true }) status!: RequestStatus;

  label(s: RequestStatus) {
    const m: Record<RequestStatus, string> = {
      CREATED: 'Creada',
      MATCHING: 'Buscando técnico',
      ASSIGNED: 'Asignada',
      IN_PROGRESS: 'En progreso',
      DONE: 'Finalizada',
      CANCELED: 'Cancelada',
    };
    return m[s] ?? s;
  }

  statusClass(s: RequestStatus) {
    const m: Record<RequestStatus, string> = {
      CREATED: 'b-created',
      MATCHING: 'b-matching',
      ASSIGNED: 'b-assigned',
      IN_PROGRESS: 'b-progress',
      DONE: 'b-done',
      CANCELED: 'b-canceled',
    };
    return m[s] ?? 'b-created';
  }
}
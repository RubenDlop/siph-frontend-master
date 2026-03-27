import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { ReviewsService } from '../../../core/services/reviews.service';

type PublicReviewApiItem = {
  id: number;
  rating: number;
  comment?: string | null;
  created_at: string;
  reviewer?: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    role: string;
    is_active: boolean;
  } | null;
};

type ReviewCard = {
  id: number;
  rating: number;
  comment: string;
  created_at: string;
  reviewer_name: string;
  reviewer_initials: string;
  reviewer_role: string;
  relative_time: string;
};

@Component({
  selector: 'app-review-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './review-list.component.html',
  styleUrls: ['./review-list.component.scss'],
})
export class ReviewListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private reviewsService = inject(ReviewsService);

  loading = true;
  error = '';
  demoMode = false;

  workerId: number | null = null;
  averageRating: number | null = null;
  reviewsCount = 0;

  reviews: ReviewCard[] = [];
  columnA: ReviewCard[] = [];
  columnB: ReviewCard[] = [];
  columnC: ReviewCard[] = [];

  readonly stars = [1, 2, 3, 4, 5];

  ngOnInit(): void {
    const qpId = Number(this.route.snapshot.queryParamMap.get('workerId'));
    const rpId = Number(this.route.snapshot.paramMap.get('id'));

    this.workerId = Number.isFinite(qpId) && qpId > 0
      ? qpId
      : Number.isFinite(rpId) && rpId > 0
      ? rpId
      : null;

    if (this.workerId) {
      this.loadRealReviews(this.workerId);
    } else {
      this.loadDemoReviews();
    }
  }

  loadRealReviews(workerId: number): void {
    this.loading = true;
    this.error = '';
    this.demoMode = false;

    this.reviewsService.getPublicWorkerReviews(workerId).subscribe({
      next: (res) => {
        this.averageRating = res?.average_rating ?? null;
        this.reviewsCount = res?.reviews_count ?? 0;

        const rows = (res?.items || []).map((item) => this.mapReview(item));
        this.reviews = rows;

        this.buildColumns(rows);
        this.loading = false;

        if (!rows.length) {
          this.error = '';
        }
      },
      error: (err) => {
        console.error(err);
        this.loading = false;
        this.error =
          err?.error?.detail || 'No se pudieron cargar las reseñas públicas.';
      },
    });
  }

  loadDemoReviews(): void {
    this.loading = false;
    this.error = '';
    this.demoMode = true;

    const now = new Date().toISOString();

    const demo: ReviewCard[] = [
      this.mapReview({
        id: 1,
        rating: 5,
        comment:
          'Excelente servicio. Llegó puntual, explicó todo muy claro y dejó el trabajo impecable.',
        created_at: now,
        reviewer: {
          id: 101,
          first_name: 'Laura',
          last_name: 'Gómez',
          email: 'laura@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
      this.mapReview({
        id: 2,
        rating: 5,
        comment:
          'Muy profesional. Se notaba la experiencia y además fue muy respetuoso en todo momento.',
        created_at: now,
        reviewer: {
          id: 102,
          first_name: 'Carlos',
          last_name: 'Mendoza',
          email: 'carlos@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
      this.mapReview({
        id: 3,
        rating: 4,
        comment:
          'Buen trabajo y buena actitud. Me gustó que fue transparente con el costo.',
        created_at: now,
        reviewer: {
          id: 103,
          first_name: 'Andrea',
          last_name: 'Pérez',
          email: 'andrea@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
      this.mapReview({
        id: 4,
        rating: 5,
        comment:
          'Recomiendo totalmente. Resolvió rápido y el resultado quedó muy bien.',
        created_at: now,
        reviewer: {
          id: 104,
          first_name: 'Jhon',
          last_name: 'Rojas',
          email: 'jhon@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
      this.mapReview({
        id: 5,
        rating: 5,
        comment:
          'Muy confiable. Se comunicó bien antes de llegar y cumplió exactamente con lo acordado.',
        created_at: now,
        reviewer: {
          id: 105,
          first_name: 'María',
          last_name: 'Torres',
          email: 'maria@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
      this.mapReview({
        id: 6,
        rating: 4,
        comment:
          'Quedé satisfecho con el servicio. Seguramente volvería a contratarlo.',
        created_at: now,
        reviewer: {
          id: 106,
          first_name: 'Diego',
          last_name: 'Ramírez',
          email: 'diego@example.com',
          role: 'USER',
          is_active: true,
        },
      }),
    ];

    this.averageRating = 4.8;
    this.reviewsCount = demo.length;
    this.reviews = demo;
    this.buildColumns(demo);
  }

  private mapReview(item: PublicReviewApiItem): ReviewCard {
    const firstName = item?.reviewer?.first_name || 'Usuario';
    const lastName = item?.reviewer?.last_name || '';
    const reviewerName = `${firstName} ${lastName}`.trim();
    const initials = `${firstName.charAt(0)}${lastName.charAt(0) || ''}`.toUpperCase();

    return {
      id: item.id,
      rating: item.rating,
      comment: item.comment?.trim() || 'El usuario dejó una calificación positiva.',
      created_at: item.created_at,
      reviewer_name: reviewerName,
      reviewer_initials: initials || 'U',
      reviewer_role: item?.reviewer?.role || 'USER',
      relative_time: this.formatRelative(item.created_at),
    };
  }

  private buildColumns(rows: ReviewCard[]): void {
    const a: ReviewCard[] = [];
    const b: ReviewCard[] = [];
    const c: ReviewCard[] = [];

    rows.forEach((item, index) => {
      if (index % 3 === 0) a.push(item);
      else if (index % 3 === 1) b.push(item);
      else c.push(item);
    });

    this.columnA = a.length ? a : rows.slice(0, Math.ceil(rows.length / 2));
    this.columnB = b.length ? b : rows.slice(0, Math.ceil(rows.length / 2));
    this.columnC = c.length ? c : rows.slice(0, Math.ceil(rows.length / 2));
  }

  fullStars(rating: number): number[] {
    return Array.from({ length: rating }, (_, i) => i + 1);
  }

  emptyStars(rating: number): number[] {
    return Array.from({ length: 5 - rating }, (_, i) => i + 1);
  }

  trackByReview(_: number, item: ReviewCard): number {
    return item.id;
  }

  private formatRelative(value: string): string {
    const date = new Date(value);
    const now = new Date();

    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return 'Hace un momento';
    if (diffMin < 60) return `Hace ${diffMin} min`;
    if (diffHour < 24) return `Hace ${diffHour} h`;
    if (diffDay < 30) return `Hace ${diffDay} días`;

    return date.toLocaleDateString('es-CO', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }
}

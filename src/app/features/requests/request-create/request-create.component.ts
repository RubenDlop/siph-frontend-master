// src/app/features/requests/request-create/request-create.component.ts
import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import * as L from 'leaflet';

import { RequestsService } from '../../../core/services/requests.service';
import { ServiceRequestCreate } from '../../../core/models/service-request';

@Component({
  selector: 'app-request-create',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './request-create.component.html',
  styleUrl: './request-create.component.scss',
})
export class RequestCreateComponent implements AfterViewInit, OnDestroy {
  @ViewChild('mapEl') mapEl?: ElementRef<HTMLDivElement>;

  loading = false;
  errorMsg = '';
  successMsg = '';

  // ✅ UX: autocompletar desde mapa
  autoFillAddress = true;
  addressTouched = false;
  geoBusy = false;

  form: ServiceRequestCreate = {
    category: 'GENERAL',
    title: '',
    description: '',
    urgency: 'NORMAL',

    city: null,
    neighborhood: null,
    address: null,
    address_ref: null,

    lat: null,
    lng: null,
    accuracy_m: null,

    schedule_date: null,
    time_window: 'FLEXIBLE',

    budget_min: null,
    budget_max: null,

    contact_name: null,
    contact_phone: null,
    contact_pref: 'WHATSAPP',
  };

  private map?: L.Map;
  private marker?: L.Marker;

  private defaultCenter: L.LatLngExpression = [10.9639, -74.7964];

  private revTimer: any = null;
  private ro?: ResizeObserver;

  constructor(private requests: RequestsService, private router: Router) {}

  ngAfterViewInit(): void {
    // ✅ Espera a que el DOM y layout estén listos
    setTimeout(() => this.initMap(), 0);
  }

  ngOnDestroy(): void {
    try {
      this.map?.off();
      this.map?.remove();
    } catch {}

    this.map = undefined;
    this.marker = undefined;

    if (this.revTimer) clearTimeout(this.revTimer);
    this.ro?.disconnect();
    this.ro = undefined;
  }

  canSubmit(): boolean {
    const title = (this.form.title ?? '').trim();
    const desc = (this.form.description ?? '').trim();
    const hasGeo = this.form.lat != null && this.form.lng != null;
    return title.length >= 3 && desc.length >= 10 && hasGeo && !this.loading;
  }

  onAddressManualChange() {
    this.addressTouched = true;
  }

  enableAutoFill() {
    this.addressTouched = false;
    this.autoFillAddress = true;
    if (this.form.lat != null && this.form.lng != null) {
      this.queueReverseGeocode(this.form.lat, this.form.lng);
    }
  }

  private clean(v: any): string | null {
    if (v === null || v === undefined) return null;
    const s = String(v).trim();
    return s.length ? s : null;
  }

  private initMap() {
    const el = this.mapEl?.nativeElement;

    if (!el) {
      console.error('[Leaflet] No se encontró el contenedor del mapa (#mapEl).');
      return;
    }

    // ✅ Limpia por si Angular re-render/hmr
    try {
      this.map?.off();
      this.map?.remove();
    } catch {}
    this.map = undefined;
    this.marker = undefined;

    // ✅ Icono default (sin importar PNGs locales)
    const DefaultIcon = L.icon({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
    });
    (L.Marker.prototype as any).options.icon = DefaultIcon;

    const map = L.map(el, { zoomControl: true }).setView(this.defaultCenter, 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    map.on('click', (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      this.setPoint(lat, lng, null);
    });

    this.map = map;

    // ✅ Anti “mapa blanco” por resize/layout/sticky
    map.whenReady(() => map.invalidateSize(true));
    setTimeout(() => map.invalidateSize(true), 50);
    setTimeout(() => map.invalidateSize(true), 250);

    // ✅ Observa cambios de tamaño del contenedor (SOLUCIÓN PRO)
    this.ro?.disconnect();
    this.ro = new ResizeObserver(() => {
      this.map?.invalidateSize(true);
    });
    this.ro.observe(el);

    // Si ya hay coords
    if (this.form.lat != null && this.form.lng != null) {
      this.setPoint(this.form.lat, this.form.lng, this.form.accuracy_m ?? null, true);
      setTimeout(() => this.map?.invalidateSize(true), 50);
    }
  }

  private setPoint(lat: number, lng: number, accuracy: number | null, keepZoom = false) {
    this.form.lat = Number(lat.toFixed(6));
    this.form.lng = Number(lng.toFixed(6));
    this.form.accuracy_m = accuracy != null ? Math.round(accuracy) : null;

    const ll: L.LatLngExpression = [lat, lng];

    if (!this.marker) {
      this.marker = L.marker(ll, { draggable: true }).addTo(this.map!);
      this.marker.on('dragend', () => {
        const p = this.marker!.getLatLng();
        this.setPoint(p.lat, p.lng, this.form.accuracy_m ?? null, true);
      });
    } else {
      this.marker.setLatLng(ll);
    }

    if (!keepZoom) this.map?.setView(ll, 16);
    setTimeout(() => this.map?.invalidateSize(true), 0);

    if (this.autoFillAddress && !this.addressTouched) {
      this.queueReverseGeocode(this.form.lat!, this.form.lng!);
    }
  }

  private queueReverseGeocode(lat: number, lng: number) {
    if (this.revTimer) clearTimeout(this.revTimer);
    this.revTimer = setTimeout(() => this.reverseFillFromPin(lat, lng), 450);
  }

  private async reverseFillFromPin(lat: number, lng: number) {
    if (!this.autoFillAddress || this.addressTouched) return;

    try {
      this.geoBusy = true;
      const info = await this.reverseGeocode(lat, lng);
      if (!info) return;

      this.form.city = this.form.city ?? info.city ?? null;
      this.form.neighborhood = this.form.neighborhood ?? info.neighborhood ?? null;
      this.form.address = this.form.address ?? info.address ?? null;
    } catch (e) {
      console.warn('[Geocode] reverse failed', e);
    } finally {
      this.geoBusy = false;
    }
  }

  private async reverseGeocode(
    lat: number,
    lng: number
  ): Promise<{ city: string | null; neighborhood: string | null; address: string | null } | null> {
    const url =
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(String(lat))}&lon=${encodeURIComponent(String(lng))}&addressdetails=1`;

    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      referrerPolicy: 'no-referrer',
    });

    if (!res.ok) return null;
    const data: any = await res.json();
    const a = data?.address ?? {};

    const city = a.city || a.town || a.village || a.municipality || a.county || null;
    const neighborhood = a.neighbourhood || a.suburb || a.quarter || a.hamlet || null;

    const road = a.road || a.residential || a.pedestrian || null;
    const house = a.house_number || null;

    const address = road
      ? (house ? `${road} ${house}` : road)
      : (data?.display_name ? String(data.display_name).split(',').slice(0, 2).join(',').trim() : null);

    return { city, neighborhood, address };
  }

  private async geocodeAddress(query: string): Promise<{ lat: number; lng: number } | null> {
    const url =
      `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&addressdetails=1&q=${encodeURIComponent(query)}`;

    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      referrerPolicy: 'no-referrer',
    });

    if (!res.ok) return null;
    const list: any[] = await res.json();
    if (!Array.isArray(list) || !list.length) return null;

    const lat = Number(list[0].lat);
    const lng = Number(list[0].lon);
    if (!isFinite(lat) || !isFinite(lng)) return null;

    return { lat, lng };
  }

  async searchAddressOnMap() {
    this.errorMsg = '';
    this.successMsg = '';

    const parts = [this.clean(this.form.address), this.clean(this.form.neighborhood), this.clean(this.form.city), 'Colombia'].filter(Boolean);
    const q = parts.join(', ');

    if (q.length < 6) {
      this.errorMsg = 'Escribe al menos una dirección válida para buscar en el mapa.';
      return;
    }

    try {
      this.geoBusy = true;
      const hit = await this.geocodeAddress(q);
      if (!hit) {
        this.errorMsg = 'No encontré esa dirección. Ajusta el texto o usa el pin manualmente.';
        return;
      }
      this.setPoint(hit.lat, hit.lng, null);
      this.successMsg = 'Ubicación actualizada desde la dirección ✅';
    } catch (e) {
      console.warn('[Geocode] search failed', e);
      this.errorMsg = 'No se pudo buscar la dirección ahora. Intenta de nuevo.';
    } finally {
      this.geoBusy = false;
    }
  }

  useMyLocation() {
    this.errorMsg = '';
    this.successMsg = '';

    if (!navigator.geolocation) {
      this.errorMsg = 'Tu navegador no soporta geolocalización.';
      return;
    }

    this.successMsg = 'Obteniendo ubicación…';

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        this.setPoint(latitude, longitude, accuracy ?? null);
        this.successMsg = 'Ubicación capturada ✅ (puedes mover el pin).';
      },
      (err) => {
        console.error(err);
        this.successMsg = '';
        if (err.code === err.PERMISSION_DENIED) this.errorMsg = 'Permiso de ubicación denegado.';
        else this.errorMsg = 'No se pudo obtener tu ubicación. Intenta de nuevo.';
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  }

  submit() {
    this.errorMsg = '';
    this.successMsg = '';

    if (!this.canSubmit()) {
      this.errorMsg = 'Completa título (mín 3), descripción (mín 10) y marca tu ubicación (lat/lng) en el mapa.';
      return;
    }

    this.loading = true;

    const payload: ServiceRequestCreate = {
      ...this.form,
      category: (this.clean(this.form.category) ?? 'GENERAL').toUpperCase(),
      title: this.clean(this.form.title) ?? '',
      description: this.clean(this.form.description) ?? '',

      city: this.clean(this.form.city),
      neighborhood: this.clean(this.form.neighborhood),
      address: this.clean(this.form.address),
      address_ref: this.clean(this.form.address_ref),

      time_window: this.clean(this.form.time_window) ?? 'FLEXIBLE',

      contact_name: this.clean(this.form.contact_name),
      contact_phone: this.clean(this.form.contact_phone),
      contact_pref: this.form.contact_pref ?? 'WHATSAPP',
    };

    this.requests.create(payload).subscribe({
      next: () => {
        this.loading = false;
        this.successMsg = 'Solicitud creada ✅';
        this.router.navigateByUrl('/my-requests');
      },
      error: (err) => {
        console.error(err);
        this.loading = false;

        const detail = err?.error?.detail;
        if (Array.isArray(detail)) {
          this.errorMsg = detail
            .map((d: any) => {
              const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : 'campo';
              return `${field}: ${d.msg}`;
            })
            .join(' · ');
          return;
        }

        if (typeof detail === 'string') {
          this.errorMsg = detail;
          return;
        }

        this.errorMsg = 'No se pudo crear la solicitud. Revisa el backend.';
      },
    });
  }
}

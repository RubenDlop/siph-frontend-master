import { Injectable } from '@angular/core';

export interface AuthUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at?: string | null;
  auth_provider?: string | null;
  azure_oid?: string | null;
}

@Injectable({ providedIn: 'root' })
export class StorageService {
  private readonly tokenKey = 'siph_token';
  private readonly userKey = 'siph_user';

  private isBrowser(): boolean {
    return typeof window !== 'undefined' && typeof localStorage !== 'undefined';
  }

  saveToken(token: string): void {
    if (!this.isBrowser()) return;
    localStorage.setItem(this.tokenKey, token);
  }

  getToken(): string | null {
    if (!this.isBrowser()) return null;
    return localStorage.getItem(this.tokenKey);
  }

  removeToken(): void {
    if (!this.isBrowser()) return;
    localStorage.removeItem(this.tokenKey);
  }

  saveUser(user: AuthUser): void {
    if (!this.isBrowser()) return;
    localStorage.setItem(this.userKey, JSON.stringify(user));
  }

  getUser(): AuthUser | null {
    if (!this.isBrowser()) return null;

    const raw = localStorage.getItem(this.userKey);
    if (!raw) return null;

    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  }

  removeUser(): void {
    if (!this.isBrowser()) return;
    localStorage.removeItem(this.userKey);
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  getRole(): string {
    return (this.getUser()?.role || 'USER').toUpperCase();
  }

  hasRole(...roles: string[]): boolean {
    const currentRole = this.getRole();
    return roles.map((r) => r.toUpperCase()).includes(currentRole);
  }

  clearToken(): void {
    this.removeToken();
    this.removeUser();
  }

  clearUser(): void {
    this.removeUser();
  }

  clear(): void {
    this.removeToken();
    this.removeUser();
  }
}

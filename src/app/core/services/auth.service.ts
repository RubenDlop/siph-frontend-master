import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom, from, switchMap, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { StorageService, AuthUser } from './storage.service';

export interface RegisterPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface GoogleLoginPayload {
  credential: string;
}

export interface AuthResponse {
  access_token: string;
  token_type?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly baseUrl = this.resolveApiUrl();
  private readonly azure = environment.azure || {};

  private msalInstance: any = null;
  private msalInitPromise: Promise<any> | null = null;
  private azureLoginInProgress = false;

  constructor(
    private http: HttpClient,
    private storage: StorageService
  ) {
    console.log('[AuthService] API URL:', this.baseUrl);
  }

  // =========================================================
  // HELPERS
  // =========================================================
  private resolveApiUrl(): string {
    const envUrl = (environment.apiUrl || '').trim();

    if (envUrl) {
      return envUrl.replace(/\/+$/, '');
    }

    return 'https://siph-api-rubendlop.fly.dev';
  }

  // =========================================================
  // INIT
  // =========================================================
  initMicrosoftSession(): void {
    void this.getMsalClient();
  }

  async completeAzureRedirectIfNeeded(): Promise<AuthUser | null> {
    try {
      const pca = await this.getMsalClient();
      const result = await pca.handleRedirectPromise({
        navigateToLoginRequestUrl: false,
      });

      if (!result?.account) return null;

      pca.setActiveAccount(result.account);

      const apiScope = this.getApiScope();
      const tokenResult = await pca.acquireTokenSilent({
        scopes: [apiScope],
        account: result.account,
        redirectUri: this.getRedirectUri(),
      });

      if (!tokenResult?.accessToken) return null;

      return await this.exchangeAzureToken(tokenResult.accessToken);
    } catch {
      return null;
    }
  }

  // =========================================================
  // LOCAL
  // =========================================================
  register(payload: RegisterPayload): Observable<AuthUser> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/auth/register`, payload)
      .pipe(switchMap((res) => this.finishLogin(res)));
  }

  login(payload: LoginPayload): Observable<AuthUser> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/auth/login`, payload)
      .pipe(switchMap((res) => this.finishLogin(res)));
  }

  // =========================================================
  // GOOGLE
  // =========================================================
  loginWithGoogle(credential: string): Observable<AuthUser> {
    const payload: GoogleLoginPayload = { credential };

    return this.http
      .post<AuthResponse>(`${this.baseUrl}/auth/google`, payload)
      .pipe(switchMap((res) => this.finishLogin(res)));
  }

  // =========================================================
  // AZURE / MICROSOFT
  // =========================================================
  loginWithAzure(): Observable<AuthUser> {
    return from(this.acquireAzureAndExchange());
  }

  private async acquireAzureAndExchange(): Promise<AuthUser> {
    if (this.azureLoginInProgress) {
      throw new Error(
        'Ya hay un inicio de sesión con Microsoft en progreso. Espera un momento e inténtalo otra vez.'
      );
    }

    this.azureLoginInProgress = true;

    try {
      const pca = await this.getMsalClient();
      const apiScope = this.getApiScope();
      const loginScopes = this.getLoginScopes();
      const redirectUri = this.getRedirectUri();

      let account =
        pca.getActiveAccount() || pca.getAllAccounts()?.[0] || null;

      if (!account) {
        const loginResult = await pca.loginPopup({
          scopes: loginScopes,
          prompt: 'select_account',
          redirectUri,
        });

        account = loginResult?.account || null;

        if (account) {
          pca.setActiveAccount(account);
        }
      }

      if (!account) {
        throw new Error('No se pudo obtener la cuenta de Microsoft.');
      }

      let accessToken = '';

      try {
        const tokenResult = await pca.acquireTokenSilent({
          scopes: [apiScope],
          account,
          redirectUri,
        });

        accessToken = tokenResult.accessToken;
      } catch {
        const tokenResult = await pca.acquireTokenPopup({
          scopes: [apiScope],
          account,
          prompt: 'select_account',
          redirectUri,
        });

        accessToken = tokenResult.accessToken;
      }

      if (!accessToken) {
        throw new Error('No se pudo obtener el access token de Microsoft.');
      }

      return await this.exchangeAzureToken(accessToken);
    } finally {
      this.azureLoginInProgress = false;
    }
  }

  private async getMsalClient(): Promise<any> {
    if (typeof window === 'undefined') {
      throw new Error(
        'El login con Microsoft solo está disponible en navegador.'
      );
    }

    if (this.msalInstance) return this.msalInstance;
    if (this.msalInitPromise) return this.msalInitPromise;

    this.msalInitPromise = (async () => {
      const clientId = (this.azure?.clientId || '').trim();
      const tenantId = (this.azure?.tenantId || '').trim();
      const authority =
        (this.azure?.authority || '').trim() ||
        `https://login.microsoftonline.com/${tenantId}`;
      const redirectUri = this.getRedirectUri();

      if (!clientId || !tenantId) {
        throw new Error(
          'Falta configurar environment.azure.clientId o environment.azure.tenantId.'
        );
      }

      const { PublicClientApplication, BrowserCacheLocation } = await import(
        '@azure/msal-browser'
      );

      const pca = new PublicClientApplication({
        auth: {
          clientId,
          authority,
          redirectUri,
        },
        cache: {
          cacheLocation: BrowserCacheLocation.LocalStorage,
        },
        system: {
          iframeBridgeTimeout: 30000,
          popupBridgeTimeout: 30000,
          redirectNavigationTimeout: 30000,
        },
      });

      await pca.initialize();

      try {
        const redirectResult = await pca.handleRedirectPromise({
          navigateToLoginRequestUrl: false,
        });

        if (redirectResult?.account) {
          pca.setActiveAccount(redirectResult.account);
        }
      } catch {
        // silencioso
      }

      const accounts = pca.getAllAccounts();
      if (!pca.getActiveAccount() && accounts.length > 0) {
        pca.setActiveAccount(accounts[0]);
      }

      this.msalInstance = pca;
      return pca;
    })();

    return this.msalInitPromise;
  }

  private getRedirectUri(): string {
    const configured = (this.azure?.redirectUri || '').trim();
    if (configured) return configured;

    if (typeof window !== 'undefined') {
      return `${window.location.origin}/assets/msal-blank.html`;
    }

    return 'http://localhost:4200/assets/msal-blank.html';
  }

  private getApiScope(): string {
    const apiScope = (this.azure?.apiScope || '').trim();
    if (!apiScope) {
      throw new Error('Falta configurar environment.azure.apiScope.');
    }
    return apiScope;
  }

  private getLoginScopes(): string[] {
    const apiScope = this.getApiScope();
    return ['openid', 'profile', 'email', apiScope];
  }

  private async exchangeAzureToken(accessToken: string): Promise<AuthUser> {
    const authRes = await firstValueFrom(
      this.http.post<AuthResponse>(`${this.baseUrl}/auth/azure/exchange`, {
        access_token: accessToken,
      })
    );

    return await firstValueFrom(this.finishLogin(authRes));
  }

  // =========================================================
  // PERFIL
  // =========================================================
  me(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${this.baseUrl}/auth/me`).pipe(
      tap((user) => {
        this.storage.saveUser(user);
      })
    );
  }

  logout(): void {
    this.storage.clear();

    if (typeof window !== 'undefined') {
      void this.getMsalClient()
        .then((pca) => {
          const account =
            pca.getActiveAccount() || pca.getAllAccounts()?.[0] || null;

          if (!account) return;

          return pca.logoutPopup({
            account,
            postLogoutRedirectUri: window.location.origin,
          });
        })
        .catch(() => {
          // silencioso
        });
    }
  }

  private finishLogin(res: AuthResponse): Observable<AuthUser> {
    this.storage.saveToken(res.access_token);
    return this.me();
  }
}

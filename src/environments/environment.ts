export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  googleClientId:
    '1026227617402-hts4hu699cuo0gmh5fg8sh8ncjfdvo76.apps.googleusercontent.com',
  azure: {
    tenantId: '8091eb44-4181-4c3c-b53d-fd6add70b0d9',
    clientId: '628629c9-2b9b-43e7-a9e4-949b5af8a5f4',
    apiClientId: 'b6a729ea-ecc2-4014-814c-4c10d21a0e24',
    authority:
      'https://login.microsoftonline.com/8091eb44-4181-4c3c-b53d-fd6add70b0d9',
    redirectUri: 'http://localhost:4200/assets/msal-blank.html',
    apiScope: 'api://b6a729ea-ecc2-4014-814c-4c10d21a0e24/access_as_user',
  },
};

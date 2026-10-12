# Authentication implementation and verification

Reviewed 2026-10-08. The existing confidential OIDC authorization-code flow remains the identity boundary. Auth0 is the selected hosted provider. F01 offers Google and Email handoffs when their fixed, backend-configured connections are enabled; F01 never collects a password, creates its own magic-link tokens, or sends authentication email.

## Implemented and tested

- Sign-in and sign-up screens, provider-specific connection selection, signup intent, explicit reauthentication and safe return to the interrupted product route.
- PKCE S256, state, nonce, browser binding, signed RS256 ID/access token checks, issuer/audience/expiry validation, five-minute single-use login attempts and login rate limits.
- Verified signed email required in production. Unverified email is rejected before creating a session. Provider errors are reduced to safe messages; raw debugging details never reach the page.
- Encrypted, revocable backend sessions; Secure/HttpOnly/SameSite cookies in production; same-origin mutations and existing CSRF checks. Successful logout revokes the app session. Failed logout preserves the session until the user can retry. Expiry returns the user to their original route after reauthentication.
- Owner-scoped account GET/PATCH, persistent display name, verified email read-only, session end and security details. Strict payloads cannot change identity, email, roles or ownership. Double-click saves issue one mutation.
- Owner identity remains issuer + subject. Email never selects or merges an owner. A later verified login updates the existing subject's email while preserving the display name and projects.

The browser suite passed with a controlled RSA OIDC issuer and a real disposable PostgreSQL database. It exercised Google/email connection parameters, signup, account persistence/reload, expiry/recovery, revocation, separate owners, unverified email, reused/expired callbacks, cancellation, keyboard operation and reduced motion. Nine states passed 36 WCAG scans across desktop/mobile/tablet and 720×500 reflow. See `authentication/result.json`, screenshots and `logs/auth-browser-final.log`. These are protocol integration tests, not actual Google login or email-delivery evidence.

## Required external configuration

1. Create an Auth0 **Regular Web Application** and API audience; enable Authorization Code and RS256. Register the exact HTTPS factory callback `/api/auth/callback`, factory origin and allowed logout URL. Preserve all OIDC transaction parameters through hosted login. Use the provider's exact issuer spelling, including its trailing slash.
2. Configure Google with production Google OAuth client credentials and the provider's callback; enable the connection for the application. Set `OIDC_GOOGLE_CONNECTION` to its fixed connection name, commonly `google-oauth2`.
3. Enable the email passwordless connection. Auth0 documents magic links with **Classic Login**, using `Auth0LockPasswordless` and `passwordlessMethod: 'link'`. New Universal Login does not support that magic-link experience. Preserve `config.internalOptions`, the code response type, state, nonce and PKCE parameters in the hosted template; do not switch F01 to implicit/browser-stored tokens. Requests and opened links must use the same browser/device. Set `OIDC_EMAIL_CONNECTION=email` only after this hosted flow is configured. [Auth0 magic-link documentation](https://auth0.com/docs/authenticate/passwordless/authentication-methods/email-magic-link), [official Lock configuration](https://github.com/auth0/lock/blob/master/EXAMPLES.md).
4. Configure a production SMTP/email provider, verified sender/domain, delivery monitoring and a short link expiry compatible with F01's five-minute attempt. The built-in Auth0 email service is for testing. Verify real delivery, expired/reused links and same-browser recovery. [Auth0 email providers](https://auth0.com/docs/customize/email/smtp-email-providers).
5. Put `OIDC_ISSUER`, `OIDC_AUTHORIZATION_URL`, `OIDC_TOKEN_URL`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_API_AUDIENCE`, `OIDC_REDIRECT_URI`, connection names and `SESSION_ENCRYPTION_KEY` in the backend's secret environment. Set `AUTH_MODE=oidc`, `APP_ENV=production`, `OIDC_REQUIRE_VERIFIED_EMAIL=true`. Keep the gateway credential server-only in both API and BFF; configure `API_INTERNAL_URL` and the exact HTTPS `NEXT_PUBLIC_APP_URL`. Never use `NEXT_PUBLIC_*` for secrets. Production validates a confidential client secret, HTTPS endpoints, encryption and verified-email policy.
6. Keep API/database private and configure the existing independent preview origin, accepted exact Docker image, workers and release secret environment. Production topology, backup/restore and provider operations require their own acceptance.

Google and passwordless email may issue **different subjects for the same email address**. They therefore have separate workspaces unless Auth0 performs an explicitly secured identity-linking flow that preserves the primary subject. F01 deliberately does not auto-link by email. Use the original sign-in method to recover its workspace. The controlled browser recovery uses the same signed subject; it does not prove cross-connection account linking.

App logout revokes F01 access, not every external provider session. Subsequent login requests `prompt=login`; the hosted provider must honor the required reauthentication policy.

## Live status and release gate

No live Auth0 tenant, Google connection, SMTP sender or production session/gateway configuration was supplied in this workspace. Actual Google login, magic-link delivery/consumption and deployed production authentication are **not verified**. Hosted Classic Login is a documented compatibility choice with a same-browser limitation, and must be accepted against the configured tenant; it is not a claim that the provider is ready.

Before live authentication can pass: verify Google signup/signin, Email signup/signin with a delivered link, verified-email denial, reused/expired link, original-method recovery, logout/revocation, expired session, two-owner project denial, HTTPS cookies, CSRF and production origin/issuer policy. Record real tenant evidence privately without tokens, email links or credentials. Public-launch readiness remains gated on these checks and the real publishing/operations checks.

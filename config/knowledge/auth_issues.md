# Authentication and Login Failures

## Summary

This article covers authentication failures in Modelyo Confidential Cloud, including 401 Unauthorized, 403 Forbidden, token expiry, OAuth flow errors, and credential rejection.

## Affected Components

- `auth-service`

## Common Symptoms

- HTTP 401 Unauthorized on API calls
- HTTP 403 Forbidden when accessing resources
- OAuth token exchange fails
- SSO/SAML login loop or redirect failure
- Credentials rejected despite being correct
- Session tokens expiring earlier than expected

## Diagnostic Steps

Run the following checks and share the results (redact credentials before sharing):

1. **Verify token validity**
   ```
   curl -H "Authorization: Bearer <your-token>" https://<endpoint>/auth/verify
   ```
   Note the HTTP status code and response body.

2. **Check token expiry**
   Decode your JWT token at jwt.io (do not share the raw token) and check the `exp` field.

3. **OAuth flow trace**
   Enable verbose logging on your OAuth client:
   ```
   export OAUTH_DEBUG=1
   ```
   Retry the login and capture the log output.

4. **SAML assertion (if applicable)**
   Capture the SAML response XML from your identity provider and note any error attributes.

## Common Causes and Resolutions

### 401 Unauthorized
- Token has expired — obtain a new token via your configured OAuth client
- Token was issued for a different audience — verify the `aud` claim matches the Modelyo endpoint
- API key has been rotated — update your configuration with the new key
- Clock skew between client and server > 5 minutes — synchronise your system clock (NTP)

### 403 Forbidden
- The authenticated identity does not have the required role or permission
- Resource belongs to a different tenant — confirm you are using credentials for the correct organization
- IP allowlist is enforced — verify the originating IP is listed in your Modelyo tenant configuration

### OAuth token exchange failure
- Redirect URI mismatch — ensure the URI registered in Modelyo matches exactly (including trailing slash)
- Client secret has changed — update your OAuth client configuration
- Authorization code has already been used — do not reuse authorization codes; restart the flow

### SSO/SAML issues
- Verify the identity provider metadata URL is accessible from Modelyo's network
- Check that the assertion signing certificate has not expired
- Confirm the NameID format matches the configured format in Modelyo

## Escalation

Attach the full error response (with credentials removed), the token decode output, and OAuth/SAML logs when escalating to Tier 2.

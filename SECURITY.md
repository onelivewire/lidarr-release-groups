# Security review and limitations

This is a scoped source review with browser regression tests, not an independent
audit or a guarantee that the software has no vulnerabilities.

## Fixed in 1.0.7: API redirects could forward an API key

Versions through 1.0.6 checked that the initial API URL shared the current page's
origin but allowed fetch's default redirect following. When the fallback API
path was used and the page exposed an API key, an API/proxy redirect to another
origin could forward the `X-Api-Key` header if that destination allowed the CORS
request. Exploitation requires control of an applicable redirect; this is not
an unauthenticated endpoint that exposes arbitrary users' keys.

A local-only Chromium test reproduced transmission of a **synthetic** key to
a second origin. Version 1.0.7 sets `redirect: 'error'` and `mode: 'same-origin'`.
The regression test verifies the redirect target receives neither a preflight
nor a GET. A separate test verifies an off-origin configured API root is rejected
before fetch is called. Native rows remain available after rejection.

Install 1.0.7 or later. Existing installations are version-pinned and do not
automatically adopt this fix. There is no evidence from this review that any
real credential was exposed; no real keys or production redirects were used in
the tests. The native-row metadata path makes no API requests.

## Trust boundaries

- The HTTP/HTTPS URL matches are deliberately broad for portable installation.
  Restrict Tampermonkey's extension site access to your actual Lidarr hosts and
  the GitHub raw download host. A page title or `window.Lidarr` is an activation
  check, **not** a security boundary: another page can imitate these values.
- `@grant none` requests no privileged userscript APIs. The raw page context
  still has ordinary page access to DOM, localStorage, authenticated same-origin
  requests and any credentials the page itself exposes. A compromised Lidarr
  page or another malicious script on that origin is outside the protection
  offered by this script.
- Production code uses DOM text APIs for labels and metadata, with no HTML
  interpolation, eval, remote libraries or dynamic code downloads. Tests include
  hostile metadata text. Preferences contain display settings and artist/group
  identifiers, never API keys; they remain in page localStorage.
- Network fallback uses GET only, a same-origin URL check, same-origin fetch
  mode, no redirects, same-origin cookies and a timeout. There are no analytics
  or intentional cross-origin runtime requests. Tampermonkey separately contacts
  the published hosting/sync services as configured by the browser owner.
- Updates/downloads are pinned to a version tag to prevent routine automatic
  adoption of future versions. Git tags are technically movable by repository
  maintainers: this policy is not cryptographic integrity verification. You
  still trust the maintainer's GitHub account, hosting, userscript manager and
  browser. Review changes and retain exports for recovery.
- This script adds no network listener and does not change how Lidarr itself is
  exposed. Existing HTTP transport, server authentication and proxy security
  remain the responsibility of the Lidarr installation.

## Reporting

Do not post keys, cookies or personal inventories in public issues. Send a
minimal reproduction with synthetic metadata and browser/Lidarr versions. If
GitHub private vulnerability reporting is enabled, use the repository's Security
tab to report a credential-exposure issue privately.

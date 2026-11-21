# Changelog

## 1.0.7 — prevent API-key forwarding through redirects

- Reject all API redirects and enforce same-origin fetch mode. Previously, the
  API fallback checked only its initial URL; a redirect could forward a
  page-provided X-Api-Key to a different origin that permits the CORS request.
- Reproduced the issue with a synthetic key and a local redirect fixture, then
  verified the fixed script makes no request to the redirect destination.
- Add a separate regression check for an off-origin configured API root.

## 1.0.6 — embedded Lidarr compatibility

- Allow execution inside Lidarr frames, including dashboards such as Organizr.
  Permissions must cover the actual Lidarr frame address as well as any custom
  direct address. Each frame still requires a Lidarr page identity.

## 1.0.5 — Chrome activation fix

- Use standard HTTP/HTTPS URL matches with a Lidarr identity guard, avoiding
  unreliable activation of regex port includes under Chrome's restricted site
  permissions. Keep Tampermonkey's site access restricted to your Lidarr hosts.
- Support custom ports and proxy paths without editing the script.

## 1.0.4 — first public release

- Publish a stable installation URL and version-pinned download/update metadata
  for Tampermonkey Browser Sync, without opting into future upgrades.
- Recognize default port 8686 and `/lidarr/` proxy paths without source editing.
- Require a Lidarr page identity before starting; leave other applications alone.
- Document cross-computer sync, permissions and migration from manual copies.

## 1.0.3 — internal release candidate

- Group releases by secondary type within native primary sections.
- Sort by release date, oldest/newest first, with unknown dates last.
- Save per-artist collapsed groups and browser-local display preferences.
- Restore native ordering through Original view.
- Read existing row metadata with a same-origin GET fallback.
- Include configurable server matching, isolated browser tests and a sample demo.

The initial package derived from the tested browser deployment.

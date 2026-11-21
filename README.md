# Lidarr release groups

Collapsible studio, live, compilation, soundtrack, remix and demo groups for
Lidarr artist pages, with chronological sorting inside each group. A browser
userscript for Tampermonkey. No server installation or build dependencies.

The native Album, EP, Single, Broadcast and Other sections remain. Works across
artists; collapse preferences are saved separately for each artist. Secondary
Types does **not** need to be a visible column.

## Install

1. Install Tampermonkey in your browser.
2. Click [Install the script](https://raw.githubusercontent.com/onelivewire/lidarr-release-groups/main/release-groups.user.js)
   and confirm installation in Tampermonkey.
3. Standard Lidarr addresses on **port 8686** and reverse proxies under
   **`/lidarr/`** work without editing. The script also checks the page identifies
   itself as Lidarr before starting. For a different port or proxy path, open
   the script's Tampermonkey Settings and add your URL under **User matches**:

   ```js
   https://music.example.com/*
   ```

   Use the narrowest hostname/path that covers your installation. Match patterns
   omit ports for Chrome/Firefox compatibility. Keep customization in manager
   settings instead of editing the downloaded source.
4. In Chrome, enable Tampermonkey's **Allow User Scripts** permission if
   required, and grant the extension access to your Lidarr site. Restrict site
   access to your Lidarr hosts; all-sites extension access is unnecessary.
5. Reload an artist page and expand the native Album section (or Expand All).
   The Release groups toolbar appears when a release table is present.

Choose oldest/newest first, click group headings to collapse them, or select
Original view. Installation and preferences are separate in each browser and
for each server origin. Run only one copy of this script on a page. If migrating
from a manually pasted copy, export it as a backup and disable it before
installing this distribution. The public version uses a separate preference key.

## Sync between computers

Publishing alone does not enable sync. On **each computer**, open Tampermonkey
Dashboard → Settings, choose Beginner/Advanced configuration mode, then under
Script Sync select **Browser Sync**, enable it and save. Chrome must be signed
in with browser synchronization enabled. The script supplies a public,
version-pinned `@downloadURL` so Tampermonkey can retrieve the same release.
See [Tampermonkey's sync instructions](https://www.tampermonkey.net/faq.php?locale=en&q=Q105).

Verify the script appears on the other computer, allow its Lidarr site access,
and reload an artist page. Per-site Chrome permissions may still require local
approval. Custom manager URL overrides should be checked on each browser.
Collapse and sort preferences use the Lidarr page's localStorage and **do not
sync**; the script installation and display preferences are separate.

## Behavior and limits

- Classification follows Lidarr/MusicBrainz metadata, without guessing from
  titles. Live takes precedence over Compilation, then Soundtrack, Remix, Demo
  and remaining types. Missing dates sort last. Unmatched rows stay visible.
- Original album links and single-release controls retain their native nodes
  and handlers. The script never writes catalog data or triggers downloads.
- Native column sorting and Shift-range selection require **Original view**:
  Lidarr's internal range order can differ from the displayed grouped order.
- Native primary sections must be expanded before their releases can be grouped.
- Uses read-only React row metadata where available, with same-origin GET API
  fallback. It reuses the current session and a page-exposed API key if present;
  no key is bundled, persisted or transmitted to another origin. No analytics,
  third-party requests or runtime dependencies.
- React properties and page structure are internal interfaces and can change
  with Lidarr updates. API failure leaves native rows available and reports the
  error; Reload groups retries.

## Compatibility and tests

The original deployment was verified with Lidarr **3.1.0.4875**, Chrome and
Tampermonkey **5.5.1**, across 1,096 releases, checking every album ID exactly
once and release-date ordering in 18 groups. The portable distribution uses
the same grouping code with generic identifiers and configurable URL matching.
Firefox is intended to work but has **not been live tested**. Other Lidarr
versions and userscript managers are unverified.

Python 3 and Chrome/Chromium are needed only for development checks:

```sh
LIDARR_UI_BROWSER=/path/to/chrome python3 test_release_groups.py
```

On macOS the test runner defaults to the standard Google Chrome application.
Tests use an isolated temporary profile and loopback fixture server, never
your existing browser profile or Lidarr server. Coverage includes grouping,
dates, collapse, original view, row identity, native delegated controls,
navigation, rerenders, API failures and HTML escaping. An optional private
catalog test uses `LIDARR_UI_CATALOG=/path/to/catalog.json` with an `albums`
array; do not publish personal inventories.

For an interactive sample-data demo, serve this directory:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/demo.html`. No extension or server credentials needed.
This demonstrates grouping using synthetic rows, not a full Lidarr UI.

## Updates and recovery

Downloads and update checks are pinned to **v1.0.4**. Installing this release
does not opt into future versions automatically. The browser owner controls installation:
review a new release, run the checks, export the installed script as a backup,
then install the newly reviewed release from its published URL. Reload an
artist and check grouping, chronological order and Original view. Repeat after
Lidarr upgrades. No background service, scheduler or server updater is installed.

To recover, disable the script in Tampermonkey and reload. To roll back, restore
the exported script. Preferences live only in browser localStorage under
`lidarr.releaseGroups.v1`; disabling the script does not delete preferences.

## Contributing

Include browser, userscript manager and Lidarr versions with reports. Redact
hostnames, keys, cookies and personal library inventories. Reproduce with
sample metadata where possible. Changes should preserve native controls and
avoid API writes. Run the browser checks before proposing a change.

Independent project; not affiliated with Lidarr or Tampermonkey. MIT licensed.

// ==UserScript==
// @name         Lidarr release groups
// @namespace    lidarr-release-groups
// @version      1.0.6
// @description  Collapsible release groups, sorted by release date. Presentation only.
// @match        http://*/*
// @match        https://*/*
// @grant        none
// @sandbox      raw
// @run-at       document-idle
// @homepageURL  https://github.com/onelivewire/lidarr-release-groups
// @supportURL   https://github.com/onelivewire/lidarr-release-groups/issues
// @license      MIT
// @updateURL    https://raw.githubusercontent.com/onelivewire/lidarr-release-groups/v1.0.6/release-groups.user.js
// @downloadURL  https://raw.githubusercontent.com/onelivewire/lidarr-release-groups/v1.0.6/release-groups.user.js
// ==/UserScript==

(() => {
  'use strict';
  // Leave other applications alone, even if they share the usual port/path.
  if (!window.Lidarr && !/\bLidarr\b/i.test(document.title)) return;
  if (window.__lidarrReleaseGroups) window.__lidarrReleaseGroups.stop();
  const VERSION = '1.0.6';
  const KEY = 'lidarr.releaseGroups.v1';
  const MARK = 'data-lrg-release-groups';
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  let prefs;
  try { prefs = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (_) { prefs = {}; }
  if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) prefs = {};
  prefs.enabled = prefs.enabled !== false;
  prefs.newest = prefs.newest === true;
  prefs.collapsed = prefs.collapsed && typeof prefs.collapsed === 'object' ? prefs.collapsed : {};
  const tables = new Map();
  let albums = new Map(), artist = '', generation = 0, pending = '', loadedAt = 0;
  let timer, toolbar, notice, observer, stopped = false, currentURL = location.href;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) {} };
  const setNotice = text => { if (notice && notice.textContent !== text) notice.textContent = text; };
  const route = () => location.pathname.match(/\/artist\/([0-9a-f-]{36})(?:\/|$)/i)?.[1]?.toLowerCase() || '';
  const albumID = row => {
    const link = row.querySelector('a[href*="/album/"]');
    return link?.getAttribute('href')?.match(/\/album\/([0-9a-f-]{36})(?:[/?#]|$)/i)?.[1]?.toLowerCase() || '';
  };
  function nativeMetadata(row) {
    // Read only the already-rendered AlbumRow props. No React state is changed.
    const id = albumID(row);
    const key = Object.keys(row).find(name => name.startsWith('__reactFiber$') || name.startsWith('__reactInternalInstance$'));
    let fiber = key && row[key];
    for (let depth = 0; fiber && depth < 20; depth++, fiber = fiber.return) {
      const props = fiber.memoizedProps;
      if (props && String(props.foreignAlbumId || '').toLowerCase() === id &&
          typeof props.albumType === 'string' && Array.isArray(props.secondaryTypes)) {
        return { foreignAlbumId: id, title: props.title, releaseDate: props.releaseDate,
          albumType: props.albumType, secondaryTypes: props.secondaryTypes };
      }
    }
    return null;
  }
  const groupFor = album => {
    const types = new Set((album.secondaryTypes || []).map(x => String(x).toLowerCase()));
    const primary = String(album.albumType || 'Other');
    const suffix = primary === 'Album' ? 'albums' : primary === 'EP' ? 'EPs' : primary === 'Single' ? 'singles' : 'releases';
    for (const [type, label, rank] of [
      ['live', 'Live', 20], ['compilation', 'Compilation', 30],
      ['soundtrack', 'Soundtrack', 40], ['remix', 'Remix', 50], ['demo', 'Demos', 60],
      ['dj-mix', 'DJ mixes', 70], ['mixtape/street', 'Mixtapes', 80],
      ['spokenword', 'Spoken word', 90], ['interview', 'Interviews', 100],
      ['audiobook', 'Audiobooks', 110]
    ]) {
      if (types.has(type)) return { key: primary + ':' + type, title: ['Demos', 'DJ mixes', 'Mixtapes', 'Interviews', 'Audiobooks'].includes(label) ? label : label + ' ' + suffix, rank };
    }
    if (types.size) return { key: primary + ':other', title: 'Other ' + suffix, rank: 120 };
    return { key: primary + ':standard', title: primary === 'Album' ? 'Studio albums' : primary === 'EP' ? 'EPs' : primary === 'Single' ? 'Singles' : primary + ' releases', rank: 10 };
  };
  const dateOf = album => {
    const value = Date.parse(album.releaseDate || '');
    return Number.isFinite(value) ? value : null;
  };
  const compare = (a, b) => {
    const ad = dateOf(a), bd = dateOf(b);
    if (ad === null && bd !== null) return 1;
    if (bd === null && ad !== null) return -1;
    if (ad !== bd) return prefs.newest ? bd - ad : ad - bd;
    return collator.compare(a.title || '', b.title || '') || collator.compare(a.foreignAlbumId || '', b.foreignAlbumId || '');
  };
  const style = document.createElement('style');
  style.setAttribute(MARK, 'style');
  style.textContent = `
    #lrg-release-toolbar {display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:14px 0;padding:12px 14px;border:1px solid #73808c66;border-radius:5px;background:#73808c12;color:inherit;font-size:13px}
    #lrg-release-toolbar button,#lrg-release-toolbar select {font:inherit;color:inherit;background:transparent;border:1px solid #73808c88;border-radius:4px;padding:5px 9px;cursor:pointer}
    #lrg-release-toolbar option {color:#222;background:#fff}
    #lrg-release-toolbar [data-note] {flex-basis:100%;opacity:.8}
    tr[${MARK}="group"] td {padding:0!important;border-bottom:1px solid #73808c66!important;background:#73808c20!important;color:inherit}
    tr[${MARK}="group"] button {display:block;width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:11px 14px;font:inherit;font-size:15px;font-weight:600;cursor:pointer}
    tr[${MARK}="group"] button span {font-size:12px;font-weight:400;opacity:.75;margin-left:10px}
    tr[${MARK}="hidden"] {display:none!important}
  `;
  document.head.append(style);

  function restore(table, state) {
    table.querySelectorAll(`tr[${MARK}="group"]`).forEach(row => row.remove());
    for (const row of state.original) {
      if (row.parentElement === state.body) {
        row.removeAttribute(MARK);
        row.removeAttribute('data-lrg-group');
        state.body.append(row);
      }
    }
    table.removeAttribute('data-lrg-grouped');
  }
  function clear() {
    observer?.disconnect();
    for (const [table, state] of tables) if (table.isConnected) restore(table, state);
    tables.clear(); toolbar?.remove(); toolbar = null; notice = null;
  }
  function observe() {
    if (!stopped) observer.observe(document.body, { childList: true, subtree: true });
  }
  function schedule() {
    if (stopped) return;
    clearTimeout(timer); timer = setTimeout(render, 120);
  }
  function mountToolbar(table) {
    if (toolbar?.isConnected) return;
    toolbar = document.createElement('div'); toolbar.id = 'lrg-release-toolbar'; toolbar.setAttribute(MARK, 'toolbar');
    const label = document.createElement('strong'); label.textContent = 'Release groups'; toolbar.append(label);
    const toggle = document.createElement('button'); toggle.type = 'button'; toggle.dataset.toggle = '';
    toggle.addEventListener('click', () => { prefs.enabled = !prefs.enabled; save(); schedule(); }); toolbar.append(toggle);
    const sort = document.createElement('select'); sort.setAttribute('aria-label', 'Release date order');
    for (const [value, title] of [['oldest', 'Oldest first'], ['newest', 'Newest first']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = title; sort.append(option);
    }
    sort.value = prefs.newest ? 'newest' : 'oldest';
    sort.addEventListener('change', () => { prefs.newest = sort.value === 'newest'; save(); schedule(); }); toolbar.append(sort);
    const expand = document.createElement('button'); expand.type = 'button'; expand.textContent = 'Expand groups';
    expand.addEventListener('click', () => { prefs.collapsed = {}; save(); schedule(); }); toolbar.append(expand);
    const reload = document.createElement('button'); reload.type = 'button'; reload.textContent = 'Reload groups';
    reload.addEventListener('click', () => { loadedAt = 0; loadMetadata(true); }); toolbar.append(reload);
    notice = document.createElement('span'); notice.dataset.note = ''; notice.setAttribute('role', 'status'); toolbar.append(notice);
    // Insert beside the native primary-type section, never inside a React-owned row.
    const section = table.closest('[class*="ArtistDetailsSeason/albumType"], [class*="ArtistDetailsSeason-albumType"], [class*="ArtistDetailsSeason_albumType"]');
    (section || table.parentElement).before(toolbar);
  }
  function decorate(table, rows) {
    const body = rows[0]?.parentElement;
    if (!body || body.tagName !== 'TBODY' || rows.some(row => row.parentElement !== body)) return false;
    let state = tables.get(table);
    if (!state || state.body !== body) { state = { body, original: [] }; tables.set(table, state); }
    rows.forEach(row => { if (!state.original.includes(row)) state.original.push(row); });
    const groups = new Map();
    for (const row of rows) {
      const album = albums.get(albumID(row));
      // Unknown rows remain visible, at the end, without guessing release identity.
      const group = album ? groupFor(album) : { key: 'unknown', title: 'Unclassified releases', rank: 999 };
      if (!groups.has(group.key)) groups.set(group.key, { ...group, entries: [] });
      groups.get(group.key).entries.push({ row, album });
    }
    const headers = new Map([...body.querySelectorAll(`:scope > tr[${MARK}="group"]`)].map(row => [row.dataset.groupKey, row]));
    const desired = [];
    const columns = table.tHead?.rows[0]?.cells.length || rows[0].cells.length;
    for (const group of [...groups.values()].sort((a, b) => a.rank - b.rank || collator.compare(a.title, b.title))) {
      group.entries.sort((a, b) => a.album && b.album ? compare(a.album, b.album) : collator.compare(a.row.textContent, b.row.textContent));
      let header = headers.get(group.key);
      if (!header) {
        header = document.createElement('tr'); header.setAttribute(MARK, 'group'); header.dataset.groupKey = group.key;
        const cell = document.createElement('td'); const button = document.createElement('button'); button.type = 'button';
        button.addEventListener('click', () => { const key = artist + ':' + group.key; prefs.collapsed[key] = !prefs.collapsed[key]; save(); schedule(); });
        cell.append(button); header.append(cell);
      }
      headers.delete(group.key);
      const closed = !!prefs.collapsed[artist + ':' + group.key];
      header.cells[0].colSpan = columns;
      const button = header.querySelector('button'); button.setAttribute('aria-expanded', String(!closed));
      const heading = (closed ? '▸ ' : '▾ ') + group.title;
      const count = group.entries.length + (group.entries.length === 1 ? ' release' : ' releases');
      if (button.dataset.label !== heading + count) {
        button.replaceChildren(document.createTextNode(heading)); const span = document.createElement('span'); span.textContent = count; button.append(span); button.dataset.label = heading + count;
      }
      desired.push(header);
      for (const { row } of group.entries) {
        if (closed) row.setAttribute(MARK, 'hidden'); else row.removeAttribute(MARK);
        row.dataset.lrgGroup = group.key; desired.push(row);
      }
    }
    for (const row of headers.values()) row.remove();
    // Reorder siblings only. Native row nodes, listeners and React ownership stay intact.
    desired.forEach((row, index) => { if (body.children[index] !== row) body.insertBefore(row, body.children[index] || null); });
    table.dataset.lrgGrouped = 'true';
    return true;
  }
  async function getJSON(endpoint) {
    const config = window.Lidarr;
    const prefix = location.pathname.slice(0, location.pathname.indexOf('/artist/'));
    const apiRoot = config?.apiRoot || prefix + '/api/v1';
    const url = new URL(apiRoot.replace(/\/$/, '') + '/' + endpoint, location.origin);
    if (url.origin !== location.origin) throw new Error('Refusing a different API origin');
    const headers = { Accept: 'application/json' };
    if (config?.apiKey) headers['X-Api-Key'] = config.apiKey;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url.href, { method: 'GET', credentials: 'same-origin', headers, signal: controller.signal });
      if (!response.ok) throw new Error('Metadata request failed (HTTP ' + response.status + ')');
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  async function loadMetadata(force = false) {
    const wanted = route();
    if (!wanted || pending === wanted || (!force && artist === wanted && loadedAt)) return;
    const epoch = generation; pending = wanted;
    setNotice('Reading release types and dates…');
    try {
      const artists = await getJSON('artist');
      const match = artists.find(item => String(item.foreignArtistId).toLowerCase() === wanted);
      if (!match) throw new Error('Artist could not be identified');
      const result = await getJSON('album?artistId=' + encodeURIComponent(match.id));
      if (stopped || epoch !== generation || route() !== wanted) return;
      albums = new Map(result.map(item => [String(item.foreignAlbumId).toLowerCase(), item]));
      artist = wanted; loadedAt = Date.now(); setNotice('');
    } catch (error) {
      if (epoch === generation) { loadedAt = Date.now(); setNotice(error.message + '. Original rows are unchanged; use Reload groups to retry.'); }
    } finally {
      if (epoch === generation) { pending = ''; schedule(); }
    }
  }
  function render() {
    if (stopped) return;
    observer.disconnect();
    try {
      const wanted = route();
      if (wanted !== artist) { generation++; pending = ''; clear(); albums = new Map(); artist = wanted; loadedAt = 0; }
      if (!wanted) return;
      for (const [table] of tables) if (!table.isConnected) tables.delete(table);
      const candidates = [...document.querySelectorAll('table')].map(table => ({ table, rows: [...table.querySelectorAll(':scope > tbody > tr')].filter(row => albumID(row)) })).filter(item => item.rows.length);
      if (!candidates.length) return;
      mountToolbar(candidates[0].table);
      toolbar.querySelector('[data-toggle]').textContent = prefs.enabled ? 'Original view' : 'Grouped view';
      toolbar.querySelector('select').disabled = !prefs.enabled;
      const nativeRows = candidates.flatMap(item => item.rows);
      const nativeAlbums = nativeRows.map(nativeMetadata);
      if (nativeAlbums.length && nativeAlbums.every(Boolean)) {
        albums = new Map(nativeAlbums.map(album => [album.foreignAlbumId, album]));
        loadedAt = Date.now();
      }
      if (!prefs.enabled || !albums.size) {
        for (const [table, state] of tables) if (table.isConnected && table.dataset.lrgGrouped) restore(table, state);
        if (!loadedAt && !pending) loadMetadata();
        return;
      }
      candidates.forEach(({ table, rows }) => decorate(table, rows));
      if (!notice.textContent || notice.textContent.startsWith('Grouped by')) setNotice('Grouped by type, then release date. Use Original view for native column sorting or Shift-range selection.');
    } finally { observe(); }
  }
  function guard(event) {
    if (!prefs.enabled || !event.target?.closest) return;
    const table = event.target.closest('table[data-lrg-grouped]');
    if (!table) return;
    const nativeHeader = event.target.closest('thead th');
    if ((nativeHeader && nativeHeader.textContent.trim()) || (event.shiftKey && event.target.closest('tbody tr[data-lrg-group]'))) {
      event.preventDefault(); event.stopImmediatePropagation();
      setNotice(event.shiftKey ? 'Use Original view for Shift-range selection. Single-release controls still work here.' : 'Choose Oldest first or Newest first above. Use Original view for native column sorting.');
    }
  }
  observer = new MutationObserver(schedule);
  document.addEventListener('click', guard, true);
  const navigation = setInterval(() => { if (location.href !== currentURL) { currentURL = location.href; schedule(); } }, 500);
  window.__lidarrReleaseGroups = {
    version: VERSION,
    stop() { stopped = true; clearTimeout(timer); clearInterval(navigation); clear(); style.remove(); document.removeEventListener('click', guard, true); delete window.__lidarrReleaseGroups; }
  };
  observe(); schedule();
})();

/* The final expression is the scanner result returned by executeScript. */
(() => {
  'use strict';
  const sources = [];
  const seen = new Map();
  const encryptedUrls = new Set();
  const blocked = { blob: 0, data: 0, encrypted: 0, empty: 0 };
  const pageTitle = document.title || 'Video';
  const mimeByExtension = {
    mp4: 'video/mp4', m4v: 'video/mp4', webm: 'video/webm',
    m3u8: 'application/vnd.apple.mpegurl', mpd: 'application/dash+xml',
    mp3: 'audio/mpeg', m4a: 'audio/mp4', ogg: 'audio/ogg', ogv: 'video/ogg',
  };
  function format(url, mimeType) {
    const match = new URL(url).pathname.match(/\.([a-z0-9]+)$/i);
    const extension = match?.[1]?.toLowerCase();
    const resolvedType = mimeType?.split(';')[0].trim() || mimeByExtension[extension] || '';
    const name = extension === 'm3u8' ? 'HLS playlist' : extension === 'mpd' ? 'DASH manifest'
      : extension ? extension.toUpperCase() : resolvedType.startsWith('audio/') ? 'Audio' : 'Stream';
    return { mimeType: resolvedType, name };
  }
  function add(raw, details) {
    if (!raw || typeof raw !== 'string') return;
    let parsed;
    try { parsed = new URL(raw, document.baseURI); } catch { return; }
    if (parsed.protocol === 'blob:') { blocked.blob++; return; }
    if (parsed.protocol === 'data:') { blocked.data++; return; }
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return;
    parsed.hash = '';
    if (encryptedUrls.has(parsed.href)) return;
    const info = format(parsed.href, details.mimeType);
    const candidate = {
      url: parsed.href, title: pageTitle, mimeType: info.mimeType,
      label: `${details.label} · ${info.name}`, playing: details.playing, fromNetwork: details.fromNetwork,
    };
    const existing = seen.get(parsed.href);
    if (existing) {
      const preferred = Number(candidate.playing) - Number(existing.playing)
        || Number(existing.fromNetwork) - Number(candidate.fromNetwork);
      if (preferred > 0) Object.assign(existing, candidate, { mimeType: candidate.mimeType || existing.mimeType });
      else if (!existing.mimeType) existing.mimeType = candidate.mimeType;
    } else {
      seen.set(parsed.href, candidate);
      sources.push(candidate);
    }
  }
  const roots = [document];
  const media = [];
  for (let index = 0; index < roots.length && index < 100; index++) {
    const root = roots[index];
    media.push(...root.querySelectorAll('video, audio'));
    for (const element of root.querySelectorAll('*')) {
      if (element.shadowRoot) roots.push(element.shadowRoot);
    }
  }
  let videoIndex = 0;
  let audioIndex = 0;
  // Do not reoffer a URL from a known encrypted element as a network candidate.
  for (const element of media) {
    if (!element.mediaKeys) continue;
    for (const raw of [element.currentSrc, element.getAttribute('src'), ...[...element.querySelectorAll('source')].map((source) => source.src)]) {
      if (!raw) continue;
      try {
        const parsed = new URL(raw, document.baseURI);
        parsed.hash = '';
        encryptedUrls.add(parsed.href);
      } catch { /* Ignore malformed media URLs. */ }
    }
  }
  for (const element of media) {
    const audio = element.tagName.toLowerCase() === 'audio';
    const number = audio ? ++audioIndex : ++videoIndex;
    const playing = !element.paused && !element.ended;
    const label = `${playing ? 'Playing ' : ''}${audio ? 'audio' : 'video'} ${number}`;
    if (element.mediaKeys) { blocked.encrypted++; continue; }
    const childSources = [...element.querySelectorAll('source')];
    const activeType = childSources.find((source) => source.src === element.currentSrc)?.type || '';
    add(element.currentSrc, { label, playing, mimeType: activeType, fromNetwork: false });
    add(element.getAttribute('src'), { label, playing, mimeType: element.getAttribute('type') || '', fromNetwork: false });
    for (const source of childSources) add(source.src, { label, playing: playing && source.src === element.currentSrc, mimeType: source.type, fromNetwork: false });
    if (!element.currentSrc && !element.getAttribute('src') && !childSources.length) blocked.empty++;
  }
  // Resource entries are candidate URLs; a playlist may still need cookies, DRM, or a format the TV cannot play.
  for (const resource of performance.getEntriesByType('resource')) {
    try {
      if (/\.(mp4|m4v|webm|m3u8|mpd|mp3|m4a|ogg|ogv)$/i.test(new URL(resource.name).pathname)) {
        add(resource.name, { label: 'Network candidate', playing: false, mimeType: '', fromNetwork: true });
      }
    } catch { /* Ignore malformed resource URLs. */ }
  }
  sources.sort((a, b) => Number(b.playing) - Number(a.playing) || Number(a.fromNetwork) - Number(b.fromNetwork));
  return { sources: sources.slice(0, 100), blocked, pageTitle };
})();

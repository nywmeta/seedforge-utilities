'use strict';

const NATIVE_HOST = 'com.lancast.bridge';
const MAX_URL_LENGTH = 8192;
const MAX_LOCATION_LENGTH = 4096;

class RequestError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function trustedPopup(sender) {
  return sender.id === chrome.runtime.id && sender.url === chrome.runtime.getURL('popup.html');
}

function requireString(value, label, maximum) {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum) {
    throw new RequestError('INVALID_REQUEST', `${label} is missing or too long.`);
  }
  return value.trim();
}

function requireHttpUrl(value, label, maximum = MAX_URL_LENGTH) {
  const text = requireString(value, label, maximum);
  let parsed;
  try { parsed = new URL(text); } catch {
    throw new RequestError('INVALID_URL', `${label} must be a complete http:// or https:// URL.`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password) {
    throw new RequestError('INVALID_URL', `${label} must use HTTP or HTTPS without a username or password.`);
  }
  if (parsed.hash) parsed.hash = '';
  return parsed.href;
}

function nativePayload(message) {
  switch (message.action) {
    case 'ping': return { action: 'ping' };
    case 'open_file_cast': return { action: 'open_file_cast' };
    case 'discover': return { action: 'discover', timeout: 4 };
    case 'addDevice': {
      const address = requireString(message.address, 'TV address', MAX_LOCATION_LENGTH);
      if (/\s/.test(address) || address.includes('@') || address.includes('#')) {
        throw new RequestError('INVALID_ADDRESS', 'Enter the TV’s IP address or complete device description URL.');
      }
      return { action: 'addDevice', address };
    }
    case 'cast': {
      const title = typeof message.title === 'string' ? message.title.slice(0, 500) : 'Video';
      const mimeType = typeof message.mimeType === 'string' && /^[a-z0-9.+-]+\/[a-z0-9.+-]+$/i.test(message.mimeType)
        ? message.mimeType : '';
      return {
        action: 'cast',
        location: requireHttpUrl(message.location, 'TV description URL', MAX_LOCATION_LENGTH),
        mediaUrl: requireHttpUrl(message.mediaUrl, 'Video URL'),
        title,
        mimeType,
      };
    }
    case 'status': return {
      action: 'status', location: requireHttpUrl(message.location, 'TV description URL', MAX_LOCATION_LENGTH),
    };
    case 'control': {
      if (!['play', 'pause', 'stop', 'seek'].includes(message.command)) {
        throw new RequestError('INVALID_COMMAND', 'Unknown playback command.');
      }
      const payload = {
        action: 'control', location: requireHttpUrl(message.location, 'TV description URL', MAX_LOCATION_LENGTH),
        command: message.command,
      };
      if (message.command === 'seek') {
        if (typeof message.position !== 'number' || !Number.isFinite(message.position) || message.position < 0 || message.position > 864000) {
          throw new RequestError('INVALID_POSITION', 'Seek position must be a valid number of seconds.');
        }
        payload.position = message.position;
      }
      return payload;
    }
    default: throw new RequestError('INVALID_REQUEST', 'Unknown request.');
  }
}

function nativeRequest(payload) {
  return new Promise((resolve, reject) => {
    let port;
    let settled = false;
    let timer;
    const finish = (error, result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (port) {
        try { port.disconnect(); } catch { /* Already closed. */ }
      }
      error ? reject(error) : resolve(result);
    };
    try {
      port = chrome.runtime.connectNative(NATIVE_HOST);
      timer = setTimeout(() => finish(new RequestError('HELPER_TIMEOUT',
        'The helper did not respond in time. Check the TV’s network connection and try again.')),
      payload.action === 'discover' ? 20000 : 30000);
      port.onMessage.addListener((reply) => {
        if (!reply || typeof reply !== 'object' || typeof reply.ok !== 'boolean') {
          finish(new RequestError('INVALID_HELPER_REPLY', 'The helper returned an invalid response. Reinstall the matching helper.'));
        } else {
          finish(null, reply);
        }
      });
      port.onDisconnect.addListener(() => {
        const reason = chrome.runtime.lastError?.message || 'The connection to the helper closed before it replied.';
        if (!settled) {
          const missing = /not found|not registered|access to the specified native messaging host is forbidden/i.test(reason);
          finish(new RequestError(missing ? 'HELPER_MISSING' : 'HELPER_DISCONNECTED', reason));
        }
      });
      port.postMessage(payload);
    } catch (error) {
      finish(new RequestError('HELPER_UNAVAILABLE', error.message || 'Could not start the local helper.'));
    }
  });
}

function scanError(message) {
  if (/cannot access|permission|chrome:|edge:|web store/i.test(message)) {
    return 'Open a normal video webpage and click the extension there. The browser blocks scans on internal pages and some protected pages.';
  }
  return 'Could not scan this page. Reload the webpage, start the video, and try again.';
}

async function scanActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new RequestError('NO_ACTIVE_TAB', 'Open a video webpage first.');
  let results;
  let frameWarning = '';
  try {
    results = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ['media.js'] });
  } catch (error) {
    // activeTab may not grant access to a video embedded from another origin.
    // Retry the main document so one inaccessible frame cannot hide its videos.
    try {
      results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['media.js'] });
      frameWarning = 'Some embedded frames could not be scanned. Open the player’s own page in a new tab, start the video there, and scan again.';
    } catch {
      throw new RequestError('SCAN_BLOCKED', scanError(error.message || ''));
    }
  }
  // Some browsers skip inaccessible frames without rejecting the injection.
  // Report only whether cross-origin embeds exist; no frame URLs are returned.
  try {
    const [embedded] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => [...document.querySelectorAll('iframe[src]')].some((frame) => {
        try {
          const url = new URL(frame.getAttribute('src'), document.baseURI);
          return ['http:', 'https:'].includes(url.protocol) && url.origin !== location.origin;
        } catch { return false; }
      }),
    });
    if (embedded?.result === true && !frameWarning) {
      frameWarning = 'This page has content embedded from another site. If the video is missing, open the player’s own page in a new tab, start it there, and scan again.';
    }
  } catch { /* Keep the media scan usable if the embed check is unavailable. */ }
  const sources = [];
  const seen = new Map();
  const blocked = { blob: 0, data: 0, encrypted: 0, empty: 0 };
  let pageTitle = tab.title || 'Video';
  let frameCount = 0;
  for (const entry of results) {
    const result = entry.result;
    if (!result || !Array.isArray(result.sources)) continue;
    frameCount++;
    if (entry.frameId === 0 && typeof result.pageTitle === 'string') pageTitle = result.pageTitle;
    for (const key of Object.keys(blocked)) blocked[key] += Math.max(0, Number(result.blocked?.[key]) || 0);
    for (const source of result.sources) {
      if (!source || typeof source.url !== 'string') continue;
      let url;
      try { url = requireHttpUrl(source.url, 'Video URL'); } catch { continue; }
      const candidate = {
        url,
        title: typeof source.title === 'string' ? source.title.slice(0, 500) : pageTitle,
        label: typeof source.label === 'string' ? source.label.slice(0, 300) : 'Video stream',
        mimeType: typeof source.mimeType === 'string' ? source.mimeType.slice(0, 100) : '',
        playing: source.playing === true,
        fromNetwork: source.fromNetwork === true,
        frameId: entry.frameId,
      };
      const existing = seen.get(url);
      if (existing) {
        // A paused copy or network entry may precede the active video in another frame.
        const preferred = Number(candidate.playing) - Number(existing.playing)
          || Number(existing.fromNetwork) - Number(candidate.fromNetwork);
        if (preferred > 0) Object.assign(existing, candidate, { mimeType: candidate.mimeType || existing.mimeType });
        else if (!existing.mimeType) existing.mimeType = candidate.mimeType;
      } else {
        seen.set(url, candidate);
        sources.push(candidate);
      }
    }
  }
  sources.sort((a, b) => Number(b.playing) - Number(a.playing) || Number(a.fromNetwork) - Number(b.fromNetwork));
  return { ok: true, sources: sources.slice(0, 100), blocked, pageTitle, frameCount, frameWarning };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!trustedPopup(sender)) return false;
  const run = async () => {
    if (!message || typeof message !== 'object' || Array.isArray(message)) {
      throw new RequestError('INVALID_REQUEST', 'Invalid request.');
    }
    if (message.action === 'scan') return scanActiveTab();
    return nativeRequest(nativePayload(message));
  };
  run().then(sendResponse, (error) => sendResponse({
    ok: false,
    error: { code: error.code || 'REQUEST_FAILED', message: error.message || 'The request failed.' },
  }));
  return true;
});

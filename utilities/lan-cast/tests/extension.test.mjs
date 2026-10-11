import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const extensionRoot = new URL('../extension/', import.meta.url);
const backgroundCode = fs.readFileSync(new URL('background.js', extensionRoot), 'utf8');
const mediaCode = fs.readFileSync(new URL('media.js', extensionRoot), 'utf8');
const popupCode = fs.readFileSync(new URL('popup.js', extensionRoot), 'utf8');
const popupHtml = fs.readFileSync(new URL('popup.html', extensionRoot), 'utf8');
const setupCode = fs.readFileSync(new URL('setup.js', extensionRoot), 'utf8');
const setupHtml = fs.readFileSync(new URL('setup.html', extensionRoot), 'utf8');
const extensionId = 'a'.repeat(32);
const popupSender = { id: extensionId, url: `chrome-extension://${extensionId}/popup.html` };

function background({ reply = { ok: true }, disconnectError = null, silent = false, executeScript } = {}) {
  let messageListener;
  let lastError;
  let lastErrorReads = 0;
  let disconnects = 0;
  const requests = [];
  const timers = new Map();
  let timerId = 0;
  const runtime = {
    id: extensionId,
    getURL: (path) => `chrome-extension://${extensionId}/${path}`,
    onMessage: { addListener: (callback) => { messageListener = callback; } },
    get lastError() { lastErrorReads++; return lastError; },
    connectNative: (host) => {
      assert.equal(host, 'com.lancast.bridge');
      const callbacks = { message: [], disconnect: [] };
      return {
        onMessage: { addListener: (callback) => callbacks.message.push(callback) },
        onDisconnect: { addListener: (callback) => callbacks.disconnect.push(callback) },
        disconnect: () => {
          disconnects++;
          callbacks.disconnect.forEach((callback) => callback());
        },
        postMessage: (payload) => {
          requests.push(payload);
          if (silent) return;
          queueMicrotask(() => {
            if (disconnectError) {
              lastError = { message: disconnectError };
              callbacks.disconnect.forEach((callback) => callback());
              lastError = undefined;
            } else {
              callbacks.message.forEach((callback) => callback(reply));
            }
          });
        },
      };
    },
  };
  const chrome = {
    runtime,
    tabs: { query: async () => [{ id: 12, title: 'Example video' }] },
    scripting: { executeScript: executeScript || (async () => []) },
  };
  const context = vm.createContext({
    chrome, URL, setTimeout: (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: (id) => timers.delete(id),
  });
  vm.runInContext(backgroundCode, context);
  return {
    context, requests, timers,
    get disconnects() { return disconnects; },
    get lastErrorReads() { return lastErrorReads; },
    listener: (...args) => messageListener(...args),
    send: (message, sender = popupSender) => new Promise((resolve) => {
      const accepted = messageListener(message, sender, resolve);
      if (!accepted) resolve(undefined);
    }),
  };
}

function media({ elements = [], resources = [], base = 'https://video.example/watch' } = {}) {
  const document = {
    title: 'Example video', baseURI: base,
    querySelectorAll: (selector) => selector === 'video, audio' ? elements : [],
  };
  const context = vm.createContext({ document, URL, performance: { getEntriesByType: () => resources.map((name) => ({ name })) } });
  return vm.runInContext(mediaCode, context);
}

function element({ currentSrc = '', src = '', sources = [], mediaKeys = null, tagName = 'VIDEO', paused = false, ended = false } = {}) {
  return {
    currentSrc, mediaKeys, tagName, paused, ended,
    getAttribute: (key) => key === 'src' ? src : null,
    querySelectorAll: () => sources,
  };
}

async function popup({ saved = {}, onRequest = async () => ({ ok: true }), onOpenTab = async () => ({ id: 1 }) } = {}) {
  class MockElement {
    value = '';
    textContent = '';
    className = '';
    hidden = false;
    disabled = false;
    open = false;
    listeners = new Map();
    attributes = new Map();
    options = [];
    addEventListener(type, callback) { this.listeners.set(type, callback); }
    setAttribute(name, value) { this.attributes.set(name, value); }
    replaceChildren() { this.options = []; this.value = ''; }
    add(option) { this.options.push(option); if (!this.value) this.value = option.value; }
  }
  const elements = Object.fromEntries([...popupHtml.matchAll(/\bid="([^"]+)"/g)].map((match) => [match[1], new MockElement()]));
  elements['transport-state'].textContent = 'TV playback';
  elements['playback-time'].textContent = '—';
  const requests = [];
  const openedTabs = [];
  const storage = { ...saved };
  const context = vm.createContext({
    URL,
    document: { getElementById: (id) => elements[id] },
    Option: class { constructor(text, value) { this.text = text; this.value = value; } },
    chrome: {
      storage: { local: { get: async () => storage, set: async (values) => Object.assign(storage, values) } },
      runtime: { sendMessage: async (request) => { requests.push(request); return onRequest(request); } },
      tabs: { create: async (options) => { openedTabs.push(options); return onOpenTab(options); } },
    },
  });
  vm.runInContext(popupCode, context);
  await new Promise(setImmediate);
  return {
    elements, requests, openedTabs, storage, context,
    click: async (id) => { await elements[id].listeners.get('click')(); await new Promise(setImmediate); },
    change: async (id, value) => { elements[id].value = value; await elements[id].listeners.get('change')(); await new Promise(setImmediate); },
  };
}

const testDevice = { id: 'uuid:test', name: 'Test TV', location: 'http://192.168.1.50/device.xml', model: 'Media Renderer', manufacturer: 'Example' };
const testSource = { url: 'https://cdn.example/movie.mp4', title: 'Movie', label: 'Playing video 1 · MP4', mimeType: 'video/mp4', playing: true };
function normalPopupReply(request) {
  switch (request.action) {
    case 'ping': return { ok: true };
    case 'discover': return { ok: true, devices: [testDevice] };
    case 'scan': return { ok: true, sources: [testSource], blocked: {}, pageTitle: 'Movie' };
    case 'status': return { ok: true, transportState: 'PLAYING', position: 100, duration: 600 };
    default: return { ok: true };
  }
}

function setup({ platform = 'MacIntel', userAgent = 'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36', brands } = {}) {
  const elements = Object.fromEntries([...setupHtml.matchAll(/\bid="([^"]+)"/g)].map((match) => [match[1], {
    textContent: '', value: '', listeners: new Map(),
    addEventListener(type, callback) { this.listeners.set(type, callback); },
  }]));
  const copied = [];
  vm.runInNewContext(setupCode, {
    document: { getElementById: (id) => elements[id] },
    navigator: { platform, userAgent, userAgentData: brands ? { brands } : undefined,
      clipboard: { writeText: async (text) => copied.push(text) } },
    chrome: { runtime: { id: extensionId } },
  });
  return {
    elements, copied,
    choose: (value) => { elements.browser.value = value; elements.browser.listeners.get('change')(); },
    copy: async () => { await elements['copy-command'].listeners.get('click')(); },
  };
}

test('manifest requests only the required permissions and uses MV3', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('manifest.json', extensionRoot), 'utf8'));
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions, ['activeTab', 'scripting', 'nativeMessaging', 'storage']);
  assert.equal(manifest.host_permissions, undefined);
  assert.equal(manifest.content_scripts, undefined);
  assert.equal(manifest.externally_connectable, undefined);
  for (const icon of Object.values(manifest.icons)) assert.ok(fs.existsSync(new URL(icon, extensionRoot)));
});

test('only the extension popup may send privileged requests', async () => {
  const host = background();
  for (const sender of [
    { id: 'other', url: popupSender.url },
    { id: extensionId, url: 'https://video.example/watch' },
    { id: extensionId, url: `chrome-extension://${extensionId}/setup.html` },
    { id: extensionId },
  ]) assert.equal(host.listener({ action: 'discover' }, sender, () => {}), false);
  assert.equal(host.requests.length, 0);
  assert.equal((await host.send({ action: 'ping' })).ok, true);
  assert.equal(host.requests.length, 1);
});

test('unknown actions and malformed messages never reach the native host', async () => {
  const host = background();
  for (const message of [null, [], { action: 'executeScript' }, { action: 'launch', command: 'rm' }]) {
    const result = await host.send(message);
    assert.equal(result.ok, false);
    assert.equal(result.error.code, 'INVALID_REQUEST');
  }
  assert.equal(host.requests.length, 0);
});

test('native payloads omit arbitrary fields and use a fixed discovery timeout', async () => {
  const host = background();
  await host.send({ action: 'discover', timeout: 3600, shell: 'arbitrary' });
  assert.deepEqual(JSON.parse(JSON.stringify(host.requests[0])), { action: 'discover', timeout: 4 });
});

test('downloaded video companion request forwards only its whitelisted action', async () => {
  const host = background();
  const reply = await host.send({ action: 'open_file_cast', path: '/private/file', url: 'https://example.test', shell: 'arbitrary' });
  assert.equal(reply.ok, true);
  assert.deepEqual(JSON.parse(JSON.stringify(host.requests[0])), { action: 'open_file_cast' });
});

test('cast rejects unsupported or authenticated URLs before opening the native host', async () => {
  const host = background();
  for (const mediaUrl of ['blob:https://example/video', 'data:video/mp4,abc', 'file:///etc/passwd', 'https://user:password@example/video.mp4', 'not a URL']) {
    const reply = await host.send({ action: 'cast', location: 'http://192.168.1.50/device.xml', mediaUrl });
    assert.equal(reply.ok, false);
    assert.equal(reply.error.code, 'INVALID_URL');
  }
  assert.equal(host.requests.length, 0);
});

test('URL length limits match the native helper', async () => {
  const host = background();
  const reply = await host.send({ action: 'cast', location: 'http://192.168.1.50/device.xml', mediaUrl: `https://example/video.mp4?x=${'x'.repeat(8192)}` });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'INVALID_REQUEST');
  assert.equal(host.requests.length, 0);
});

test('cast removes fragments, bounds titles, and discards malformed MIME types', async () => {
  const host = background();
  assert.equal((await host.send({ action: 'cast', location: 'http://192.168.1.50/device.xml#x', mediaUrl: 'https://example/video.mp4#t=1', title: 't'.repeat(600), mimeType: 'video/mp4\r\nInjected: yes', extra: 'ignored' })).ok, true);
  const payload = host.requests[0];
  assert.equal(payload.location, 'http://192.168.1.50/device.xml');
  assert.equal(payload.mediaUrl, 'https://example/video.mp4');
  assert.equal(payload.title.length, 500);
  assert.equal(payload.mimeType, '');
  assert.equal(payload.extra, undefined);
});

test('controls reject unknown commands and invalid seek positions', async () => {
  const host = background();
  for (const request of [
    { command: 'execute' }, { command: 'seek', position: -1 },
    { command: 'seek', position: NaN }, { command: 'seek', position: '15' },
  ]) {
    assert.equal((await host.send({ action: 'control', location: 'http://192.168.1.50/device.xml', ...request })).ok, false);
  }
  assert.equal(host.requests.length, 0);
  assert.equal((await host.send({ action: 'control', location: 'http://192.168.1.50/device.xml', command: 'seek', position: 15 })).ok, true);
  assert.equal(host.requests[0].position, 15);
});

test('native response closes the port and consumes disconnect lastError', async () => {
  const host = background({ reply: { ok: true, version: '1.0.0' } });
  const reply = await host.send({ action: 'ping' });
  assert.equal(reply.version, '1.0.0');
  assert.equal(host.disconnects, 1);
  assert.equal(host.timers.size, 0);
  assert.ok(host.lastErrorReads >= 1);
});

test('missing helper is reported without claiming success', async () => {
  const host = background({ disconnectError: 'Specified native messaging host not found.' });
  const reply = await host.send({ action: 'ping' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'HELPER_MISSING');
  assert.match(reply.error.message, /not found/);
  assert.equal(host.timers.size, 0);
  assert.ok(host.lastErrorReads >= 1);
});

test('invalid native reply is rejected', async () => {
  const host = background({ reply: { result: 'success' } });
  const reply = await host.send({ action: 'ping' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'INVALID_HELPER_REPLY');
  assert.equal(host.disconnects, 1);
});

test('native helper errors preserve their error code and message', async () => {
  const host = background({ reply: { ok: false, error: { code: 'SOAP_FAULT', message: 'TV rejected the format.' } } });
  const reply = await host.send({ action: 'cast', location: 'http://192.168.1.50/device.xml', mediaUrl: 'https://example/video.mp4' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'SOAP_FAULT');
  assert.equal(reply.error.message, 'TV rejected the format.');
});

test('native timeout closes the port and returns a concrete error', async () => {
  const host = background({ silent: true });
  const result = host.send({ action: 'discover' });
  assert.equal(host.timers.size, 1);
  const [{ callback, delay }] = host.timers.values();
  assert.equal(delay, 20000);
  callback();
  const reply = await result;
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'HELPER_TIMEOUT');
  assert.equal(host.disconnects, 1);
});

test('scan deduplicates frame sources and places playing media first', async () => {
  const host = background({ executeScript: async () => [
    { frameId: 0, result: { pageTitle: 'Main page', sources: [{ url: 'https://example/network.mp4', label: 'Network candidate', fromNetwork: true }], blocked: { blob: 1 } } },
    { frameId: 9, result: { sources: [{ url: 'https://example/playing.mp4', playing: true }, { url: 'https://example/network.mp4' }], blocked: { encrypted: 1 } } },
  ] });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.ok, true);
  assert.equal(reply.sources.length, 2);
  assert.equal(reply.sources[0].url, 'https://example/playing.mp4');
  assert.equal(reply.sources[0].frameId, 9);
  assert.equal(reply.pageTitle, 'Main page');
  assert.equal(reply.blocked.blob, 1);
  assert.equal(reply.blocked.encrypted, 1);
  assert.equal(host.requests.length, 0);
});

test('scan normalizes duplicate URLs and preserves the playing frame over an earlier candidate', async () => {
  const host = background({ executeScript: async () => [
    { frameId: 0, result: { sources: [{ url: 'https://example/movie.mp4#t=1', fromNetwork: true }] } },
    { frameId: 4, result: { sources: [{ url: 'https://example/movie.mp4', mimeType: 'video/mp4' }] } },
    { frameId: 9, result: { sources: [{ url: 'https://example/movie.mp4#t=30', playing: true, label: 'Playing video 1' }] } },
  ] });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.sources.length, 1);
  assert.equal(reply.sources[0].url, 'https://example/movie.mp4');
  assert.equal(reply.sources[0].playing, true);
  assert.equal(reply.sources[0].fromNetwork, false);
  assert.equal(reply.sources[0].frameId, 9);
  assert.equal(reply.sources[0].mimeType, 'video/mp4');
});

test('inaccessible embedded frames fall back to a main-document scan with a warning', async () => {
  const calls = [];
  const host = background({ executeScript: async (request) => {
    calls.push(request);
    if (request.target.allFrames) throw new Error('Cannot access contents of URL https://cross-origin.example.');
    return [{ frameId: 0, result: { sources: [{ url: 'https://example/video.mp4' }], blocked: {} } }];
  } });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.ok, true);
  assert.equal(reply.sources.length, 1);
  assert.match(reply.frameWarning, /embedded frames/);
  assert.equal(calls.length, 3);
  assert.equal(calls[1].target.allFrames, undefined);
  assert.equal(typeof calls[2].func, 'function');
});

test('silently skipped cross-origin embeds still produce useful scan guidance', async () => {
  const host = background({ executeScript: async (request) => request.func
    ? [{ frameId: 0, result: true }]
    : [{ frameId: 0, result: { sources: [], blocked: {} } }] });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.ok, true);
  assert.equal(reply.sources.length, 0);
  assert.equal(reply.frameCount, 1);
  assert.match(reply.frameWarning, /another site/);
  assert.match(reply.frameWarning, /player’s own page/);
  assert.equal(host.requests.length, 0);
});

test('embed inspection reports only a boolean and distinguishes cross-origin HTTP frames', async () => {
  let inspect;
  const host = background({ executeScript: async (request) => {
    if (request.func) inspect = request.func;
    return request.func ? [{ frameId: 0, result: false }] : [];
  } });
  await host.send({ action: 'scan' });
  const inspectFrames = (urls) => vm.runInNewContext(`(${inspect.toString()})()`, {
    URL, location: { origin: 'https://page.example' },
    document: { baseURI: 'https://page.example/watch', querySelectorAll: () => urls.map((url) => ({ getAttribute: () => url })) },
  });
  assert.equal(inspectFrames(['/player', 'https://page.example/embed', 'about:blank', 'javascript:alert(1)']), false);
  assert.equal(inspectFrames(['https://player.example/embed']), true);
});

test('unavailable embed inspection preserves an otherwise successful media scan', async () => {
  const host = background({ executeScript: async (request) => {
    if (request.func) throw new Error('Embed inspection unavailable.');
    return [{ frameId: 0, result: { sources: [testSource], blocked: {} } }];
  } });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.ok, true);
  assert.equal(reply.sources[0].url, testSource.url);
});

test('blocked browser page scans give actionable feedback', async () => {
  const host = background({ executeScript: async () => { throw new Error('Cannot access chrome://settings/'); } });
  const reply = await host.send({ action: 'scan' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'SCAN_BLOCKED');
  assert.match(reply.error.message, /normal video webpage/);
});

test('media scanner extracts and deduplicates currentSrc, src, and source elements', () => {
  const reply = media({ elements: [element({ currentSrc: 'https://cdn.example/movie.mp4', src: 'https://cdn.example/movie.mp4', sources: [{ src: 'https://cdn.example/movie.mp4', type: 'video/mp4' }, { src: 'https://cdn.example/other.webm', type: 'video/webm' }] })] });
  assert.equal(reply.sources.length, 2);
  assert.equal(reply.sources[0].mimeType, 'video/mp4');
  assert.equal(reply.sources[0].playing, true);
  assert.equal(reply.sources[1].playing, false);
});

test('media scanner resolves relative media URLs', () => {
  const reply = media({ elements: [element({ src: '/video/movie.mp4' })] });
  assert.equal(reply.sources[0].url, 'https://video.example/video/movie.mp4');
});

test('scanner preserves the playing element when a paused duplicate precedes it', () => {
  const reply = media({ elements: [
    element({ currentSrc: 'https://cdn.example/movie.mp4', paused: true }),
    element({ currentSrc: 'https://cdn.example/movie.mp4', paused: false }),
  ] });
  assert.equal(reply.sources.length, 1);
  assert.equal(reply.sources[0].playing, true);
  assert.match(reply.sources[0].label, /^Playing video 2/);
});

test('scanner retains active playback when a page has more than 100 media elements', () => {
  const elements = Array.from({ length: 100 }, (_, index) => element({
    currentSrc: `https://cdn.example/paused-${index}.mp4`, paused: true,
  }));
  elements.push(element({ currentSrc: 'https://cdn.example/playing.mp4' }));
  const reply = media({ elements });
  assert.equal(reply.sources.length, 100);
  assert.equal(reply.sources[0].url, 'https://cdn.example/playing.mp4');
  assert.equal(reply.sources[0].playing, true);
});

test('blob/data URLs are excluded and reported; empty media is counted', () => {
  const reply = media({ elements: [
    element({ currentSrc: 'blob:https://example/abc' }),
    element({ src: 'data:video/mp4;base64,AAAA' }),
    element(),
  ] });
  assert.equal(reply.sources.length, 0);
  assert.equal(reply.blocked.blob, 1);
  assert.equal(reply.blocked.data, 1);
  assert.equal(reply.blocked.empty, 1);
});

test('DRM media elements are excluded; network manifests remain explicitly unverified candidates', () => {
  const reply = media({
    elements: [element({ currentSrc: 'https://cdn.example/protected.mp4', mediaKeys: {} })],
    resources: ['https://cdn.example/manifest.mpd'],
  });
  assert.equal(reply.blocked.encrypted, 1);
  assert.equal(reply.sources.length, 1);
  assert.match(reply.sources[0].label, /^Network candidate/);
  assert.equal(reply.sources[0].fromNetwork, true);
  assert.equal(reply.sources[0].mimeType, 'application/dash+xml');
  assert.ok(!reply.sources.some((source) => source.url.endsWith('protected.mp4')));
});

test('known encrypted URLs cannot return through resource entries or duplicate elements', () => {
  const reply = media({
    elements: [
      element({ currentSrc: 'https://cdn.example/protected.mp4' }),
      element({ currentSrc: 'https://cdn.example/protected.mp4#t=1', sources: [{ src: 'https://cdn.example/protected.m3u8', type: 'application/vnd.apple.mpegurl' }], mediaKeys: {} }),
    ],
    resources: ['https://cdn.example/protected.mp4', 'https://cdn.example/protected.m3u8', 'https://cdn.example/unverified.mpd'],
  });
  assert.equal(reply.blocked.encrypted, 1);
  assert.equal(reply.sources.length, 1);
  assert.equal(reply.sources[0].url, 'https://cdn.example/unverified.mpd');
});

test('scanner rejects credentials, non-HTTP schemes, and ordinary non-media network resources', () => {
  const reply = media({
    elements: [element({ src: 'https://user:password@example/video.mp4' }), element({ src: 'file:///movie.mp4' })],
    resources: ['https://cdn.example/app.js', 'https://cdn.example/segment.ts', 'https://cdn.example/photo.png', 'https://cdn.example/master.m3u8?token=abc'],
  });
  assert.equal(reply.sources.length, 1);
  assert.equal(reply.sources[0].url, 'https://cdn.example/master.m3u8?token=abc');
  assert.equal(reply.sources[0].mimeType, 'application/vnd.apple.mpegurl');
});

test('scanner reads media in open shadow roots', () => {
  const nested = element({ src: 'https://cdn.example/shadow.mp4' });
  const shadowRoot = { querySelectorAll: (selector) => selector === 'video, audio' ? [nested] : [] };
  const document = {
    title: 'Shadow video', baseURI: 'https://video.example/',
    querySelectorAll: (selector) => selector === '*' ? [{ shadowRoot }] : [],
  };
  const reply = vm.runInNewContext(mediaCode, { document, URL, performance: { getEntriesByType: () => [] } });
  assert.equal(reply.sources.length, 1);
  assert.equal(reply.sources[0].url, 'https://cdn.example/shadow.mp4');
});

test('popup missing-helper feedback keeps scan available and casting disabled', async () => {
  const ui = await popup({ onRequest: async () => ({ ok: false, error: { code: 'HELPER_MISSING', message: 'Specified native messaging host not found.' } }) });
  assert.equal(ui.elements['helper-help'].hidden, false);
  assert.equal(ui.elements['retry-helper'].hidden, false);
  assert.equal(ui.elements.scan.disabled, false);
  assert.equal(ui.elements.discover.disabled, true);
  assert.equal(ui.elements['file-cast'].disabled, true);
  assert.equal(ui.elements.cast.disabled, true);
  assert.match(ui.elements.notice.textContent, /not found/);
});

test('downloaded video companion opens without choosing a stream or a TV', async () => {
  const url = `http://127.0.0.1:40500/${'a'.repeat(43)}/`;
  const ui = await popup({ onRequest: (request) => request.action === 'open_file_cast'
    ? { ok: true, url } : normalPopupReply(request) });
  assert.equal(ui.elements['file-cast'].disabled, false);
  assert.equal(ui.elements.cast.disabled, true);
  await ui.click('file-cast');
  assert.equal(ui.openedTabs.length, 1);
  assert.equal(ui.openedTabs[0].url, url);
  const companionRequest = ui.requests.find((request) => request.action === 'open_file_cast');
  assert.deepEqual(JSON.parse(JSON.stringify(companionRequest)), { action: 'open_file_cast' });
  assert.match(ui.elements.notice.textContent, /new tab/);
  assert.equal(ui.elements['transport-state'].textContent, 'TV playback');
  assert.ok(!Object.values(ui.storage).includes(url));
});

test('companion rejects non-literal loopback origins and malformed token URLs before opening a tab', async () => {
  const token = 'a'.repeat(43);
  for (const url of [
    undefined, 42, `https://127.0.0.1:40500/${token}/`, `http://localhost:40500/${token}/`,
    `http://127.0.0.2:40500/${token}/`, `http://[::1]:40500/${token}/`, `http://127.1:40500/${token}/`,
    `http://2130706433:40500/${token}/`, `http://0x7f000001:40500/${token}/`, `http://127.0.0.1/${token}/`,
    `http://127.0.0.1:0/${token}/`, `http://127.0.0.1:65536/${token}/`, `http://127.0.0.1:040500/${token}/`,
    `http://user@127.0.0.1:40500/${token}/`, `http://127.0.0.1:40500/${token}/?x=1`,
    `http://127.0.0.1:40500/${token}/#x`, 'http://127.0.0.1:40500/short/',
    `http://127.0.0.1:40500/${'a'.repeat(129)}/`, `http://127.0.0.1:40500/${token}/extra/`,
    `http://127.0.0.1:40500/${token}`, `http://127.0.0.1:40500/%61${token}/`,
  ]) {
    const ui = await popup({ onRequest: (request) => request.action === 'open_file_cast'
      ? { ok: true, url } : normalPopupReply(request) });
    await ui.click('file-cast');
    assert.equal(ui.openedTabs.length, 0, String(url));
    assert.equal(ui.elements.notice.className, 'notice error');
    assert.match(ui.elements.notice.textContent, /invalid local video page/);
  }
});

test('companion failures do not open a tab or claim casting success', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'open_file_cast'
    ? { ok: false, error: { code: 'HELPER_MISSING', message: 'Local helper is missing.' } }
    : normalPopupReply(request) });
  await ui.click('file-cast');
  assert.equal(ui.openedTabs.length, 0);
  assert.equal(ui.elements.notice.textContent, 'Local helper is missing.');
  assert.equal(ui.elements['file-cast'].disabled, true);
  assert.equal(ui.elements['transport-state'].textContent, 'TV playback');
});

test('an older helper gives a concrete update instruction for downloaded videos', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'open_file_cast'
    ? { ok: false, error: { code: 'UNKNOWN_ACTION', message: 'Unknown bridge action.' } }
    : normalPopupReply(request) });
  await ui.click('file-cast');
  assert.equal(ui.openedTabs.length, 0);
  assert.match(ui.elements.notice.textContent, /helper needs an update/);
  assert.match(ui.elements.notice.textContent, /helper installer/);
});

test('blocked companion tab creation reports its error', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'open_file_cast'
    ? { ok: true, url: `http://127.0.0.1:40500/${'a'.repeat(43)}/` } : normalPopupReply(request),
  onOpenTab: async () => { throw new Error('The browser blocked opening this tab.'); } });
  await ui.click('file-cast');
  assert.equal(ui.elements.notice.className, 'notice error');
  assert.equal(ui.elements.notice.textContent, 'The browser blocked opening this tab.');
});

test('missing-stream and blob feedback explain player-page scanning and normal downloads', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'scan'
    ? { ok: true, sources: [], blocked: { blob: 1 }, frameWarning: 'Open the player’s own page.' }
    : normalPopupReply(request) });
  await ui.click('scan');
  const feedback = ui.elements['source-summary'].textContent;
  assert.match(feedback, /player’s own page/);
  assert.match(feedback, /normal Download button/);
  assert.match(feedback, /Cast a downloaded video/);
  assert.match(feedback, /browser-only blob\/data/);
  assert.match(feedback, /protected playback remains unsupported/);
});

test('popup enables casting only after a valid stream and renderer exist', async () => {
  const ui = await popup({ onRequest: normalPopupReply });
  assert.equal(ui.elements.cast.disabled, true);
  await ui.click('scan');
  assert.equal(ui.elements.cast.disabled, true);
  await ui.click('discover');
  assert.equal(ui.elements.cast.disabled, false);
  assert.match(ui.elements['source-summary'].textContent, /unverified/);
});

test('failed casting displays helper error and never reports playing or pauses the page', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'cast'
    ? { ok: false, error: { code: 'SOAP_FAULT', message: 'TV rejected the format.' } }
    : normalPopupReply(request) });
  await ui.click('scan');
  await ui.click('discover');
  await ui.click('cast');
  assert.equal(ui.elements.notice.className, 'notice error');
  assert.equal(ui.elements.notice.textContent, 'TV rejected the format.');
  assert.equal(ui.elements['transport-state'].textContent, 'TV playback');
  assert.equal(ui.elements.cast.disabled, false);
  assert.ok(!ui.requests.some((request) => request.action === 'control' || request.action === 'status'));
});

test('successful cast reports actual TV status and preserves the correct direct media request', async () => {
  const ui = await popup({ onRequest: normalPopupReply });
  await ui.click('scan');
  await ui.click('discover');
  await ui.click('cast');
  assert.equal(ui.elements['transport-state'].textContent, 'Playing on TV');
  assert.equal(ui.elements['playback-time'].textContent, '1:40 / 10:00');
  assert.match(ui.elements.notice.textContent, /accepted the stream and play command/);
  const cast = ui.requests.find((request) => request.action === 'cast');
  assert.equal(cast.mediaUrl, testSource.url);
  assert.equal(cast.location, testDevice.location);
  assert.equal(cast.mimeType, testSource.mimeType);
  assert.equal(ui.storage.selectedDeviceLocation, testDevice.location);
});

test('rediscovery clears playback status when the selected TV changes or disappears', async () => {
  for (const devices of [[{ ...testDevice, location: 'http://192.168.1.51/device.xml', name: 'Other TV' }], []]) {
    let discovered = [testDevice];
    const ui = await popup({ onRequest: (request) => request.action === 'discover'
      ? { ok: true, devices: discovered } : normalPopupReply(request) });
    await ui.click('scan');
    await ui.click('discover');
    await ui.click('cast');
    assert.equal(ui.elements['transport-state'].textContent, 'Playing on TV');
    discovered = devices;
    await ui.click('discover');
    assert.equal(ui.elements['transport-state'].textContent, 'TV playback');
    assert.equal(ui.elements['playback-time'].textContent, '—');
  }
});

test('accepted commands with an unreadable status do not invent playback success', async () => {
  const ui = await popup({ onRequest: (request) => request.action === 'status'
    ? { ok: false, error: { code: 'SOAP_FAULT', message: 'Status unavailable.' } }
    : normalPopupReply(request) });
  await ui.click('scan');
  await ui.click('discover');
  await ui.click('cast');
  assert.equal(ui.elements['transport-state'].textContent, 'Play command accepted');
  assert.match(ui.elements.notice.textContent, /status could not be read/);
  await ui.click('pause');
  assert.equal(ui.elements['transport-state'].textContent, 'Pause command accepted');
  assert.match(ui.elements.notice.textContent, /accepted the pause command/);
});

test('saved direct URL opens its field; explicit source selection replaces the pasted URL', async () => {
  const ui = await popup({ saved: { directMediaUrl: 'https://cdn.example/saved.mp4' }, onRequest: normalPopupReply });
  assert.equal(ui.elements['direct-source'].open, true);
  await ui.click('scan');
  await ui.change('source', testSource.url);
  assert.equal(ui.elements['media-url'].value, '');
  assert.equal(ui.storage.directMediaUrl, '');
  assert.equal(ui.storage.selectedSourceUrl, testSource.url);
});

test('setup provides distinct Opera GX and Opera installer choices', () => {
  assert.match(setupHtml, /<option value="opera-gx">Opera GX<\/option>/);
  assert.match(setupHtml, /<option value="opera">Opera<\/option>/);
  assert.match(setupHtml, /<option value="chrome">Google Chrome<\/option>/);
  assert.match(setupHtml, /<option value="edge">Microsoft Edge<\/option>/);
});

test('shared OPR user agent does not infer GX; choosing GX builds the Mac command', async () => {
  const ui = setup({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X) Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0' });
  assert.equal(ui.elements.browser.value, 'opera');
  assert.match(ui.elements['browser-hint'].textContent, /If this is Opera GX, select Opera GX/);
  assert.equal(ui.elements['extension-id'].textContent, extensionId);
  ui.choose('opera-gx');
  assert.equal(ui.elements['install-command'].textContent,
    `python3 helper/install.py --extension-id ${extensionId} --browser opera-gx`);
  await ui.copy();
  assert.equal(ui.copied[0], ui.elements['install-command'].textContent);
  assert.match(ui.elements['copy-state'].textContent, /Command copied/);
});

test('an explicit Opera GX brand can select GX without treating all Opera browsers as GX', () => {
  const ui = setup({ userAgent: 'Mozilla/5.0 Chrome/130.0.0.0 OPR/115.0.0.0', brands: [{ brand: 'Chromium', version: '130' }, { brand: 'Opera GX', version: '115' }] });
  assert.equal(ui.elements.browser.value, 'opera-gx');
  assert.match(ui.elements['install-command'].textContent, /--browser opera-gx$/);
  const regular = setup({ userAgent: 'Mozilla/5.0 Chrome/130.0.0.0 OPR/115.0.0.0', brands: [{ brand: 'Opera', version: '115' }] });
  assert.equal(regular.elements.browser.value, 'opera');
});

test('setup preserves Chrome/Edge detection and generates OS-specific installer commands', () => {
  const chrome = setup();
  assert.equal(chrome.elements.browser.value, 'chrome');
  assert.match(chrome.elements['install-command'].textContent, /^python3 .*--browser chrome$/);
  const edge = setup({ platform: 'Win32', userAgent: 'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0' });
  assert.equal(edge.elements.browser.value, 'edge');
  assert.match(edge.elements['install-command'].textContent, /^py -3 .*--browser edge$/);
  edge.choose('opera-gx');
  assert.match(edge.elements['install-command'].textContent, /^py -3 .*--browser opera-gx$/);
  const linux = setup({ platform: 'Linux x86_64', userAgent: 'Mozilla/5.0 Chrome/130.0.0.0 OPR/115.0.0.0' });
  linux.choose('opera');
  assert.match(linux.elements['install-command'].textContent, /^python3 .*--browser opera$/);
  assert.match(linux.elements['platform-hint'].textContent, /On Linux/);
});

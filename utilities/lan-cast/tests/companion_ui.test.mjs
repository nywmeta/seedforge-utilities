import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../helper/file_cast.py', import.meta.url), 'utf8');
const html = source.split("UI = r'''")[1].split("'''", 1)[0];
const script = html.match(/<script nonce="__NONCE__">([\s\S]*?)<\/script>/)[1]
  .replace('__CONFIG__', JSON.stringify({ prefix: '/test-token/', csrf: 'test-csrf' }));
const tvA = 'http://192.168.1.50/device.xml';
const tvB = 'http://192.168.1.51/device.xml';
const episodeA = { uploadId: 'episode-a', name: 'episode-a.mp4', size: 100 };
const episodeB = { uploadId: 'episode-b', name: 'episode-b.mp4', size: 200 };
const state = (file = null, casting = null, location = null) => ({ ok: true, file, casting, location });
const flush = () => new Promise(setImmediate);

async function windowView({ onState = async () => state(), onRequest = async () => ({ ok: true }) } = {}) {
  class Element {
    value = ''; textContent = ''; disabled = false; hidden = false; options = []; files = [];
    classes = new Set();
    classList = { toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name) };
    append(option) { this.options.push(option); }
  }
  const elements = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element()]));
  elements.tvs.options.push({ value: '', textContent: 'Find a TV to get started' });
  const intervals = [], timeouts = new Map(), requests = [], events = new Map(), documentEvents = new Map();
  let timeoutId = 0;
  const document = {
    hidden: false, getElementById: id => elements[id], createElement: () => new Element(),
    addEventListener: (name, callback) => documentEvents.set(name, callback),
  };
  const context = vm.createContext({
    document, window: { addEventListener: (name, callback) => events.set(name, callback) },
    URL, AbortController,
    XMLHttpRequest: class {
      upload = {}; requestHeaders = {};
      open(method, url) { this.method = method; this.url = url; }
      setRequestHeader(name, value) { this.requestHeaders[name] = value; }
      send() {
        requests.push({ url: this.url, options: { method: this.method, headers: this.requestHeaders } });
        this.responseText = JSON.stringify({ ok: true, ...episodeB });
        queueMicrotask(() => this.onload());
      }
    },
    setInterval: callback => { intervals.push(callback); return intervals.length; },
    setTimeout: callback => { timeouts.set(++timeoutId, callback); return timeoutId; },
    clearTimeout: id => timeouts.delete(id),
    fetch: async (url, options = {}) => {
      requests.push({ url, options });
      const result = options.method === 'POST'
        ? await onRequest(url.split('/').at(-1), JSON.parse(options.body)) : await onState();
      const snapshot = structuredClone(result);
      return { ok: true, json: async () => snapshot };
    },
  });
  vm.runInContext(script, context);
  await flush();
  return {
    elements, requests, context, document, timeouts,
    poll: async () => { if (intervals[0]) await intervals[0](); await flush(); },
    focus: async () => { if (events.get('focus')) await events.get('focus')(); await flush(); },
    click: async id => { await elements[id].onclick(); await flush(); },
  };
}

test('another window starting a cast enables playback controls without reloading', async () => {
  let current = state();
  const view = await windowView({ onState: async () => current });
  assert.equal(view.elements.play.disabled, true);
  current = state(episodeA, episodeA, tvA);
  await view.poll();
  for (const id of ['play', 'pause', 'stop', 'refresh']) assert.equal(view.elements[id].disabled, false, id);
  assert.equal(view.elements.current.textContent, episodeA.name);
});

test('another window stopping a cast clears the active target and disables controls', async () => {
  let current = state(episodeA, episodeA, tvA);
  const view = await windowView({ onState: async () => current });
  current = state(episodeA);
  await view.focus();
  for (const id of ['play', 'pause', 'stop', 'refresh']) assert.equal(view.elements[id].disabled, true, id);
  assert.equal(view.elements['active-tv'].textContent, '');
  assert.notEqual(view.elements.current.textContent, episodeA.name);
});

test('a staged replacement stays distinct from the active video and selected TV', async () => {
  let current = state(episodeA, episodeA, tvA);
  const view = await windowView({ onState: async () => current });
  vm.runInContext(`addDevice({ location: ${JSON.stringify(tvB)}, name: 'Other TV' })`, view.context);
  current = state(episodeB, episodeA, tvA);
  await view.poll();
  assert.equal(view.elements.tvs.value, tvB);
  assert.match(view.elements['file-note'].textContent, /episode-b\.mp4/);
  assert.equal(view.elements.current.textContent, episodeA.name);
  assert.match(view.elements['active-tv'].textContent, /192\.168\.1\.50/);
  await view.click('pause');
  assert.equal(view.requests.at(-1).url, '/test-token/api/pause');
  assert.deepEqual(JSON.parse(view.requests.at(-1).options.body), {});
});

test('an unchanged poll preserves detailed TV status and command errors', async () => {
  const view = await windowView({ onState: async () => state(episodeA, episodeA, tvA) });
  view.elements.status.textContent = 'PAUSED_PLAYBACK · 2:10 / 20:00';
  view.elements.message.textContent = 'The TV rejected this command.';
  await view.poll();
  assert.equal(view.elements.status.textContent, 'PAUSED_PLAYBACK · 2:10 / 20:00');
  assert.equal(view.elements.message.textContent, 'The TV rejected this command.');
});

test('a delayed pre-cast poll cannot overwrite a completed cast', async () => {
  let deferred, wait = false;
  const view = await windowView({ onState: async () => wait ? new Promise(resolve => { deferred = resolve; }) : state(episodeA, null, tvA) });
  wait = true;
  const pending = view.poll();
  await flush();
  await view.click('cast');
  deferred(state());
  await pending;
  assert.equal(view.elements.play.disabled, false);
  assert.equal(view.elements.current.textContent, episodeA.name);
});

test('a delayed pre-stop poll cannot resurrect a stopped cast', async () => {
  let deferred, wait = false;
  const view = await windowView({ onState: async () => wait ? new Promise(resolve => { deferred = resolve; }) : state(episodeA, episodeA, tvA) });
  wait = true;
  const pending = view.poll();
  await flush();
  await view.click('stop');
  deferred(state(episodeA, episodeA, tvA));
  await pending;
  assert.equal(view.elements.play.disabled, true);
  assert.equal(view.elements['active-tv'].textContent, '');
});

test('a delayed poll cannot replace a completed file copy with the previous staged file', async () => {
  let deferred, wait = false;
  const view = await windowView({ onState: async () => wait ? new Promise(resolve => { deferred = resolve; }) : state(episodeA) });
  wait = true;
  const pending = view.poll();
  await flush();
  view.elements.file.files = [{ name: episodeB.name }];
  await view.elements.file.onchange();
  deferred(state(episodeA));
  await pending;
  assert.match(view.elements['file-note'].textContent, /episode-b\.mp4/);
  const upload = view.requests.find(request => request.url.endsWith('/api/upload'));
  assert.equal(upload.options.headers['X-LAN-Cast-CSRF'], 'test-csrf');
});

test('hidden windows skip passive polls and concurrent polls share one request', async () => {
  let deferred, wait = false;
  const view = await windowView({ onState: async () => wait ? new Promise(resolve => { deferred = resolve; }) : state() });
  view.document.hidden = true;
  await view.poll();
  assert.equal(view.requests.length, 1);
  view.document.hidden = false;
  wait = true;
  const first = view.poll();
  await flush();
  await view.poll();
  assert.equal(view.requests.length, 2);
  deferred(state());
  await first;
});

test('failed state snapshots preserve the current cast and rejected commands restore controls', async () => {
  let current = state(episodeA, episodeA, tvA);
  const view = await windowView({ onState: async () => current,
    onRequest: async () => ({ ok: false, error: { message: 'UPnP 701: transition unavailable' } }) });
  current = { ok: false, error: { message: 'Unavailable' } };
  await view.poll();
  assert.equal(view.elements.play.disabled, false);
  await view.click('pause');
  assert.match(view.elements.message.textContent, /UPnP 701/);
  assert.equal(view.elements.pause.disabled, false);
});

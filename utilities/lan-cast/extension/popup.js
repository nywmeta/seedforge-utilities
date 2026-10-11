'use strict';

const $ = (id) => document.getElementById(id);
const state = {
  busy: false,
  helperReady: false,
  devices: [],
  sources: [],
  selectedSourceUrl: '',
  selectedDeviceLocation: '',
  pageTitle: 'Video',
};

function isHttpUrl(value) {
  if (typeof value !== 'string' || value.length > 8192) return false;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password;
  } catch { return false; }
}

function fileCastUrl(value) {
  // Accept only the helper's exact loopback origin and opaque single-token path.
  const match = typeof value === 'string'
    ? /^http:\/\/127\.0\.0\.1:([1-9][0-9]{0,4})\/([A-Za-z0-9_-]{32,128})\/$/.exec(value) : null;
  if (!match || Number(match[1]) > 65535) {
    throw new Error('The helper returned an invalid local video page. Update the helper and try again.');
  }
  return value;
}

function selectedDevice() { return state.devices.find((device) => device.location === $('device').value); }
function selectedSource() { return state.sources.find((source) => source.url === $('source').value); }
function mediaUrl() { return $('media-url').value.trim() || selectedSource()?.url || ''; }

function updateButtons() {
  const idle = !state.busy;
  const native = idle && state.helperReady;
  const hasDevice = Boolean(selectedDevice());
  $('scan').disabled = !idle;
  $('discover').disabled = !native;
  $('file-cast').disabled = !native;
  $('add-device').disabled = !native || !$('device-address').value.trim();
  $('source').disabled = !idle || !state.sources.length;
  $('device').disabled = !idle || !state.devices.length;
  $('media-url').disabled = !idle;
  $('device-address').disabled = !idle;
  $('cast').disabled = !native || !hasDevice || !isHttpUrl(mediaUrl());
  for (const id of ['play', 'pause', 'stop', 'refresh-status']) $(id).disabled = !native || !hasDevice;
  $('retry-helper').disabled = !idle;
}

function notice(message, kind = '') {
  const element = $('notice');
  element.textContent = message;
  element.className = `notice${kind ? ` ${kind}` : ''}`;
  element.hidden = !message;
  element.setAttribute('role', kind === 'error' ? 'alert' : 'status');
}

function setHelper(ready) {
  state.helperReady = ready;
  $('helper-dot').className = `dot ${ready ? 'ready' : 'missing'}`;
  $('helper-state').textContent = ready ? 'Local helper connected' : 'Local helper needs setup';
  $('helper-help').hidden = ready;
  $('retry-helper').hidden = ready;
  updateButtons();
}

async function request(payload) {
  let reply;
  try { reply = await chrome.runtime.sendMessage(payload); } catch (error) {
    throw new Error(error.message || 'The extension could not reach its background service. Reopen this popup.');
  }
  if (!reply || reply.ok !== true) {
    const code = reply?.error?.code || 'REQUEST_FAILED';
    let message = typeof reply?.error?.message === 'string' ? reply.error.message : 'The request failed.';
    if (payload.action === 'open_file_cast' && code === 'UNKNOWN_ACTION') {
      message = 'Your installed helper needs an update for downloaded videos. Run this version’s helper installer, then reopen LAN Cast.';
    }
    if (/^HELPER_(MISSING|UNAVAILABLE|DISCONNECTED)$/.test(code)) setHelper(false);
    const error = new Error(message);
    error.code = code;
    throw error;
  }
  return reply;
}

async function run(label, action, clearNotice = true) {
  if (state.busy) return;
  state.busy = true;
  $('app').setAttribute('aria-busy', 'true');
  $('busy-label').textContent = label;
  $('busy').hidden = false;
  if (clearNotice) notice('');
  updateButtons();
  try { await action(); } catch (error) {
    notice(error.message || 'Something went wrong. Please try again.', 'error');
  } finally {
    state.busy = false;
    $('app').setAttribute('aria-busy', 'false');
    $('busy').hidden = true;
    updateButtons();
  }
}

async function save(values) {
  try { await chrome.storage.local.set(values); } catch { /* Keep the current session usable if storage is full. */ }
}

function renderSources(reply) {
  state.sources = Array.isArray(reply.sources) ? reply.sources.filter((source) => source && isHttpUrl(source.url)).slice(0, 100) : [];
  state.pageTitle = typeof reply.pageTitle === 'string' ? reply.pageTitle : 'Video';
  const select = $('source');
  select.replaceChildren();
  if (!state.sources.length) {
    select.add(new Option('No direct stream found', ''));
  } else {
    for (const source of state.sources) {
      let suffix = '';
      try { suffix = new URL(source.url).hostname; } catch { /* Validated above. */ }
      select.add(new Option(`${source.label || 'Video stream'} · ${suffix}`, source.url));
    }
    select.value = state.sources.some((source) => source.url === state.selectedSourceUrl)
      ? state.selectedSourceUrl : state.sources[0].url;
    state.selectedSourceUrl = select.value;
    save({ selectedSourceUrl: select.value });
  }
  const blocked = reply.blocked || {};
  const notes = [];
  if (state.sources.length) notes.push(`${state.sources.length} stream${state.sources.length === 1 ? '' : 's'} found. Network candidates are unverified.`);
  else notes.push('No direct stream found. Start the video and scan again, or open the player’s own page if it is embedded. If the site offers a normal Download button, save the video and choose “Cast a downloaded video” above.');
  if (blocked.blob || blocked.data) notes.push('This video uses a browser-only blob/data URL that the TV cannot open. A normal site download can be played through “Cast a downloaded video”; protected playback remains unsupported.');
  if (blocked.encrypted) notes.push('A protected video was detected; DRM video is not supported.');
  if (reply.frameWarning) notes.push(reply.frameWarning);
  $('source-summary').textContent = notes.join(' ');
  updateButtons();
}

function cleanDevice(device) {
  if (!device || typeof device !== 'object' || !isHttpUrl(device.location)) return null;
  return {
    id: typeof device.id === 'string' ? device.id : device.location,
    name: typeof device.name === 'string' && device.name ? device.name.slice(0, 300) : 'UPnP renderer',
    location: device.location,
    model: typeof device.model === 'string' ? device.model.slice(0, 300) : '',
    manufacturer: typeof device.manufacturer === 'string' ? device.manufacturer.slice(0, 300) : '',
  };
}

function renderDevices(devices, saved = false) {
  const previousLocation = selectedDevice()?.location || '';
  state.devices = [...new Map(devices.map(cleanDevice).filter(Boolean).map((device) => [device.location, device])).values()];
  const select = $('device');
  select.replaceChildren();
  if (!state.devices.length) {
    select.add(new Option('No compatible TV found', ''));
    $('device-summary').textContent = 'Keep the TV on, use the same local network, and try Find TVs again. You can also enter its address.';
  } else {
    for (const device of state.devices) select.add(new Option(`${device.name}${device.model && device.model !== device.name ? ` · ${device.model}` : ''}`, device.location));
    select.value = state.devices.some((device) => device.location === state.selectedDeviceLocation)
      ? state.selectedDeviceLocation : state.devices[0].location;
    state.selectedDeviceLocation = select.value;
    updateDeviceSummary(saved);
    save({ selectedDeviceLocation: select.value, savedDevices: state.devices });
  }
  if ((selectedDevice()?.location || '') !== previousLocation) resetPlayback();
  updateButtons();
}

function updateDeviceSummary(saved = false) {
  const device = selectedDevice();
  if (!device) return;
  let hostname = '';
  try { hostname = new URL(device.location).host; } catch { /* Validated above. */ }
  $('device-summary').textContent = `${saved ? 'Saved TV · ' : ''}${[device.manufacturer, hostname].filter(Boolean).join(' · ')}${saved ? '. Use Find TVs if its address changed.' : ''}`;
}

function resetPlayback() {
  $('transport-state').textContent = 'TV playback';
  $('playback-time').textContent = '—';
}

function timeLabel(value) {
  if (typeof value === 'string' && /^\d{1,3}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)) return value.replace(/\.\d+$/, '').replace(/^00:/, '');
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return '—';
  const seconds = Math.floor(value);
  const hours = Math.floor(seconds / 3600);
  return `${hours ? `${hours}:` : ''}${String(Math.floor(seconds / 60) % 60).padStart(hours ? 2 : 1, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function renderStatus(reply) {
  const labels = { PLAYING: 'Playing on TV', PAUSED_PLAYBACK: 'Paused on TV', STOPPED: 'Stopped', NO_MEDIA_PRESENT: 'No media loaded', TRANSITIONING: 'Loading on TV', PAUSED_RECORDING: 'Paused' };
  const transportState = typeof reply.transportState === 'string' ? reply.transportState : '';
  $('transport-state').textContent = labels[transportState] || transportState || 'TV status unavailable';
  const position = timeLabel(reply.position);
  const duration = timeLabel(reply.duration);
  $('playback-time').textContent = duration === '—' || duration === '0:00' || duration === '00:00' ? position : `${position} / ${duration}`;
}

async function checkHelper() {
  try {
    await request({ action: 'ping' });
    setHelper(true);
  } catch (error) {
    setHelper(false);
    throw error;
  }
}

$('scan').addEventListener('click', () => run('Looking for video streams…', async () => {
  renderSources(await request({ action: 'scan' }));
}));

$('file-cast').addEventListener('click', () => run('Opening downloaded video casting…', async () => {
  const reply = await request({ action: 'open_file_cast' });
  const url = fileCastUrl(reply.url);
  await chrome.tabs.create({ url });
  notice('Opened LAN Cast for downloaded videos. Choose your saved video and TV in the new tab.', 'success');
}));

$('discover').addEventListener('click', () => run('Finding TVs on your network…', async () => {
  const reply = await request({ action: 'discover' });
  renderDevices(Array.isArray(reply.devices) ? reply.devices : []);
  if (!state.devices.length) {
    notice('No UPnP/DLNA playback device responded. Check the TV is awake and on the same network.');
  } else {
    notice(`Found ${state.devices.length} playback device${state.devices.length === 1 ? '' : 's'}.`, 'success');
  }
  if (Array.isArray(reply.warnings) && reply.warnings.length) {
    notice(reply.warnings.map((warning) => typeof warning === 'string' ? warning : warning?.message || '').filter(Boolean).join(' '));
  }
}));

$('add-device').addEventListener('click', () => run('Checking the TV address…', async () => {
  const reply = await request({ action: 'addDevice', address: $('device-address').value.trim() });
  const device = cleanDevice(reply.device);
  if (!device) throw new Error('The helper did not return a compatible playback device for that address.');
  state.selectedDeviceLocation = device.location;
  renderDevices([...state.devices, device]);
  $('device-address').value = '';
  notice(`Added ${device.name}.`, 'success');
}));

$('cast').addEventListener('click', () => run('Sending the stream to your TV…', async () => {
  const device = selectedDevice();
  const source = selectedSource();
  const direct = $('media-url').value.trim();
  if (!device || !isHttpUrl(mediaUrl())) throw new Error('Choose a TV and a valid video URL first.');
  await request({
    action: 'cast', location: device.location, mediaUrl: mediaUrl(),
    title: direct ? 'LAN Cast video' : source?.title || state.pageTitle,
    mimeType: direct ? '' : source?.mimeType || '',
  });
  await save({ directMediaUrl: direct, selectedDeviceLocation: device.location });
  notice(`The TV accepted the stream and play command. Check playback on ${device.name}.`, 'success');
  $('transport-state').textContent = 'Play command accepted';
  $('playback-time').textContent = '—';
  try { renderStatus(await request({ action: 'status', location: device.location })); } catch (error) {
    notice(`The TV accepted the stream, but its playback status could not be read: ${error.message}`);
  }
}));

for (const command of ['play', 'pause', 'stop']) {
  $(command).addEventListener('click', () => run(`Sending ${command} to your TV…`, async () => {
    const device = selectedDevice();
    if (!device) throw new Error('Choose a TV first.');
    await request({ action: 'control', location: device.location, command });
    notice(`The TV accepted the ${command} command.`, 'success');
    try { renderStatus(await request({ action: 'status', location: device.location })); } catch {
      $('transport-state').textContent = `${command[0].toUpperCase()}${command.slice(1)} command accepted`;
      $('playback-time').textContent = '—';
    }
  }));
}

$('refresh-status').addEventListener('click', () => run('Reading TV playback status…', async () => {
  const device = selectedDevice();
  if (!device) throw new Error('Choose a TV first.');
  renderStatus(await request({ action: 'status', location: device.location }));
}));

$('retry-helper').addEventListener('click', () => run('Checking the local helper…', checkHelper));
$('source').addEventListener('change', () => {
  state.selectedSourceUrl = $('source').value;
  // An explicit selection means the user chose that stream over a pasted URL.
  $('media-url').value = '';
  save({ selectedSourceUrl: state.selectedSourceUrl, directMediaUrl: '' });
  updateButtons();
});
$('device').addEventListener('change', () => {
  state.selectedDeviceLocation = $('device').value;
  save({ selectedDeviceLocation: state.selectedDeviceLocation });
  resetPlayback();
  updateDeviceSummary();
  updateButtons();
});
$('media-url').addEventListener('input', updateButtons);
$('media-url').addEventListener('change', () => save({ directMediaUrl: $('media-url').value.trim() }));
$('device-address').addEventListener('input', updateButtons);
$('device-address').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !$('add-device').disabled) $('add-device').click();
});

async function initialize() {
  try {
    const saved = await chrome.storage.local.get(['selectedSourceUrl', 'selectedDeviceLocation', 'directMediaUrl', 'savedDevices']);
    state.selectedSourceUrl = typeof saved.selectedSourceUrl === 'string' ? saved.selectedSourceUrl : '';
    state.selectedDeviceLocation = typeof saved.selectedDeviceLocation === 'string' ? saved.selectedDeviceLocation : '';
    $('media-url').value = typeof saved.directMediaUrl === 'string' ? saved.directMediaUrl : '';
    $('direct-source').open = Boolean($('media-url').value);
    if (Array.isArray(saved.savedDevices) && saved.savedDevices.length) renderDevices(saved.savedDevices, true);
  } catch { /* The popup works without saved preferences. */ }
  await run('Checking the local helper…', checkHelper);
}

updateButtons();
initialize();

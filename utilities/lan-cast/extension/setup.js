'use strict';

const browserSelect = document.getElementById('browser');
const command = document.getElementById('install-command');
const copyState = document.getElementById('copy-state');
const browserHint = document.getElementById('browser-hint');
const windows = /Win/i.test(navigator.platform);
const mac = /Mac/i.test(navigator.platform);
const brands = Array.isArray(navigator.userAgentData?.brands) ? navigator.userAgentData.brands : [];
// OPR/ is shared by Opera and Opera GX. Only an explicit GX label can identify GX.
const explicitOperaGX = /\bOpera GX\b/i.test(navigator.userAgent)
  || brands.some((entry) => entry?.brand === 'Opera GX');
const operaFamily = /\bOPR\//.test(navigator.userAgent) || explicitOperaGX;
browserSelect.value = explicitOperaGX ? 'opera-gx' : operaFamily ? 'opera'
  : /Edg\//.test(navigator.userAgent) ? 'edge' : 'chrome';
document.getElementById('extension-id').textContent = chrome.runtime.id;
document.getElementById('platform-hint').textContent = windows
  ? 'On Windows, run the command from PowerShell or Command Prompt.'
  : mac ? 'On macOS, use Install on Mac.command or run the command from Terminal.'
    : 'On Linux, run the command from a terminal.';

function updateCommand() {
  command.textContent = `${windows ? 'py -3' : 'python3'} helper/install.py --extension-id ${chrome.runtime.id} --browser ${browserSelect.value}`;
  copyState.textContent = 'The command includes this extension’s ID.';
  browserHint.textContent = operaFamily && !explicitOperaGX && browserSelect.value === 'opera'
    ? 'Opera detected. If this is Opera GX, select Opera GX to register its helper.'
    : ['opera', 'opera-gx'].includes(browserSelect.value)
      ? 'Choose Opera GX for the gaming browser, or Opera for the standard browser.'
      : 'Choose the browser where this extension is loaded.';
}

browserSelect.addEventListener('change', updateCommand);
document.getElementById('copy-command').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(command.textContent);
    copyState.textContent = 'Command copied. Run it from the extracted lan-cast folder.';
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(command);
    selection.removeAllRanges();
    selection.addRange(range);
    copyState.textContent = 'Copy was blocked. The command is selected; copy it with your keyboard.';
  }
});

updateCommand();

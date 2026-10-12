# Validation — LAN Cast 1.2.2 release candidate

Checked on macOS on 12 October 2026. This record separates current seeking checks from earlier installation and maintenance evidence.

## 1.2.2 seeking checks

- The complete local utility suites passed: **96 Python tests and 80 JavaScript tests**. The release gate additionally runs **18 publishing/packaging tests**, syntax checks and reproducible packaging. Test sockets were explicitly permitted for the complete local run.
- Eighteen new Python tests cover exact-size DIDL metadata, unchanged remote-stream metadata, malformed capability inputs before network access, HTTP GET/HEAD/Range feature parity, active-TV targeting, strict seeking values, fresh-position relative jumps, start/end clamping, missing positions and preservation of the serving session on command failures.
- Eight new companion UI groups (with timestamp subcases) cover strict time entry, malformed input without a request, bounded skip payloads, busy/no-cast controls, SOAP rejection, status failure after an accepted command and clearing an entered time when the active video changes. UI tests simulate browser requests.
- Existing helper modules were backed up and updated to 1.2.2 on this Mac. The downloaded-video window was reopened in Opera GX and loaded the same already-downloaded MP4 through its local upload API. The original file was retained.
- Before the repair, the physical Samsung S90F session's resource used general protocolInfo and omitted size; its available transport actions were Pause/Stop. Its service description nevertheless advertised seeking modes.
- After recasting the repaired stream, the resource included exact size and `DLNA.ORG_OP=01;DLNA.ORG_CI=0`. The TV advertised Seek, DLNA byte/time seeking and playback-speed actions. A REL_TIME request to 3:40 succeeded; the subsequent TV position was about 3:37, consistent with seeking to a nearby frame. The visible Opera window's **Jump to time** was also exercised and displayed that observed position.
- The user explicitly confirmed that the **physical TV remote now permits seeking/fast-forward** for this video. This is actual device evidence, separate from command acknowledgement and simulated tests.
- One attempt to replace a paused session initially returned **UPnP 701** during startup. The candidate file session was closed as designed on failure; stopping TV playback and casting again succeeded. No automatic recovery from that startup fault is claimed. Seeking can affect playback state on this TV; no pause-preservation guarantee is made.
- No arbitrary codec profile, universal-TV support, remote-stream seeking or HTTP time-seek support is claimed. This remains a release candidate.

## 1.2.1 maintenance checks

- Nine companion UI tests reproduce and check state changes from another window, staged/active video separation, preservation of a different TV selection, delayed snapshots across Cast/Stop/file-copy completion, hidden-window polling, overlapping polls, rejected commands and preservation of detailed status/messages.
- A Python regression check confirms that passive state reads do not extend the idle lifetime or send a command to the TV.
- Locally, **52 Python utility tests without sockets, all 56 JavaScript utility tests and all 18 publishing/packaging tests** passed. The complete local Python suite was blocked by this session's loopback socket permissions; no full local gate pass is claimed.
- The complete release gate is `scripts/release.py` and runs in the repository's standard public GitHub workflow. Check the workflow run for the release tag's exact commit for the full socket-suite result. Publication requires that complete gate to pass and the downloadable ZIP to match its checked build.
- The approved package contains **32 files**. No browser registration or active TV playback was changed while testing this patch. These UI tests simulate browser elements and requests; they do not establish a new installed-browser or hardware result.
- The user's intermittent playback-button report recovered before this change. Its cause was not identified; this patch addresses a separately reproduced stale-window behavior.

## Previous 1.2.0 automated checks

- **77 Python utility tests** passed using Python 3.9.6: native framing, simulated renderer, SOAP/DIDL, controls/status, bounded device deadlines, isolated installer/launcher/uninstall, macOS shared Opera registration, helper asset preflight, companion reuse and startup errors, strict local interface URL validation, Host/Origin/CSRF checks, streamed private uploads, replacement/failure cleanup, TV-only serving, HTTP Range and HEAD responses.
- **47 JavaScript utility tests** passed using the bundled Node runtime: minimal Manifest V3 permissions, trusted popup/native boundary, media scanner and inaccessible embedded-player guidance, helper errors, companion action and returned loopback URL validation, popup behavior, and browser-specific setup.
- **18 offline publishing/packaging tests** passed. JavaScript and Mac launcher syntax checks passed; the new package contains 31 reviewed files.
- Tests change no real browser registration; installer tests use temporary home directories. Socket tests use loopback simulated servers.

## Observed on this Mac and TV with 1.2.0

- Updated the existing unpacked Opera GX extension in place to **1.2.0**, preserving its extension ID. The original extension files were backed up before updating.
- Installed the matching helper modules and Opera’s registration in its documented shared Chrome folder. After reload, the actual Opera GX popup showed **Local helper connected**.
- The actual plugin’s **Find TVs** command discovered the physical Samsung S90F. Its **Cast a downloaded video** button opened the local companion window in Opera GX.
- In the companion window, **Find TVs** discovered that TV. The browser file picker selected the already-downloaded MP4; the window copied it locally and enabled casting.
- The companion’s **Cast to TV** action was accepted. **Check status** reported **PLAYING**, with a progressing position and duration **23:49**. A second episode was then downloaded through its provider’s normal button, verified against its file checksum, selected in the companion, and cast through the same window. Opera’s companion status reported **PLAYING**, with a progressing position and duration **23:39**. This also exercised replacing an active episode.
- Earlier in the same task, the user explicitly confirmed picture and sound for the same MP4 and TV through the local UPnP file-serving route. That confirmation is distinct from the updated-interface status check.

## Limits

- The video provider refused fetching its browser stream outside the player; this release does not bypass that restriction. Use the provider’s normal download option, then choose the downloaded video in the companion.
- Native communication has been checked in Opera GX on this Mac. Other installed browsers and Windows/Linux runtime installation remain unverified.
- TV format support varies. This check establishes one MP4 on one physical TV, not every codec, website, subtitle format or TV model. There is no transcoding or separate subtitle support.
- Commands depend on the renderer and source. Seeking is now confirmed only for the tested local MP4 on the Samsung S90F; other TVs, files and web streams remain unverified.
- The computer must remain on and connected while it serves the video. Keep a Mac laptop’s lid open.

## Repeat checks

From this utility folder:

```sh
python3 -B -m unittest discover -s tests -v
node --test tests/*.test.mjs
```

For a complete release gate, use `python3 scripts/release.py --node node` from the Seedforge repository root. Restricted environments must allow local test sockets. Publication remains separate from local installation and validation.

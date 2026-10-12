# LAN Cast changes

## 1.2.2 release candidate — 12 October 2026

- Advertise byte-range seeking and unchanged content for downloaded files in both DLNA resource metadata and HTTP responses. Include the exact file size. Arbitrary browser stream URLs retain general metadata; no codec profile or HTTP time-seek capability is claimed.
- Add **Back 30 seconds**, **Forward 30 seconds**, and **Jump to time** (`12:30` or `1:02:03`) to the downloaded-video window. Playback controls target the active TV, even when another TV is selected for the next cast.
- Relative jumps read the TV's current position and clamp to the known video bounds. Invalid times are rejected before sending a command. Rejected seeking leaves the serving session and entered time available.
- Add 18 Python regression tests and eight UI test groups, including timestamp cases. Retain the 1.2.1 window-synchronization fix.

On a physical Samsung S90F, the original file session offered only Pause/Stop. After the repaired stream was cast, the TV advertised seeking and fast-forward, a time jump changed its reported position, and the user confirmed the physical remote could seek. This establishes that tested downloaded MP4 on that TV; other TVs, formats and remote streams remain unverified. A paused-session replacement initially returned UPnP 701; stopping the session and casting again succeeded. See VALIDATION.md.

## 1.2.1 release candidate — 12 October 2026

- Refresh the downloaded-video window's local casting state every five seconds while visible, and when returning to it. Starting or stopping a cast in another window updates playback controls without a reload.
- Keep the staged video, active video and playback TV distinct. Preserve a different TV selection and detailed playback status while synchronizing.
- Discard state replies overtaken by a local command. Bound state requests and prevent overlapping polls.
- Passive state reads no longer extend the helper's eight-hour idle lifetime. Retain the existing token, Host/Origin and CSRF protections.
- Explain that **Cast to TV** restarts playback after **Stop** closes the file-serving session. Add nine companion UI behavior tests and an idle-lifetime regression test; include both JavaScript suites in the release gate.

The stale-window problem was reproduced in offline UI tests. The user's earlier intermittent control failure recovered before this patch; its cause remains unconfirmed. Physical-device observations below belong to 1.2.0. This patch has not been installed over an active helper or exercised on a physical TV.

## 1.2.0 release candidate — 11 October 2026

- Correct Opera and Opera GX native-host registration on macOS to the documented shared Chrome folder. Preserve previously authorized extension IDs.
- Add a local window for choosing downloaded episodes, finding a TV, casting, playback controls, and status. Stream uploads to private temporary storage; serve only the selected file to the selected TV, with byte-range support.
- Add **Cast a downloaded video** to the plugin and a standalone Mac launcher. Keep browser website permissions limited to the active tab.
- Explain cross-origin embedded-player and browser-only video limitations, including the normal-download fallback.
- Retain originals, keep Mac idle sleep suspended only while serving, and clean up temporary video copies.

A downloaded MP4’s picture and sound were confirmed on a physical Samsung S90F through a local UPnP server. Updated-plugin/browser verification is recorded separately in VALIDATION.md. AI assistants with browser-control tools can operate the visible controls; LAN Cast itself includes no AI model or universal tab-casting service.

## 1.1.1 release candidate — 11 October 2026

- Preserve active-video priority when the same normalized URL appears in multiple frames or elements, including pages with many candidate streams.
- Exclude URLs identified as encrypted media from network candidates.
- Clear the previous TV's playback status when discovery changes or removes the selected TV.
- Bound slow device HTTP responses with an overall deadline.
- Reject XML-forbidden characters in stream URLs and cast titles.
- Handle malformed existing native-host origin lists without crashing the installer.
- Align extension/helper version reporting. Add MIT license, privacy documentation and reproducible packaging.

Automated checks use a simulated renderer and browser APIs. Physical TV playback, native-host lookup in installed browsers and Windows/Linux installation remain unverified in this release.

## 1.1.0 — earlier local build

Added Opera/Opera GX setup alongside Chrome, Edge and Chromium. Native-host setup and physical TV playback were not completed.

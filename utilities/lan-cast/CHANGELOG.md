# LAN Cast changes

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

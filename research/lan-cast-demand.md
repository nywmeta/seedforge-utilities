# Seedforge casting demand research

Reviewed 2026-10-11. Read-only research; no community posts or messages sent. Sources below are actual user threads, project issues, repositories, or official stores. Older threads establish recurring pain, not proof that it remains unsolved in 2026. No usage, donation, or revenue forecasts are justified by this evidence.

## Recommendation

If the user's own UPnP plugin is accessible, finish and test that before expanding scope. If it is not, the strongest small opportunity is a **cross-platform, dependency-light DLNA discovery and troubleshooting companion**: show what answers discovery, distinguish MediaServers from MediaRenderers, inspect advertised AVTransport capabilities, identify unreachable local service descriptions, and export a readable local report. Keep diagnosis separate from device playback changes. This is an inference from recurring support problems; it is not proof that no competitor exists.

A new general browser casting app would enter a crowded field and require maintenance for media extraction, DRM, cookies, codecs, TV firmware, browser permissions, and OS installation. Prefer a narrow direct-media casting flow or diagnostic gap over “cast any website” claims. A contribution to an existing permissively licensed utility may produce more useful results for less maintenance.

## Demand evidence

| Source | Date/status observed | Concrete need | Implication |
| --- | --- | --- | --- |
| [Reddit: Looking for alternatives vGet Cast to Cast to TV with DNLA](https://www.reddit.com/r/software/comments/upn4uk) | 2022-05-14; search returned full post and no solution verification | User's old extension stopped working; wants browser video detection, direct-link casting, and local-file casting to a LAN TV. | Exact historical browser workflow demand. Must not describe as still unmet without checking modern alternatives. |
| [Reddit: Looking for an alternative casting app](https://www.reddit.com/r/linux4noobs/comments/17um05a) | 2023-11-13; search returned full post and comments | Wants a FOSS Linux alternative to a Windows app for web media casting; generic server answers did not address browser workflow. | Linux/browser gap existed; report does not establish present absence. |
| [MacRumors: DLNA not working – help!](https://forums.macrumors.com/threads/dlna-not-working-help.2439096/) | 2024-10-03 to 2024-10-12; full public thread read | Sequoia user tries several servers, confusing network visibility and client types. Samsung later sees media; Roku still does not. Last visible follow-up moved to a private message, with no public resolution. | Plain diagnostics and a repeatable support report would reduce guesswork. Do not endorse forum advice to disable security settings. |
| [go2tv #148: unstable search devices](https://github.com/alexballas/go2tv/issues/148) | Open; created 2026-04-02 | Device discovery intermittently fails compared with older versions. Maintainer says discovery improvements shipped in v2.3.0 on 2026-04-30; confirmation is absent in the visible discussion. | Discovery issues recur even in established software. Open status alone is not proof current code is broken. |
| [go2tv #163: DLNA Error](https://github.com/alexballas/go2tv/issues/163) | Open; created 2026-08-16; full visible discussion read | LG TV accepts/probes media but stays in TRANSITIONING. Several versions tested. Power-cycling helps an older version; newer discovery comparisons requested. | Need to distinguish discovery, HTTP media delivery, capability/codec rejection, and stale renderer state. This discussion does not isolate a final cause. |
| [PlayBridge #238: LG DLNA behavior](https://github.com/playbridgeapp/playbridge/issues/238) | Open; created 2026-09-24, updated 2026-09-25; verified through GitHub connector | Windows/Android user reports an LG UR8750PSA is shown as connected but casting frequently fails. Maintainer comment says it will be investigated. | Current real report of misleading connection state and interoperability pain. One report does not establish prevalence. |
| [ScreenStream #352: UPnP/DLNA local-stream casting request](https://github.com/dkrivoruchko/ScreenStream/issues/352) | Open; created 2026-03-28 | User wants existing RTSP/MJPEG screen-stream URLs sent to Kodi via AVTransport. | Narrow URL handoff is a real feature request; avoid expanding into capturing/encoding the screen. |

## Existing alternatives checked

- [go2tv](https://github.com/alexballas/go2tv): MIT repository. Advertises auto-discovery, local media casting, DLNA/Chromecast, GUI/CLI, a browser web UI, subtitles, seeking, and optional FFmpeg transcoding. It already covers much of basic local-file casting. README features are maintainer claims, not independently reproduced here.
- [PlayBridge](https://github.com/playbridgeapp/playbridge): GPLv3 project described as alpha, with phone, desktop, CLI, and browser extension senders, native receivers, and DLNA targets. Large feature surface means a small Seedforge utility should offer a focused advantage.
- [Streaming LAN Cast repository](https://github.com/fabriziosantidev/streaming-lan-cast): Chrome/Firefox extension plus local Python helper, Streamlink, PyChromecast, and FFmpeg. Near-exact browser casting workflow. PolyForm Noncommercial 1.0.0 restricts commercial use; do not call this OSI open source or copy/relicense it into an MIT product.
- [Streaming LAN Cast official Firefox listing](https://addons.mozilla.org/en-US/firefox/addon/streaming-lan-cast/): actually published despite the repository README retaining a placeholder store link. Listing showed version 0.5.13, dated 2026-10-05, a custom PolyForm Noncommercial license, and a small optional contribution area. This is a concrete lesson: verify the store rather than infer publication status from documentation. No Chrome store publication was verified.
- [LG TV Tools](https://github.com/ultrasardine/lg-tv-tools-manager): offers discovery, casting, diagnostic logging, and TV control. LG-specific, with a larger UI/dependency surface; not a general no-install troubleshooting report. The repository is a fork, so inspect origin/license before reuse.
- [GUPnP Tools](https://github.com/GNOME/gupnp-tools): GPL2 tools already inspect UPnP devices/services, invoke actions, and control media renderers. A Seedforge diagnostic utility is not a novel protocol inspector. Any differentiation must be installation simplicity, support-ready reports, safe defaults, and cross-platform usability.
- [Ubuntu UPnP Inspector manpage](https://manpages.ubuntu.com/manpages/trusty/man1/upnp-inspector.1.html): documents an existing graphical device/service analyzer built on Coherence. Historical package documentation is not verification of current easy installation.
- [pywiim](https://github.com/mjcumming/pywiim): includes discover/verify/diagnostic commands and JSON reports for WiiM/LinkPlay audio devices. Useful precedent, but device-specific.

## Practical release scope and evidence boundaries

For an existing casting plugin: document exactly supported URL types and hardware; use direct non-DRM media first; require local helper pairing; provide setup and troubleshooting; avoid “all TVs”, “all websites”, or “fully tested” assertions. Automated fake-renderer tests validate protocol behavior but cannot establish real TV compatibility.

For a diagnostic companion: default to a bounded local SSDP query, inspect same-device local description/service URLs, avoid public-network fetches, redirects to other hosts, credentials, and playback-changing SOAP actions. Produce separate facts (“no renderer responded”, “description fetched”, “AVTransport advertised”) and possible explanations. Do not automatically disable firewalls, open router ports, or alter device settings.

Publish first to the user's approved GitHub destination with accurate setup instructions, license, changelog, tests, limitations, and an optional donation link only after the user supplies/confirms a legitimate recipient. Read each community's current rules before any specific announcement. Do not treat issue trackers as advertising channels or old support posts as invitations for promotional replies.

## Research limitations

Browser results sometimes contain cached snapshots. The dated facts and visible statuses above were checked through actual pages; PlayBridge issue status was additionally checked through the connected GitHub API. Some Reddit pages fail direct opening but their search result supplied the full thread text. No code, installations, hardware behavior, or donation recipient was verified by this research pass. No defensible estimate of total market size or donation income is available.

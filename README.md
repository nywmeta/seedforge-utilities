# Seedforge utilities

Small free tools for recurring, specific software frustrations. Source code is MIT licensed. Support is optional; every feature works without payment or an account.

## First utility: LAN Cast

[LAN Cast](utilities/lan-cast/README.md) sends a direct video URL from a Chromium browser to a local UPnP/DLNA renderer. It includes a Python standard-library helper, playback controls and explicit setup/removal instructions.

**Release candidate:** automated checks cover a simulated renderer. Actual TV playback and installed native-host lookup still require verification. It does not mirror tabs, bypass DRM, transcode video, or transfer browser login credentials.

## How we choose work

Read real problem reports, reproduce the problem, check existing free solutions, then make the smallest useful repair or utility. Prefer helping an existing maintained project when that resolves the need. Keep one utility in progress. A release is evidence of delivered software, not proof of users, revenue or compatibility.

The [operating workflow](PIPELINE.md), [demand record](research/lan-cast-demand.md), and [results ledger](STATUS.md) explain the decisions and their evidence.

## Repeatable release checks

Python 3.9+ and Node 22+ are needed for development. End users need only Python and their browser.

```sh
python3 scripts/release.py --node node
```

The command runs the tests, checks release files and versions, and creates a reproducible utility ZIP plus a SHA-256 checksum in `dist/`. It never publishes or contacts a payment service. GitHub CI runs the same checks only in public repositories using a standard runner, without paid runners, caches or artifact uploads.

## Support

<!-- seedforge-support-start -->
Optional support is not configured yet. The software is free to use and modify.
<!-- seedforge-support-end -->

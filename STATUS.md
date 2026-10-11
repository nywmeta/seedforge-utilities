# Seedforge release status

Updated 11 October 2026 (Europe/Helsinki).

## Current release candidate

LAN Cast 1.1.1 sends direct non-DRM video or audio URLs from a Chromium browser to a local UPnP/DLNA renderer with AVTransport. It uses a Python standard-library helper and browser permissions limited to the active tab. Broad website or TV compatibility is not claimed.

The checked release candidate is prepared. Public downloadable release verification is pending; publication is confirmed only after anonymous source and release-asset checks succeed.

## Validation

The release gate passed on 11 October 2026: **41 Python utility tests, 37 JavaScript utility tests and 18 offline pipeline tests** (96 total), plus syntax and file checks. Tests cover a simulated renderer, browser API behavior, local helper installation in isolated directories, safe packaging and publication verification. Pipeline tests reject missing or changed public source, invalid archives, hidden credential files, external symlinks and omitted code. Reproducible ZIP bytes and file modes are checked.

The reusable publishing skill passed its frontmatter validator. The GitHub workflow and pinned official action commits were inspected; live GitHub CI has not run for this repository.

Physical TV playback, successful native-host communication inside an installed browser, and Windows/Linux installation remain unverified. See [LAN Cast validation](utilities/lan-cast/VALIDATION.md) for the detailed evidence and remaining device checks.

## Checked artifact

Filename: `lan-cast-v1.1.1-rc.zip`, containing 25 files.

SHA-256: `a659b60f78f6acedd300bb506c7a7bf29c60124814b2d82a194f83a887e9bf8a`.

Run [the release gate](scripts/release.py) to create the archive and accompanying checksum in `dist/`. Generated archives are distributed as release assets rather than included in the source tree.

## Optional support

Support is disabled in `funding.json`. No recipient page is configured or verified, and the software requires no payment.

## Next opportunity

A read-only UPnP diagnostic companion is a candidate, subject to reproducing a gap that maintained free tools do not cover. Existing UPnP tools already provide inspection and troubleshooting; a focused upstream improvement may be preferable. See [the demand record](research/lan-cast-demand.md).

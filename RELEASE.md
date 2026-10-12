# LAN Cast 1.2.1 verified release

Repository: `nywmeta/seedforge-utilities`, public and MIT licensed.
Tag: `lan-cast-v1.2.1-rc`, published as a prerelease.
[Release and downloads](https://github.com/nywmeta/seedforge-utilities/releases/tag/lan-cast-v1.2.1-rc).

## Title

LAN Cast 1.2.1 — playback controls stay in sync

## Release body

When LAN Cast's downloaded-video window was open more than once, a window could retain disabled controls after another started a cast, or enabled controls after another stopped it. This maintenance release refreshes the shared local casting state every five seconds while visible and when returning to a window.

The staged episode, playing episode and playback TV stay distinct. A delayed state response cannot overwrite a completed Cast, Stop or file copy. Passive refreshes keep the existing eight-hour idle timeout. After Stop closes the serving session, use **Cast to TV** to restart.

The complete [free GitHub release gate](https://github.com/nywmeta/seedforge-utilities/actions/runs/38216963159) passed: **78 Python, 56 JavaScript and 18 publishing/packaging tests**. The 32-file ZIP matches the checked CI build byte for byte. Nine companion UI regression tests cover the reproduced window-state problem.

This remains a prerelease. The patch has not been installed over an active helper or tested on a physical TV; earlier Opera GX and Samsung S90F evidence belongs to 1.2.0. The user's earlier intermittent button problem recovered before this patch, and its cause remains unconfirmed. TV command, format and platform limitations in VALIDATION.md still apply.

Free, MIT licensed, local UPnP/DLNA casting. Python **3.9+** is required. Download the ZIP and follow README.md. All features remain free; optional support is currently disabled.

## Live verification

The actual `scripts/verify_publication.py` completed anonymously on the free public CI runner at `2026-10-12T07:24:05.750651+00:00`. Every packaged source file at `4e41da978c2091473c55aef06ddbd912967db741`, the repository MIT license, downloaded ZIP and checksum matched the checked build. `publication.json` records the result. SHA-256: `55890d18ee7ed104011dafcd453b6ea53dec6bfa14ca9121e52bf9f0d1100472`.

[Verification run](https://github.com/nywmeta/seedforge-utilities/actions/runs/38217504583). The runner checked out the release tag and ran the full gate before verification. No paid services, artifact/cache storage or additional token privileges were used.

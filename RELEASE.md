# LAN Cast 1.2.0 release preparation

Repository: `nywmeta/seedforge-utilities`, public, MIT licensed.
Tag: `lan-cast-v1.2.0-rc`. Publish as a prerelease.
The previous 1.1.1 release remains recorded in publication.json until the new release passes live verification.

## Title

LAN Cast 1.2.0 — downloaded episodes to TV, with repaired Opera setup

## Release body

LAN Cast plays direct video URLs and downloaded video files on a UPnP/DLNA TV. Everything is free and MIT licensed. No account, cloud video upload or runtime package download is required.

This release fixes macOS Opera/Opera GX helper registration and adds a local episode window: find your TV, choose a downloaded video, cast, and control playback. **Cast a downloaded video** opens that window from the plugin; a standalone Mac launcher is also included.

A browser-controlling AI assistant can use these visible controls. LAN Cast includes no AI model, API subscription or universal tab-casting service. The included AI-ASSISTANT.md explains the supported workflow.

Verified on this Mac: Opera GX’s helper connection, TV discovery and companion launch. The companion’s file picker, MP4 cast/status and episode replacement were exercised on a physical Samsung S90F; the TV reported PLAYING. The user separately confirmed picture and sound for one MP4 through the local UPnP file-serving route. 77 Python, 47 JavaScript and 18 publishing/packaging tests pass.

The TV must support the file’s container/codecs. Direct URLs must be fetchable independently of the browser. For an unavailable stream, use the provider’s normal download option when permitted. Protected playback, browser-only blobs, transcoding and separate subtitle files are unsupported. Keep the computer on and connected during playback. Windows/Linux and other installed browsers remain runtime-unverified.

Download the ZIP, extract it to a permanent folder, and follow README.md. Python3.9+ is required. The checksum identifies the checked package. Optional support is never required; payment links are enabled only after confirming the actual recipient.

## Live verification

After publication, run `scripts/verify_publication.py` against the 1.2.0 ZIP. It must match the public source at the tag commit, downloaded ZIP and checksum before updating publication.json. Record the result in STATUS.md. Community outreach requires separate authorization and a current rules check.

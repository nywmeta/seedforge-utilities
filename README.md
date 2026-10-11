# Seedforge utilities

Small, free tools for everyday software frustrations. MIT licensed, with no mandatory account or payment.

## LAN Cast — play your videos on your TV

LAN Cast sends a direct video URL or a downloaded video file to a **UPnP / DLNA TV** on your local network. Use the Opera/Chrome/Edge extension for a direct stream, or its companion window to choose a downloaded episode and control playback. There is no cloud video upload, screen mirroring or runtime package download.

**[Download LAN Cast 1.2.0 release candidate](https://github.com/nywmeta/seedforge-utilities/releases/download/lan-cast-v1.2.0-rc/lan-cast-v1.2.0-rc.zip)** · [Release notes](https://github.com/nywmeta/seedforge-utilities/releases/tag/lan-cast-v1.2.0-rc) · [SHA-256](https://github.com/nywmeta/seedforge-utilities/releases/download/lan-cast-v1.2.0-rc/lan-cast-v1.2.0-rc.zip.sha256)

Extract the ZIP, keep it in a permanent folder, and follow the [setup instructions](utilities/lan-cast/README.md). Python **3.9+** is required. On Mac, the package has an installer and a standalone **Cast downloaded video.command** launcher.

### A simple episode workflow

1. Download the video through its provider’s normal download option.
2. Open **LAN Cast → Cast a downloaded video**.
3. Find your TV, choose the video, then **Cast to TV**.

Keep the computer on and connected during playback. The TV must expose UPnP AVTransport and support the video/audio format. Direct links must be independently fetchable by the TV. Protected streams, browser-only blobs, separate subtitle files and transcoding are unsupported.

### Use it with your AI assistant

A browser-controlling assistant can use the same visible controls to help cast an identified video to an identified TV. This was demonstrated during development. LAN Cast is the local casting tool; it does not include an AI model, API subscription or an automatic connection to every assistant. See [the assistant guide](utilities/lan-cast/AI-ASSISTANT.md).

### What we verified

The repaired **Opera GX helper connection**, TV discovery and companion launch were observed on macOS. The companion file picker, MP4 playback requests and episode replacement were exercised against a physical Samsung S90F; its status reported **PLAYING**. The user separately confirmed picture and sound for one of those MP4s through the local UPnP file-serving route. **77 Python, 47 JavaScript and 18 publishing/packaging tests** pass. See [the validation record](utilities/lan-cast/VALIDATION.md) for the scope and remaining platform checks.

This remains a release candidate. Windows/Linux and other installed browsers have not received runtime confirmation; results on one TV do not establish every website or format.

## Optional support

<!-- seedforge-support-start -->
Optional support is not configured yet. Every feature is free to use and modify.
<!-- seedforge-support-end -->

## How Seedforge works

We reproduce recurring problems, check existing free solutions, and build the smallest useful repair. A release proves delivery, not users or revenue. The [workflow](PIPELINE.md), [demand record](research/lan-cast-demand.md), and [results ledger](STATUS.md) preserve that evidence.

To repeat release checks from this repository:

```sh
python3 scripts/release.py --node node
```

Python 3.9+ and Node 22+ are development requirements. The command tests and reproducibly packages the utility; it never publishes or spends money. Public GitHub CI uses standard free runners, without artifact/cache storage.

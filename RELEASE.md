# LAN Cast release preparation

Status: checked release candidate. Public downloadable release verification is pending.

Repository: `nywmeta/seedforge-utilities`, public, MIT licensed.

Repository description: Small free MIT-licensed utilities for recurring software frustrations, starting with a direct-stream UPnP/DLNA caster.

Tag: `lan-cast-v1.1.1-rc`. Mark the release as a **prerelease**.

Title: LAN Cast 1.1.1 — direct-stream casting release candidate

## Release body

LAN Cast sends a direct video URL from Opera GX, Opera, Chrome or Edge to a local UPnP/DLNA renderer. It includes a Python standard-library helper for finding TVs and controlling playback. All features are free; source is MIT licensed. No account, subscription or backend is required.

This candidate fixes active-video selection and duplicate URLs, known DRM sources resurfacing, stale playback status when changing TVs, slow HTTP device responses and installer/XML validation edge cases.

**Physical TV playback and installed-browser native-host communication remain unverified.** Automated tests use a simulated renderer and browser APIs. Windows/Linux installation has automated path coverage but has not been exercised on those platforms.

The TV must expose UPnP AVTransport, fetch the URL independently and support the media format. Browser-only blob URLs, protected video and streams requiring browser login are unsupported. This utility does not mirror tabs or transcode video.

Download and extract the ZIP, then read its README for setup and removal. Python 3.9+ is required. The accompanying SHA-256 checksum identifies the checked package.

Optional support will be added only after the owner confirms a recipient page. Support is never required.

## Upload and verify

Publish the complete repository source, not only this document or the binary ZIP. Attach `dist/lan-cast-v1.1.1-rc.zip` and its `.sha256` file to the prerelease. Then run:

```sh
python3 scripts/verify_publication.py --repo nywmeta/seedforge-utilities --tag lan-cast-v1.1.1-rc --archive dist/lan-cast-v1.1.1-rc.zip
```

The verifier uses anonymous GitHub reads, checks every packaged source file at the release commit and downloads both assets. Only a complete successful check updates `publication.json`. Record the verified result in `STATUS.md` afterward. Do not send community announcements without specific authorization and a current rules check.

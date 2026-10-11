# Validation — LAN Cast 1.1.1 release candidate

Checked on macOS on 11 October 2026.

## Passed in this release

- **41 Python tests**, using Python 3.9.6. Coverage includes native framing and a real helper subprocess, isolated install/launcher/uninstall operations, a local simulated HTTP MediaRenderer, SOAP/DIDL metadata and faults, transport controls/status, discovery parsing, manual address lookup, validation limits, overall HTTP deadlines, forbidden XML characters and malformed saved native-host origins.
- **37 JavaScript tests**, using the bundled Node runtime. Coverage includes Manifest V3 permissions, trusted popup request boundary, native errors/timeouts, media scanning and canonical duplicate handling, playing-source priority, shadow DOM/restricted frames, DRM/blob filtering, popup request behavior, TV selection/status reset and Opera/Opera GX setup commands.
- JavaScript syntax checks and macOS launcher shell syntax.
- No real browser registrations changed by the tests; installer tests use temporary home directories. Network tests use a temporary simulated renderer on `127.0.0.1`.

The release gate also verifies required assets/documents, matching helper/extension versions, narrow permissions, configured funding prerequisites and ZIP integrity. Packaging fixes timestamps and file modes for reproducibility. SHA-256 is supplied beside each built ZIP. Pipeline verification tests are recorded separately in the repository checkpoint.

## Still requires real-device verification

- Native-host lookup and successful communication after installation inside an actual Opera GX/Opera/Chrome/Edge browser. An earlier local build loaded into Opera GX and displayed a missing-host error; that is not successful end-to-end setup.
- SSDP discovery and AVTransport actions on an actual home network and physical TV, including a Samsung S90F's model/region/firmware.
- Playback of intended direct streams and TV codec/format support. Acceptance of commands does not establish actual video playback.
- Windows/Linux installation on those operating systems. Path/registry logic has automated coverage but no platform runtime confirmation in this release.

## Repeat checks

From this utility folder:

```sh
python3 -B -m unittest discover -s tests -v
node --test tests/extension.test.mjs
```

For packaging, use `python3 scripts/release.py --node node` from the Seedforge repository root. The integration tests need permission to open a local test socket in a restricted environment.

This is a release candidate. No physical-TV, streaming-service or installed-browser compatibility is implied by these automated checks.

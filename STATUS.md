# Seedforge utility checkpoint

Updated 11 October 2026 (Europe/Helsinki).

## Active work

LAN Cast 1.2.0 is published and verified. It repairs macOS Opera registration and adds a downloaded-video companion window, episode replacement and an AI-assistant guide. Research confirms a recurring workflow in a competitive market. Scope: direct fetchable media URLs and downloaded files to UPnP AVTransport, with a local helper and extension access limited to the active tab. Do not claim broad website/TV compatibility or a bundled AI model.

## Publication

**Published and verified.** Public source: [nywmeta/seedforge-utilities](https://github.com/nywmeta/seedforge-utilities). Download: [LAN Cast 1.2.0 release candidate](https://github.com/nywmeta/seedforge-utilities/releases/tag/lan-cast-v1.2.0-rc), marked as a prerelease.

Anonymous verification succeeded on 11 October 2026 at 20:06 UTC. Tag commit: `dd7cc79dd2f36d71a6b3cf80f8b0ef9f4f466741`. The verifier checked public repository status, the tag commit, all 31 packaged source files, the MIT license, and the bytes of both the downloaded ZIP and checksum. `publication.json` records the verified result.

[GitHub's release checks passed](https://github.com/nywmeta/seedforge-utilities/actions/runs/38170683017) at the tag commit. Browser sign-in to the owner is working. The connector still rejects writes with “Resource not accessible by integration”; publication used the signed-in browser. Public status updates follow verification; the release tag stays at the checked source commit.

1.2.0 verification includes actual Opera GX native-host communication, TV discovery, companion launch, file-picker copy, cast, episode replacement and PLAYING status on a physical Samsung S90F. The user earlier confirmed picture and sound for one MP4 through the local UPnP file-serving route. These checks do not retroactively validate the 1.1.1 installer, which placed macOS Opera registration in the wrong folder. See the utility VALIDATION.md for exact evidence and limitations. Community announcements still require specific user authorization and a current rules check.

The previous 1.1.1 prerelease was anonymously verified at 09:13 UTC, tag `3a227b89892afa7b0cc9ef41601d6fe208bac2fb`; its historical record is superseded by the repaired 1.2.0 release.

## Optional support

The user suggested their PayPal. An existing PayPal.Me URL, ownership confirmation and permission to display it publicly were requested. No URL has been supplied or recipient page verified. `funding.json` is disabled; no payment link is published. Do not guess the handle from GitHub/email/name.

## Validation and artifacts

The complete release gate passed on 11 October 2026: **77 Python utility tests, 47 JavaScript utility tests and 18 offline pipeline tests** (142 total), plus syntax/file checks. Pipeline tests reject missing/mismatched public source and assets, invalid archives, hidden credential files, external symlinks and omitted code. They also check reproducible ZIP bytes and executable file modes. Live GitHub CI passed at the release tag commit.

Artifact: `dist/lan-cast-v1.2.0-rc.zip`, 31 files. SHA-256: `10df44ab83de76e4996f97746e821ad126d9816b9831c9aedd0c54b743d44142`. A checksum file is published alongside it. Automated mocks and a local simulated TV do not establish actual TV playback. See the utility's `VALIDATION.md` for physical evidence and remaining checks.

## Next bounded candidate

Read-only UPnP diagnosis: discovery results, renderer/server distinction, advertised transport capabilities, reachability and a support report. Evidence and alternatives in `research/lan-cast-demand.md`. Reproduce a concrete gap first; GUPnP Tools and existing casting projects already provide diagnosis. Prefer contributing a focused improvement upstream when it meets the need. Do not start another broad casting app or claim an uncontested market.

## Costs and actions

No purchases, subscriptions, advertising, credit purchases/resets or paid services initiated. Existing Codex allowance was used. No Reddit/forum/issue outreach was sent. A separate existing income automation belongs to another chat and was left intact; it is not a utility-publishing continuation.

## Weekly continuation

An active heartbeat named **Seedforge free utility pipeline** was created in this chat (automation ID `seedforge-free-utility-pipeline`). It runs Mondays at 10:00 Europe/Helsinki, with one bounded task, a usage check, €0 external spend and quiet handling of unchanged blockers. The local host, allowance and required account access must be available; this is not a guarantee of unattended publication. The prompt points to this checkpoint and the local reusable skill rather than repeating an account sweep.

## Installed 1.2.0 repair and file interface

The existing Opera GX extension was updated in place after folder write access was granted. Its matching helper was installed in the documented shared Chrome registration folder. The popup reports connected, discovers the physical TV, and opens the downloaded-video companion. The companion file picker and cast/status actions were exercised through the browser; the physical TV reported PLAYING. Private media addresses, episode files, device addresses and browser observations remain outside the public source/package. The checked 1.2.0 build is now published with matching public source and downloads.

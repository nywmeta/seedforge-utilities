# Seedforge utility checkpoint

Updated 11 October 2026 (Europe/Helsinki).

## Active work

LAN Cast 1.2.0 local repair candidate; published release remains 1.1.1. Existing local utility recovered and improved; research confirms a real recurring workflow but a competitive market. Narrow scope: direct non-DRM media URL to UPnP AVTransport, with local helper and browser permissions limited to the active tab. Do not claim broad website/TV compatibility.

## Publication

**Published and verified.** Public source: [nywmeta/seedforge-utilities](https://github.com/nywmeta/seedforge-utilities). Download: [LAN Cast 1.1.1 release candidate](https://github.com/nywmeta/seedforge-utilities/releases/tag/lan-cast-v1.1.1-rc), marked as a prerelease.

Anonymous verification succeeded on 11 October 2026 at 09:13 UTC. Tag commit: `3a227b89892afa7b0cc9ef41601d6fe208bac2fb`. The verifier checked public repository status, the tag commit, every packaged source file, the MIT license, and the bytes of both the downloaded ZIP and checksum. `publication.json` records the verified result. An additional check matched all 41 public source files to the prepared public source tree.

[GitHub's release checks passed](https://github.com/nywmeta/seedforge-utilities/actions/runs/38127183565) at the tag commit. Browser sign-in to the owner is working. The connector still rejects writes with “Resource not accessible by integration”; future connector use needs access to this repository. No credential extraction or unrelated repository reuse occurred. Public README/status updates follow verification; the release tag stays at the checked source commit. The final documentation commit `fb2885a82b0dd76575bc0cddd8a91ab6bb7f23f4` also passed [GitHub checks](https://github.com/nywmeta/seedforge-utilities/actions/runs/38127752820), and all 41 current source files were compared successfully again.

Local 1.2.0 verification now includes actual Opera GX native-host communication, TV discovery, companion launch, file-picker copy, cast and PLAYING status on a physical Samsung S90F. The user earlier confirmed picture and sound for the same MP4 through the local UPnP file-serving route. These checks do not retroactively validate the published 1.1.1 installer; that version placed macOS Opera registration in the wrong folder. Preserve the published prerelease label. See the current utility VALIDATION.md for exact evidence and limitations. Community announcements still require specific user authorization and a current rules check.

## Optional support

The user suggested their PayPal. An existing PayPal.Me URL, ownership confirmation and permission to display it publicly were requested. No URL has been supplied or recipient page verified. `funding.json` is disabled; no payment link is published. Do not guess the handle from GitHub/email/name.

## Validation and artifacts

The complete release gate passed on 11 October 2026: **41 Python utility tests, 37 JavaScript utility tests and 18 offline pipeline tests** (96 total), plus syntax/file checks. Pipeline tests reject missing/mismatched public source and assets, invalid archives, hidden credential files, external symlinks and omitted code. They also check reproducible ZIP bytes and executable file modes. The reusable skill passed its frontmatter validator. GitHub workflow structure and pinned official action commits were checked; live GitHub CI also passed at the release tag commit.

Artifact: `dist/lan-cast-v1.1.1-rc.zip`, 25 files. SHA-256: `a659b60f78f6acedd300bb506c7a7bf29c60124814b2d82a194f83a887e9bf8a`. A checksum file is supplied alongside it. Automated mocks and a local simulated TV do not establish actual TV playback. See the utility's `VALIDATION.md` for current evidence and remaining checks.

## Next bounded candidate

Read-only UPnP diagnosis: discovery results, renderer/server distinction, advertised transport capabilities, reachability and a support report. Evidence and alternatives in `research/lan-cast-demand.md`. Reproduce a concrete gap first; GUPnP Tools and existing casting projects already provide diagnosis. Prefer contributing a focused improvement upstream when it meets the need. Do not start another broad casting app or claim an uncontested market.

## Costs and actions

No purchases, subscriptions, advertising, credit purchases/resets or paid services initiated. Existing Codex allowance was used. No Reddit/forum/issue outreach was sent. A separate existing income automation belongs to another chat and was left intact; it is not a utility-publishing continuation.

## Weekly continuation

An active heartbeat named **Seedforge free utility pipeline** was created in this chat (automation ID `seedforge-free-utility-pipeline`). It runs Mondays at 10:00 Europe/Helsinki, with one bounded task, a usage check, €0 external spend and quiet handling of unchanged blockers. The local host, allowance and required account access must be available; this is not a guarantee of unattended publication. The prompt points to this checkpoint and the local reusable skill rather than repeating an account sweep.

## Local 1.2.0 repair and file interface

The existing Opera GX extension was updated in place after folder write access was granted. Its matching helper was installed in the documented shared Chrome registration folder. The popup now reports connected, discovers the physical TV, and opens the downloaded-video companion. The companion file picker and cast/status actions were exercised through the browser; the physical TV reported PLAYING. 77 Python and 47 JavaScript utility tests pass. Private media addresses, episode files, device addresses and browser observations remain outside the public source/package. The 1.2.0 build is a local candidate; no new GitHub publication is claimed.

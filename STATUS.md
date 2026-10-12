# Seedforge utility checkpoint

Updated 12 October 2026 (Europe/Helsinki).

## Active work

LAN Cast 1.2.1 is published and anonymously verified. The maintenance patch fixes stale playback controls across companion windows, preserves active/staged video and TV selection, and avoids extending idle lifetime through passive refreshes. Keep one utility active; no new build was started. The earlier intermittent user report recovered before the patch and its cause remains unconfirmed. The installed helper remains 1.2.0; this scheduled run changed no TV playback or browser registration.

## Publication

**Published and verified.** Public source: [nywmeta/seedforge-utilities](https://github.com/nywmeta/seedforge-utilities). Download: [LAN Cast 1.2.1 release candidate](https://github.com/nywmeta/seedforge-utilities/releases/tag/lan-cast-v1.2.1-rc), marked as a prerelease.

Anonymous verification succeeded on 12 October 2026 at 07:24 UTC. Tag commit: `4e41da978c2091473c55aef06ddbd912967db741`. The verifier checked the active public repository, all 32 packaged source files at the tag, the MIT license and the anonymous ZIP/checksum downloads. SHA-256: `55890d18ee7ed104011dafcd453b6ea53dec6bfa14ca9121e52bf9f0d1100472`. `publication.json` contains the actual record produced by the verifier.

[The full release gate passed](https://github.com/nywmeta/seedforge-utilities/actions/runs/38216963159), and [anonymous publication verification passed](https://github.com/nywmeta/seedforge-utilities/actions/runs/38217504583) from the release tag. The local full gate was blocked by loopback socket permissions, so the existing standard free public runner executed the same gate. The locally packaged ZIP matched its checked build byte for byte. Browser publication access worked; unchanged connector write failures were not retried. The release tag remains pinned to the checked source commit.

1.2.0 verification includes actual Opera GX native-host communication, TV discovery, companion launch, file-picker copy, cast, episode replacement and PLAYING status on a physical Samsung S90F. The user earlier confirmed picture and sound for one MP4 through the local UPnP file-serving route. These checks do not retroactively validate the 1.1.1 installer, which placed macOS Opera registration in the wrong folder. See the utility VALIDATION.md for exact evidence and limitations. Community announcements still require specific user authorization and a current rules check.

The previous 1.2.0 prerelease was anonymously verified on 11 October at 20:06 UTC, tag `dd7cc79dd2f36d71a6b3cf80f8b0ef9f4f466741`; its ZIP SHA-256 was `10df44ab83de76e4996f97746e821ad126d9816b9831c9aedd0c54b743d44142`. The 1.2.1 maintenance patch has not yet received new installed-browser or physical-TV verification.

The previous 1.1.1 prerelease was anonymously verified at 09:13 UTC, tag `3a227b89892afa7b0cc9ef41601d6fe208bac2fb`; its historical record is superseded by the repaired 1.2.0 release.

## Optional support

The user suggested their PayPal. An existing PayPal.Me URL, ownership confirmation and permission to display it publicly were requested. No URL has been supplied or recipient page verified. `funding.json` is disabled; no payment link is published. Do not guess the handle from GitHub/email/name.

## Validation and artifacts

The complete 1.2.1 release gate passed on 12 October 2026 in GitHub CI: **78 Python utility tests, 56 JavaScript utility tests and 18 publishing/packaging tests** (152 total), plus syntax/file checks and reproducible packaging. Nine new UI behavior tests and one passive-state idle-lifetime test cover the maintenance patch. The local non-socket checks passed: 52 Python tests, all 56 JavaScript tests and all 18 pipeline tests.

Artifact: `dist/lan-cast-v1.2.1-rc.zip`, 32 reviewed files. SHA-256: `55890d18ee7ed104011dafcd453b6ea53dec6bfa14ca9121e52bf9f0d1100472`. A matching checksum file is published alongside it. Prior 1.2.0 device observations are explicitly separated from simulated 1.2.1 UI checks in VALIDATION.md. No new universal browser, stream, codec or TV claim is made.

Allowance was checked before the scheduled work. No credits/reset were purchased or redeemed. The public workflow uses contents-read permissions, removes checkout credentials before scripts, has no artifact/cache steps, and supports an optional manual anonymous release check.

## Next bounded candidate

Read-only UPnP diagnosis: discovery results, renderer/server distinction, advertised transport capabilities, reachability and a support report. Evidence and alternatives in `research/lan-cast-demand.md`. Reproduce a concrete gap first; GUPnP Tools and existing casting projects already provide diagnosis. Prefer contributing a focused improvement upstream when it meets the need. Do not start another broad casting app or claim an uncontested market.

## Costs and actions

No purchases, subscriptions, advertising, credit purchases/resets or paid services initiated. Existing Codex allowance was used. No Reddit/forum/issue outreach was sent. A separate existing income automation belongs to another chat and was left intact; it is not a utility-publishing continuation. This scheduled run used one read-only helper and completed one bounded LAN Cast maintenance patch.

## Weekly continuation

An active heartbeat named **Seedforge free utility pipeline** was created in this chat (automation ID `seedforge-free-utility-pipeline`). It runs Mondays at 10:00 Europe/Helsinki, with one bounded task, a usage check, €0 external spend and quiet handling of unchanged blockers. The local host, allowance and required account access must be available; this is not a guarantee of unattended publication. The prompt points to this checkpoint and the local reusable skill rather than repeating an account sweep.

## Installed 1.2.0 repair and file interface

During 1.2.0 validation, the existing Opera GX extension was updated in place after folder write access was granted. Its matching helper was installed in the documented shared Chrome registration folder. The popup reported connected, discovered the physical TV, and opened the downloaded-video companion. The companion file picker and cast/status actions were exercised through the browser; the physical TV reported PLAYING. Private media addresses, episode files, device addresses and browser observations remain outside the public source/package. The installed files still report 1.2.0; the 1.2.1 maintenance patch is published separately.

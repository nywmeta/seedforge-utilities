# Lan Cast

**1.2.2 release candidate · MIT licensed · free to use.**

A browser extension for Opera GX, Opera, Chrome and Microsoft Edge that sends a direct web video URL to a UPnP/DLNA TV on your local network. A companion window also lets you choose a downloaded video and play it on the TV, with no cloud service or account.

## Opera GX on Mac

1. Unzip this package and keep the `lan-cast` folder somewhere permanent.
2. In Opera GX, open `opera://extensions`. Enable **Developer mode**, choose **Load unpacked**, and select this package's `extension` folder. If Lan Cast is already loaded from that folder, choose **Reload**.
3. Copy the extension's 32-letter **ID** shown on that page.
4. Double-click **Install on Mac.command**. Press Return to choose the default browser, **opera-gx**, then paste the ID.
5. Reload the extension on `opera://extensions`. Pin **Lan Cast** in Opera GX's extensions menu, then open it.

Python **3.9 or newer** must be installed. No administrator rights are needed. Keep that Python installation available; the helper uses only its standard library and runs when Lan Cast needs it.

If the launcher cannot open, run this from a terminal in the `lan-cast` folder. Replace `YOUR_EXTENSION_ID` with the ID you copied:

```sh
python3 helper/install.py --extension-id YOUR_EXTENSION_ID --browser opera-gx
```

The installer copies the helper into your user application-data folder and connects it to the selected browser. See `VALIDATION.md` for the checks performed in this build.

## AI-assisted casting

A browser-controlling assistant can operate LAN Cast’s visible controls, as demonstrated during development. LAN Cast supplies the local extension and companion, with no bundled AI model, API subscription or universal website access. See [the assistant guide](AI-ASSISTANT.md) for a task example and the supported direct-stream/download routes.

## Cast a downloaded episode

1. Download the video through its provider’s normal download option.
2. Open **Cast a downloaded video** in the LAN Cast popup. On a Mac you can also double-click **Cast downloaded video.command** in this package, even before browser setup.
3. Choose **Find TVs**, select your TV, then use **Video file** to choose the episode from your computer. If discovery misses the TV, enter its IP or full device-description URL.
4. Wait for the local copy to finish, then choose **Cast to TV**. Use **Play**, **Pause**, **Stop**, and **Check status** in the window. Use **Back 30 seconds**, **Forward 30 seconds**, or enter `12:30` / `1:02:03` in **Jump to time**, then press **Go**.

The computer must stay on and connected throughout playback. On a Mac the helper temporarily prevents idle sleep while serving; keep the lid open. MP4 is a useful first choice, but the TV must support the video and audio codecs. Separate subtitle files and transcoding are not supported. Up to 8 GB per file; a private temporary copy is removed on normal helper exit or when the video is replaced; an abnormal termination can leave private temporary copies. The interface shuts down after eight hours without activity, including video transfers.

Windows/Linux users can run `python3 helper/companion.py --open` (on Windows, `py -3 helper/companion.py --open`). Their runtime setup has not been verified.

## Other browsers and Windows

For Chrome, open `chrome://extensions`; for Edge, open `edge://extensions`. Follow the same **Developer mode → Load unpacked → copy ID** steps. Standard Opera uses `opera://extensions`.

On Mac, **Install on Mac.command** lets you choose `opera-gx`, `opera`, `chrome`, `edge` or `chromium`. For a terminal install, use the command above with the matching `--browser` value. Run it separately for each browser using that browser's extension ID.

On Windows, double-click **Install on Windows.cmd**, choose your browser and paste its ID. The terminal alternative for Opera GX is:

```powershell
py -3 helper/install.py --extension-id YOUR_EXTENSION_ID --browser opera-gx
```

Change `opera-gx` to `chrome` or `edge` for those browsers. Windows installation has not been verified on Windows. On macOS and Windows, Opera GX, Opera and Chrome share this helper's registration; see **Remove** before uninstalling it from one of those browsers.

Linux users can run the `python3` command with `--browser chrome`, `edge`, `opera` or `chromium`; those Linux paths are unverified. Add `--dry-run` to preview an install without changing files. A browser managed by your organization may prevent helper installation.

## Cast a video

1. Turn on your TV and connect it and your computer to the same home network.
2. Open a page with a video and open **Lan Cast**. Scan the page, then choose a detected stream; alternatively paste a direct `https://…/video.mp4` link.
3. Choose **Find TVs**, then select your TV. If the TV asks to allow your computer, accept on the TV.
4. Choose **Cast to TV**. Use the popup's play, pause, stop, and status controls as supported by the TV.

If automatic discovery misses the TV, use the manual connection option with the TV's IPv4 address (for example `192.168.1.50`). If it does not respond to unicast discovery, enter its full UPnP device-description URL, including the correct port and path. An IP alone is not a guaranteed fallback: the helper does not guess manufacturer-specific ports.

## Seeking and fast-forward

Downloaded files advertise byte-range seeking to the TV. Physical remote seeking was confirmed on a Samsung S90F with one downloaded MP4. TV and format support varies; remote web URLs keep their original general metadata. The time controls send UPnP seeking commands and report acceptance separately from the observed position. Some TVs move to a nearby keyframe or change playback state after seeking; use Play/Pause as needed. If the TV does not report its current time, the 30-second buttons cannot calculate a jump; use **Jump to time** instead.

## TV compatibility

This extension requires a TV to advertise a **UPnP MediaRenderer with an AVTransport service**. A TV advertising DLNA alone does not prove it accepts remote playback commands. The helper checks for AVTransport before allowing a connection.

A downloaded MP4 was played on a physical Samsung S90F over UPnP on 11 October 2026; the user confirmed picture and sound. That check used the local file-serving route. It does not establish compatibility with every website, codec, or TV. Automated checks also use a simulated renderer. Cast success means the TV accepted the commands; verify the picture on your TV.

## Which streams work?

- Direct HTTP/HTTPS video URLs that the TV can fetch independently. MP4 with a TV-supported video/audio codec is a useful first test. Supported formats depend on the TV.
- HLS (`.m3u8`) or DASH (`.mpd`) links only when the TV's UPnP playback service supports that format. Finding a URL does not guarantee that it can play.
- Signed URLs may work until they expire. Query parameters are preserved, but browser cookies, authorization headers, or special referrer headers are not transferred.
- Browser-only `blob:` streams, DRM-protected playback, YouTube's usual browser player, and Netflix-style subscription players are not generally castable by sending their page URL. Some pages expose a usable manifest in their recent network entries; the scanner labels those as candidates.

The extension sends a direct stream URL to the TV. For downloaded files, the companion serves only the selected video to the selected TV on your local network. Neither route mirrors your tab, transcodes, or bypasses a provider’s access restrictions.

## Troubleshooting

- **Downloaded-video controls look out of date:** Visible companion windows refresh their shared casting state every five seconds and when you return to a window. After **Stop**, use **Cast to TV** to play again; Stop closes the temporary file-serving session.
- **Helper not found / forbidden:** Check the copied extension ID, the browser selected during installation, and that Python still exists. Re-run the installer, then reload the extension.
- **No TVs:** Confirm the TV is on, both devices are on the same network, and guest Wi-Fi/client isolation is disabled. A VPN or firewall can block SSDP discovery (UDP port 1900). Allow the browser/Python local-network access if your operating system asks. Router internet port forwarding is unnecessary.
- **TV found but cast fails:** Try a direct MP4 URL accessible without logging in, check the TV's permission prompt, and inspect the error shown in Lan Cast. The TV may reject a format or playback action.
- **Pause / seek rejected:** These actions depend on the renderer and stream. Live streams commonly cannot seek.
- **UPnP 701 while replacing a paused video:** Stop the current session, then use **Cast to TV** again. This recovery was needed once on the tested TV.
- **Old helper window after updating:** Close it and reopen **Cast a downloaded video** so the new helper serves the file with updated seek information; reload the extension after updating its source folder.
- **Video not found:** Start the page video once, scan again, or paste a known direct stream URL. Browser internal pages, restricted pages, and some cross-origin frames cannot be scanned.

## Remove

Remove Lan Cast from your browser's extensions page. From the package folder, unregister the helper:

```sh
python3 helper/install.py --uninstall --browser opera-gx
```

Use `--browser opera` for Opera, `chrome` for Chrome, `edge` for Edge, or `all` for all supported browser registrations. On Windows use `py -3` instead of `python3`. The uninstaller leaves the helper files in your application-data folder because another browser may use them; the printed folder can be deleted after all registrations are removed.

On macOS and Windows, uninstalling the helper for Opera GX, Opera or Chrome removes their shared Lan Cast registration and can disconnect Lan Cast in the other two browsers. Re-run the installer with each remaining browser's extension ID to restore access. This shared registration follows [Opera's documented native messaging locations](https://help.opera.com/en/extensions/message-passing/#native-messaging-host).

## Permissions and architecture

The extension uses `activeTab` and `scripting` to scan the page when opened, `storage` for selected devices/preferences, and `nativeMessaging` to contact the helper. It requests no persistent access to every website. Detected media URLs are used for casting; TV addresses, your last selected stream URL and a pasted direct URL may be saved locally. Those URLs can contain signed tokens; see `PRIVACY.md` for details and removal instructions. No analytics or external account is required.

The helper sends bounded SSDP discovery packets and reads device descriptions, then invokes `SetAVTransportURI`, `Play`, and other AVTransport actions with XML SOAP. It accepts local literal IP addresses for TV endpoints, rejects redirects and cross-host service endpoints, and does not fetch a website’s video itself. The companion’s controls listen only on loopback, use a private address and request token, and expose the selected file only to the selected TV IP. Discovery and local file serving are IPv4. Explicit local IPv6 description URLs are accepted, but scoped link-local IPv6 addresses (containing `%`) are unsupported.

Developer references: [loading Opera extensions](https://help.opera.com/en/extensions/basics/), [Opera native messaging](https://help.opera.com/en/extensions/message-passing/), [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging), [Edge native messaging](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging), and the [UPnP AVTransport specification](https://www.upnp.org/specs/av/UPnP-av-AVTransport-v3-Service.pdf).

## Validation

From the package folder:

```sh
python3 -B -m unittest discover -s tests -v
node --test tests/*.test.mjs
```

The Python tests exercise a simulated local renderer, discovery parsing, SOAP/XML behavior, framing, validation, and isolated user-directory installation. JavaScript checks cover the scanner and trusted native-message boundary. See `VALIDATION.md` for the checks actually performed in this build and remaining physical-device checks.

## License and support

MIT licensed; see `LICENSE`. All features are free to use and modify.

<!-- seedforge-support-start -->
Optional support is not configured yet.
<!-- seedforge-support-end -->

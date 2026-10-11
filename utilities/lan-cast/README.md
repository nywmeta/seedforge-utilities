# Lan Cast

**1.1.1 release candidate · MIT licensed · physical TV playback remains unverified.**

A browser extension for Opera GX, Opera, Chrome and Microsoft Edge that sends a web video URL to a UPnP/DLNA TV on your local network. Includes a small Python helper for finding TVs and controlling playback.

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

## Other browsers and Windows

For Chrome, open `chrome://extensions`; for Edge, open `edge://extensions`. Follow the same **Developer mode → Load unpacked → copy ID** steps. Standard Opera uses `opera://extensions`.

On Mac, **Install on Mac.command** lets you choose `opera-gx`, `opera`, `chrome`, `edge` or `chromium`. For a terminal install, use the command above with the matching `--browser` value. Run it separately for each browser using that browser's extension ID.

On Windows, double-click **Install on Windows.cmd**, choose your browser and paste its ID. The terminal alternative for Opera GX is:

```powershell
py -3 helper/install.py --extension-id YOUR_EXTENSION_ID --browser opera-gx
```

Change `opera-gx` to `chrome` or `edge` for those browsers. Windows installation has not been verified on Windows. On Windows, Opera GX, Opera and Chrome share this helper's registration; see **Remove** before uninstalling it from one of those browsers.

Linux users can run the `python3` command with `--browser chrome`, `edge`, `opera` or `chromium`; those Linux paths are unverified. Add `--dry-run` to preview an install without changing files. A browser managed by your organization may prevent helper installation.

## Cast a video

1. Turn on your TV and connect it and your computer to the same home network.
2. Open a page with a video and open **Lan Cast**. Scan the page, then choose a detected stream; alternatively paste a direct `https://…/video.mp4` link.
3. Choose **Find TVs**, then select your TV. If the TV asks to allow your computer, accept on the TV.
4. Choose **Cast to TV**. Use the popup's play, pause, stop, and status controls as supported by the TV.

If automatic discovery misses the TV, use the manual connection option with the TV's IPv4 address (for example `192.168.1.50`). If it does not respond to unicast discovery, enter its full UPnP device-description URL, including the correct port and path. An IP alone is not a guaranteed fallback: the helper does not guess manufacturer-specific ports.

## TV compatibility

This extension requires a TV to advertise a **UPnP MediaRenderer with an AVTransport service**. A TV advertising DLNA alone does not prove it accepts remote playback commands. The helper checks for AVTransport before allowing a connection.

**Playback on a physical Samsung S90F or any other physical TV has not been verified in this release.** Discovery and playback protocol checks use a simulated renderer. Cast success means the TV accepted the commands; verify the picture on your TV. Unsupported formats or expired URLs can still fail afterward.

## Which streams work?

- Direct HTTP/HTTPS video URLs that the TV can fetch independently. MP4 with a TV-supported video/audio codec is a useful first test. Supported formats depend on the TV.
- HLS (`.m3u8`) or DASH (`.mpd`) links only when the TV's UPnP playback service supports that format. Finding a URL does not guarantee that it can play.
- Signed URLs may work until they expire. Query parameters are preserved, but browser cookies, authorization headers, or special referrer headers are not transferred.
- Browser-only `blob:` streams, DRM-protected playback, YouTube's usual browser player, and Netflix-style subscription players are not generally castable by sending their page URL. Some pages expose a usable manifest in their recent network entries; the scanner labels those as candidates.

The extension sends the stream URL to the TV. It does not mirror your tab, transcode, or host/proxy the video. To cast a file from your computer, first make it available at an HTTP URL that the TV can reach.

## Troubleshooting

- **Helper not found / forbidden:** Check the copied extension ID, the browser selected during installation, and that Python still exists. Re-run the installer, then reload the extension.
- **No TVs:** Confirm the TV is on, both devices are on the same network, and guest Wi-Fi/client isolation is disabled. A VPN or firewall can block SSDP discovery (UDP port 1900). Allow the browser/Python local-network access if your operating system asks. Router internet port forwarding is unnecessary.
- **TV found but cast fails:** Try a direct MP4 URL accessible without logging in, check the TV's permission prompt, and inspect the error shown in Lan Cast. The TV may reject a format or playback action.
- **Pause / seek rejected:** These actions depend on the renderer and stream. Live streams commonly cannot seek.
- **Video not found:** Start the page video once, scan again, or paste a known direct stream URL. Browser internal pages, restricted pages, and some cross-origin frames cannot be scanned.

## Remove

Remove Lan Cast from your browser's extensions page. From the package folder, unregister the helper:

```sh
python3 helper/install.py --uninstall --browser opera-gx
```

Use `--browser opera` for Opera, `chrome` for Chrome, `edge` for Edge, or `all` for all supported browser registrations. On Windows use `py -3` instead of `python3`. The uninstaller leaves the helper files in your application-data folder because another browser may use them; the printed folder can be deleted after all registrations are removed.

On Windows, uninstalling the helper for Opera GX, Opera or Chrome removes their shared Lan Cast registration and can disconnect Lan Cast in the other two browsers. Re-run the installer with each remaining browser's extension ID to restore access. This shared registration follows [Opera's documented Windows native messaging location](https://help.opera.com/en/extensions/message-passing/#native-messaging-host).

## Permissions and architecture

The extension uses `activeTab` and `scripting` to scan the page when opened, `storage` for selected devices/preferences, and `nativeMessaging` to contact the helper. It requests no persistent access to every website. Detected media URLs are used for casting; TV addresses, your last selected stream URL and a pasted direct URL may be saved locally. Those URLs can contain signed tokens; see `PRIVACY.md` for details and removal instructions. No analytics or external account is required.

The helper sends bounded SSDP discovery packets and reads device descriptions, then invokes `SetAVTransportURI`, `Play`, and other AVTransport actions with XML SOAP. It accepts local literal IP addresses for TV endpoints, rejects redirects and cross-host service endpoints, and does not fetch the video itself. Discovery is IPv4. Explicit local IPv6 description URLs are accepted, but scoped link-local IPv6 addresses (containing `%`) are unsupported.

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

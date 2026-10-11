# LAN Cast privacy

LAN Cast has no telemetry, advertising, backend account or analytics. Its helper uses Python's standard library. No runtime packages are downloaded.

When you open the popup and scan, the extension examines accessible video/audio elements and recent resource URLs in that tab. It uses a temporary `activeTab` permission; it does not request permanent access to all websites. Browser protections can prevent scanning restricted pages and cross-origin frames.

Detected media URLs remain in the popup until you select a stream. Your last selected stream URL, a pasted direct URL, selected TV location and manually added device details may be saved in local browser extension storage for convenience. These URLs may include signed query tokens. Browser cookies, authorization headers, passwords and referrer headers are not forwarded. Do not share signed links in bug reports. Removing the extension removes its storage; your browser's extension/site-data controls can also clear it.

The native helper receives only validated requests from the extension's own popup. It sends discovery packets on your local network and reads UPnP device descriptions/control responses from literal local IP endpoints. It refuses redirects and service URLs on other hosts. It sends the chosen media URL and title to your TV using SOAP. The TV then fetches the media from the URL's server itself; that server may see the TV's request and your network's public IP.

Other devices on the same LAN may see discovery traffic. UPnP control commonly uses plain HTTP on your local network. Use a network you trust. LAN Cast neither opens router ports nor disables firewalls. It does not fetch/proxy the media, mirror your display or bypass protected playback.

Optional support links, when configured, open the payment provider's site. The extension does not collect payment details. Payment-provider terms and privacy policies apply on that site.

Unregister the helper using the README's removal command. Helper files are retained until you remove them because another browser registration may use them. No browser history or cast event log is created by the helper.

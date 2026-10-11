# Use LAN Cast with your assistant

If your AI assistant can operate your browser, it can use LAN Cast's visible controls to help cast a video. The assistant's browser access comes from the tools you give it; LAN Cast supplies the extension and local companion window. No model or API subscription is included or required by LAN Cast.

## Set up once

Install Python **3.9 or newer**, keep this package in a permanent folder, and load its `extension` folder through your browser's **Developer mode → Load unpacked**. Run **Install on Mac.command** or **Install on Windows.cmd**, select your browser, and paste the extension ID. Reload the extension. See [installation instructions](README.md) for details and other platforms.

Turn on the TV and connect it and your computer to the same home network. Allow the browser or Python local-network access when your operating system asks. If the TV asks to allow your computer, accept using its remote.

## Give the assistant a clear task

For example: “Cast this video to my living-room TV using LAN Cast. You may find the TV and use playback controls. If a direct stream cannot play, use the site's normal download option only if it permits downloading.”

Identify the intended TV and video. Grant the assistant access needed for that task; it can continue the authorized steps without asking again for each button. You may need to handle permission prompts, a file picker, or the TV's remote.

## Prefer a direct stream

Open and start the video, then open **LAN Cast → Scan page**. Choose a detected stream, **Find TVs**, select the intended TV, and **Cast to TV**. This works when the TV can independently fetch and play that stream.

If an embedded player is missed, open the player's own page and scan again. Browser-only streams, protected playback, and streams requiring your browser's login may be unavailable.

## Use a permitted download when needed

Use the provider's normal **Download** option only when allowed. Open **Cast a downloaded video**, find and select the TV, choose **Video file**, wait for the copy, then **Cast to TV**. Keep the companion window open and the computer awake and connected. Use **Play**, **Pause**, **Stop**, and **Check status** there.

Confirm picture and sound on the physical TV. Ask the assistant to keep its work scoped to the chosen video and avoid copying signed stream URLs or unrelated browsing history into chats or logs.

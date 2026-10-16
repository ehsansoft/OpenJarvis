---
name: screen-capture-kit
description: Record desktop app flows (Voicebox, VS Code, plugin admin) with ffmpeg gdigrab region capture and trim them, saving everything on D:.
version: 0.1.0
author: Ehsan OpenJarvis
---

# Screen Capture Kit

ffmpeg gdigrab recipes for desktop captures when the target is not a browser
page (browser targets go through `storyboard-recorder` first).

## Before recording (approval gates)

- Reviewer explicitly OKs each desktop recording: app, capture region, purpose.
- Confirm no sensitive windows (password managers, email, chats, wallets) are
  visible or in the taskbar/live-preview area; region must cover only the demo
  window.

## Recipes

- Full screen: `ffmpeg -f gdigrab -framerate 30 -i desktop -c:v libx264 -preset veryfast -crf 23 out.webm`
- Region: add `-offset_x <x> -offset_y <y> -video_size <WxH>` measured from the
  window bounds.
- Audio: OFF by default. Narration is added in post (caption-sync TTS or Ehsan's
  Persian recordings) — this removes mic noise and keeps sync deterministic.
  Slating: wait 2 s before the first action.
- Trim (re-encode, frame-accurate): `ffmpeg -i in.webm -ss <start> -t <secs> -c:v libx264 -crf 23 out.mp4`.
  Stream-copy (`-c copy`) only when the cut lands on keyframes.

## Hygiene + outputs

- Save raw to `D:\Media\<project>\tutorials\raw\<date>-<slug>-takeN.webm`;
  never to C:, Desktop, or any temp path on C:.
- One take per attempt; discard failed takes after the approval decision unless
  they serve as b-roll.
- CPU discipline: no capture while a local model inference is running;
  sequential jobs only, ~30 fps veryfast is safe for this machine.

Instruction-only workspace procedure. No executable resources or additional authority.

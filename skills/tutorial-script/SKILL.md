---
name: tutorial-script
description: Write tutorial video scripts in TTS (English) or human-narration (Persian) mode with timed scene lists matched to the storyboard.
version: 0.1.0
author: Ehsan OpenJarvis
---

# Tutorial Script

Produce the script and narration brief for one tutorial video. Two modes, chosen
by the reviewer; do not switch modes silently.

## Inputs (collect before writing)

1. Subject: project name, feature/flow being demonstrated, objective ("teach X", "tour Y").
2. Target duration (default 3 minutes; ask if unknown).
3. Mode: `tts-en` (Voicebox Kokoro speaks) or `human-fa` (Ehsan records the narration in Persian).
4. Evidence: the current UI state. Prefer a fresh `ui-audit` screenshot set or ask for one;
   never describe UI features from memory alone.

## Research rules

- Read only repo sources the reviewer pointed at (README, docs, the page/component files).
- For public/synthetic context (`free/*` models or web research) follow the privacy law:
  private project details stay local; explicit approval for each remote use.
- Facts in the script must be tied to evidence (file, URL, or screenshot) in a short
  evidence list; label anything uncertain as an assumption.

## Scene format (both modes)

Numbered scenes, one per screen or interaction, each with:
- scene id (S01, S02, ...);
- screen/state (URL or app window and what must be visible);
- action cues in prose (what is clicked/filled/scrolled, in order);
- narration line: English (`tts-en`, 12–22 words, plain sentences) or
  Persian (`human-fa`, short hi-rest sentences, formal but friendly fa-IR);
- target seconds (aim 5–12 s per scene; mention when a click needs settling time);
- on-screen takeaway text (max 6 words) if the composite uses captions.

End the document with: glossary (fa↔en for RTL-theme tutorials), open questions,
and an evidence list.

## Mode rules

- `tts-en`: definitions must be speakable as-is; no arrows, no parentheses-heavy
  text, spell out numbers; note pronunciation of any non-English word.
- `human-fa`: every scene's narration line is written so Ehsan reads it once,
  cleanly: one idea per sentence, pausing cues marked with «×» where on-screen
  actions happen. Add the recording checklist: 10 s silence lead-in, one try per
  scene, per-scene separate WAV files (`raw/S01.wav`, ...) saved into
  `D:\Media\<project>\tutorials\raw\`.

## Outputs

- Script + narration brief: `D:\Media\<project>\tutorials\script\<date>-<slug>.md`
  (mirrored into the board task for review).
- Draft only — nothing is recorded, rendered or published without approval.

Instruction-only workspace procedure. No executable resources or additional authority.

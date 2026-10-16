---
name: caption-sync
description: Generate scene/word-level SRT captions from narration audio, fully local, with TTS ground-truth mode for precision (en + fa).
version: 0.1.0
author: Ehsan OpenJarvis
---

# Caption Sync

Turn narration audio into SRT under `D:\Media\<project>\tutorials\captions\`.
No cloud transcription services, ever.

## Mode A — TTS ground truth (preferred when narration is Voicebox TTS)

- Render the narration sentence-by-sentence through the Voicebox speak endpoint
  (see its README/docs for the exact route), measure each WAV's duration
  exactly, and build cue timings as cumulative offsets. Captions become exact
  by construction — no ASR drift.
- Rules: one cue per sentence; split further only above ~2.5 s or 6–7 words on
  screen.

## Mode B — ASR on recorded audio (human narration, desktop captures)

- Model: the already-verified faster-whisper CT2 turbo (locate its directory
  under `D:\AI-Control\…` before first run; do not re-download). Runs inside
  the D: venv with `language` set explicitly (`"en"` or `"fa"`) and
  word-level timestamps.
- Merge words into cues (≤ 6–7 words, ≤ 2.5 s; prefer split points at pauses
  > 0.3 s).
- Persian note: ASR on fa-IR technical vocabulary is imperfect — spot-check
  terms against the script's glossary and correct before
  publishing.

## Verification + outputs

- Spot-check the first, middle and last cue against the audio; fix drift by
  re-measuring, not by hand-editing dozens of cues.
- Naming mirrors the video: `<date>-<slug>-<lang>.srt` (`-fa` / `-en`).
- If measured durations conflict with the storyboard's target scene lengths,
  flag which scenes need trimming — the audio is the source of truth for
  pacing.

Instruction-only workspace procedure. No executable resources or additional authority.

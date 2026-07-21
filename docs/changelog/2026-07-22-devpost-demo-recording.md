# Devpost demo recording and final export

Date: 2026-07-22

## Summary

Captured the real MEYES application flow and produced a verified sub-three-minute Devpost demo with
English narration explaining the product, Codex collaboration, and GPT-5.6 usage.

## Added

- A real window-capture utility that records an exact native HWND without storing camera frames
  separately.
- A reusable voiceover generator using the installed Microsoft Hazel Desktop voice.
- A deterministic OpenCV compositor for branded scenes, real application footage, burned-in
  captions, and upload-timed external subtitles.
- Browser-native VP9/Opus mux and media-probe pages that require no downloaded executable.
- The final `1280×720` WebM and English SRT in `docs/media/demo/`.
- A YouTube title, description, chapters, AI-voice disclosure, and publication checklist.

## Recorded evidence

- Smooth Pursuit completed with `316` live samples and all `9/9` screen regions.
- The accepted calibration reported RMSE `0.0995`, mean error `0.0890`, maximum error `0.1870`,
  and `18` holdout samples.
- The capture includes the cancel-default Live Input consent dialog, the persistent
  `REAL OS OUTPUT ENABLED` state, visible gaze-pointer movement, and a return to Safe Mode.

## Verification

- Full repository gate: documentation and icon verification, Ruff format/lint, strict mypy, and
  `822` passing pytest cases.
- Final decoded timestamp: `153.994` seconds (`00:02:34` rounded).
- Final frame size: `1280×720`.
- Video codec marker: `V_VP9`.
- Audio codec marker: `A_OPUS`.
- Browser probe: one audio track and non-zero decoded audio bytes.
- Final frame: branded MEYES `WHAT COMES NEXT` outro.
- SHA-256: `1031d2c61bc1d81b21cca35d2ac63db33bbd31b18343e416b205fee3bf8ad6af`.
- Reviewed a full-timeline contact sheet before removing intermediate and raw captures.

## Known limitations

- The narration is synthetic and must retain the included disclosure when published.
- YouTube publication, Public visibility, logged-out URL verification, and entrant consent review
  remain external account actions.
- This one-device capture is demonstration evidence, not broad webcam, lighting, or accessibility
  validation.

## Next task

Perform the entrant's final playback/consent review, publish the verified file to YouTube as Public,
confirm the URL while logged out, and paste that exact URL into Devpost.

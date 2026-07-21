# MEYES YouTube demo package

The final local export is ready for the Devpost video field:

| Artifact | Value |
|---|---|
| Video | [`media/demo/meyes-demo-devpost-final.webm`](./media/demo/meyes-demo-devpost-final.webm) |
| Captions | [`media/demo/meyes-demo-devpost-final-en.srt`](./media/demo/meyes-demo-devpost-final-en.srt) |
| Duration | `00:02:34` by the final decoded video timestamp |
| Frame | `1280×720`, 15 FPS source cadence |
| Tracks | VP9 video and Opus audio |
| SHA-256 | `1031d2c61bc1d81b21cca35d2ac63db33bbd31b18343e416b205fee3bf8ad6af` |

The English voiceover explains what I built, the local-first privacy and explicit-consent model,
Smooth Pursuit calibration, real Windows pointer output, my use of Codex, and my use of GPT-5.6.
The narration uses the Microsoft Hazel Desktop synthetic voice. Burned-in English captions and a
separate upload-ready SRT are included.

## Recommended YouTube title

```text
MEYES — Hands-Free Windows Control with Webcam Eye Gaze | OpenAI Build Week
```

## Recommended YouTube description

```text
MEYES is my local-first Windows accessibility prototype for hands-free computer control using an
ordinary webcam, eye gaze, and simple face gestures.

In this real application demo I show:
- local webcam processing and Safe Mode;
- hands-free Smooth Pursuit calibration across nine screen regions;
- explicit confirmation before Windows input is activated;
- real gaze-driven pointer output; and
- a return to Safe Mode.

I used Codex as my engineering collaborator throughout the project. With GPT-5.6, I planned the
architecture, implemented and reviewed state machines, traced lifecycle bugs, generated regression
tests, audited the native Windows SendInput safety boundary, and iterated on the interface and
documentation. I made the final product, accessibility, safety, and evidence decisions.

Repository: https://github.com/drestaputra/meyes

MEYES is an assistive productivity prototype, not a medical device. Camera processing stays on the
device and frames are not intentionally stored or uploaded. This video uses Microsoft Hazel Desktop
synthetic English narration; English captions are included.

#OpenAIBuildWeek #Codex #GPT56 #Accessibility #EyeTracking
```

## Chapters

```text
00:00 What I built
00:12 Ordinary webcam and local processing
00:32 Face and gaze intent
00:53 Smooth Pursuit calibration
01:19 Consent and real Windows pointer output
01:59 Built with Codex and GPT-5.6
02:23 What's next
```

## Publication gate

- [ ] Entrant watches the complete final export with sound.
- [ ] Entrant confirms consent and that no private information is visible.
- [ ] Upload the video to YouTube and set visibility to **Public**.
- [ ] Upload the supplied English SRT if YouTube does not preserve the burned-in caption preference.
- [ ] Open the resulting URL while logged out or in a private window.
- [ ] Paste the exact verified URL into Devpost.

Public upload and the logged-out URL check remain external account actions and must not be marked
complete until performed against the real YouTube URL.

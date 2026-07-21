# MEYES demo voiceover and shot list

Target duration: **2:45 maximum**. The narration below targets approximately **2:35–2:42** at a
calm 135–140 words per minute, leaving a safety margin below the Devpost three-minute limit.

## Recording plan

| Time | What to show | Voiceover |
|---|---|---|
| 0:00–0:13 | MEYES hero, then the application opening in `SAFE MODE` | Hi, I’m Dresta, and I built MEYES: a local-first Windows application that explores hands-free computer control using only an ordinary webcam, eye gaze, and simple face gestures. |
| 0:13–0:34 | Start the camera and open Diagnostics; show live face, eye, hand, temple, and cheek evidence | I was inspired by eye trackers used by professional gamers and streamers, but dedicated hardware can be expensive. I wanted to explore a more accessible alternative that could also support people who find a traditional mouse or keyboard difficult to use. MEYES is an assistive productivity prototype, not a medical device. |
| 0:34–0:57 | Demonstrate wink, temple touch, and cheek detection in Diagnostics while the bottom bar remains in Safe Mode | MediaPipe face and hand landmarks run locally. MEYES converts those observations into deliberate events: winks can trigger clicks, temple gestures can scroll, and cheek touches can be configured as additional actions. Camera frames are not intentionally stored or uploaded. |
| 0:57–1:25 | Run the full-screen Smooth Pursuit flow; show moving target, live progress, accepted result, and activation dialog | For gaze control, I replaced a confusing manual calibration with Smooth Pursuit. I follow one moving target while MEYES captures eye features continuously across nine screen regions. It checks spatial coverage and target-following correlation, fits a robust calibration mapper, and shows the result before any real pointer output is allowed. |
| 1:25–1:50 | Confirm `Activate Live Input`; move the cursor with gaze; show one wink click and bounded temple scroll; trigger emergency shortcut | Live Input is always an explicit choice. After confirmation, the accepted mapper can move the Windows pointer, while the configured gestures handle clicks and scrolling. The emergency shortcut immediately releases every owned input and returns MEYES to Safe Mode. |
| 1:50–2:08 | Show architecture/evidence view, tests, and the persistent Safe/Live boundary | The architecture keeps camera observations, gesture intent, cursor candidates, user consent, and Windows `SendInput` execution in separate layers. That separation helped me test failures safely and prevent camera startup from silently enabling operating-system input. |
| 2:08–2:34 | Show Codex task history, commit history, tests, and code changes | I used Codex as my engineering collaborator throughout the project. With GPT-5.6, I planned the architecture, implemented and reviewed state machines, traced lifecycle bugs, generated regression tests, audited the native Windows safety boundary, and iterated on the interface and documentation. I made the final product, accessibility, safety, and evidence decisions. |
| 2:34–2:44 | Return to the polished MEYES hero and repository link | Next, I want to validate MEYES with more users, webcams, lighting conditions, and accessibility needs. My goal is to make hands-free interaction more affordable using hardware people already own. |

## Full narration

Hi, I’m Dresta, and I built MEYES: a local-first Windows application that explores hands-free
computer control using only an ordinary webcam, eye gaze, and simple face gestures.

I was inspired by eye trackers used by professional gamers and streamers, but dedicated hardware
can be expensive. I wanted to explore a more accessible alternative that could also support people
who find a traditional mouse or keyboard difficult to use. MEYES is an assistive productivity
prototype, not a medical device.

MediaPipe face and hand landmarks run locally. MEYES converts those observations into deliberate
events: winks can trigger clicks, temple gestures can scroll, and cheek touches can be configured
as additional actions. Camera frames are not intentionally stored or uploaded.

For gaze control, I replaced a confusing manual calibration with Smooth Pursuit. I follow one
moving target while MEYES captures eye features continuously across nine screen regions. It checks
spatial coverage and target-following correlation, fits a robust calibration mapper, and shows the
result before any real pointer output is allowed.

Live Input is always an explicit choice. After confirmation, the accepted mapper can move the
Windows pointer, while the configured gestures handle clicks and scrolling. The emergency shortcut
immediately releases every owned input and returns MEYES to Safe Mode.

The architecture keeps camera observations, gesture intent, cursor candidates, user consent, and
Windows `SendInput` execution in separate layers. That separation helped me test failures safely
and prevent camera startup from silently enabling operating-system input.

I used Codex as my engineering collaborator throughout the project. With GPT-5.6, I planned the
architecture, implemented and reviewed state machines, traced lifecycle bugs, generated regression
tests, audited the native Windows safety boundary, and iterated on the interface and documentation.
I made the final product, accessibility, safety, and evidence decisions.

Next, I want to validate MEYES with more users, webcams, lighting conditions, and accessibility
needs. My goal is to make hands-free interaction more affordable using hardware people already own.

## Capture requirements

- Record at 1920×1080 or 1280×720, 30 FPS, with notifications and private applications closed.
- Keep the persistent `SAFE MODE` / `LIVE INPUT` status visible during every transition.
- Do not cut away between calibration acceptance, consent, real pointer output, and emergency stop.
- Use a disposable target for click/scroll demonstrations.
- End the raw capture in Safe Mode with the camera stopped.
- Record the narration in a quiet room as WAV, M4A, or high-quality MP3.
- If using an AI voice instead, disclose it in the YouTube description and retain the English
  subtitles.

## Final publication checklist

- Export below `00:03:00`; target `00:02:44` or shorter.
- Watch the complete export for private information, accidental marks, audio clipping, and claims
  not demonstrated on screen.
- Upload to YouTube as **Public** or another visibility explicitly accepted by the current rules.
- Open the final URL in a private/incognito window while logged out.
- Paste that exact verified URL into Devpost.

from __future__ import annotations

import argparse
import math
import re
import textwrap
import wave
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

WIDTH = 1280
HEIGHT = 720
FPS = 15.0
CANONICAL_DURATION = 164.0
BRAND_BLUE = (255, 96, 28)
NAVY = (52, 32, 10)
MUTED = (122, 99, 76)
PAPER = (250, 248, 245)
GREEN = (79, 128, 0)


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def parse_timestamp(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def load_srt(path: Path) -> list[Cue]:
    blocks = re.split(r"\r?\n\r?\n", path.read_text(encoding="utf-8").strip())
    cues: list[Cue] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        start, end = lines[1].split(" --> ", 1)
        cues.append(Cue(parse_timestamp(start), parse_timestamp(end), " ".join(lines[2:])))
    return cues


def format_timestamp(seconds: float) -> str:
    millis_total = max(0, round(seconds * 1000))
    hours, remainder = divmod(millis_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def write_scaled_srt(path: Path, cues: list[Cue], scale: float) -> None:
    blocks = []
    for index, cue in enumerate(cues, 1):
        blocks.append(
            f"{index}\n{format_timestamp(cue.start * scale)} --> "
            f"{format_timestamp(cue.end * scale)}\n{cue.text}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def wave_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def fit_frame(frame: np.ndarray, size: tuple[int, int] = (WIDTH, HEIGHT)) -> np.ndarray:
    target_w, target_h = size
    h, w = frame.shape[:2]
    scale = min(target_w / w, target_h / h)
    resized = cv2.resize(
        frame, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA
    )
    canvas = np.full((target_h, target_w, 3), PAPER, dtype=np.uint8)
    y = (target_h - resized.shape[0]) // 2
    x = (target_w - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def draw_text(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    *,
    scale: float,
    color: tuple[int, int, int],
    thickness: int = 2,
    max_width: int | None = None,
    line_gap: int = 12,
) -> int:
    x, y = origin
    font = cv2.FONT_HERSHEY_SIMPLEX
    if max_width:
        approximate_chars = max(12, int(max_width / max(8, 18 * scale)))
        lines = textwrap.wrap(text, width=approximate_chars)
    else:
        lines = [text]
    line_height = int(34 * scale) + line_gap
    for line in lines:
        cv2.putText(frame, line, (x, y), font, scale, color, thickness, cv2.LINE_AA)
        y += line_height
    return y


def draw_brand(frame: np.ndarray, label: str) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (WIDTH, 64), (255, 255, 255), -1)
    cv2.addWeighted(overlay, 0.96, frame, 0.04, 0, frame)
    cv2.rectangle(frame, (0, 0), (8, 64), BRAND_BLUE, -1)
    cv2.putText(frame, "MEYES", (28, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.86, NAVY, 2, cv2.LINE_AA)
    cv2.putText(
        frame, label.upper(), (170, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.50, MUTED, 1, cv2.LINE_AA
    )


def draw_subtitle(frame: np.ndarray, cue: Cue | None) -> None:
    if not cue:
        return
    lines = textwrap.wrap(cue.text, width=93)
    box_height = 34 + 31 * len(lines)
    y0 = HEIGHT - box_height - 18
    overlay = frame.copy()
    cv2.rectangle(overlay, (34, y0), (WIDTH - 34, HEIGHT - 18), (12, 12, 12), -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
    y = y0 + 34
    for line in lines:
        size, _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 1)
        x = max(48, (WIDTH - size[0]) // 2)
        cv2.putText(
            frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA
        )
        y += 31


def cue_at(cues: list[Cue], t: float) -> Cue | None:
    return next((cue for cue in cues if cue.start <= t < cue.end), None)


def read_at(capture: cv2.VideoCapture, seconds: float) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds) * 1000)
    ok, frame = capture.read()
    if not ok:
        raise RuntimeError(f"Could not read source frame at {seconds:.2f}s")
    return fit_frame(frame)


def card(title: str, body: list[str], *, accent: tuple[int, int, int] = BRAND_BLUE) -> np.ndarray:
    frame = np.full((HEIGHT, WIDTH, 3), PAPER, dtype=np.uint8)
    cv2.circle(frame, (1080, 118), 132, (239, 231, 218), -1)
    cv2.circle(frame, (1168, 58), 72, accent, -1)
    cv2.rectangle(frame, (86, 132), (96, 566), accent, -1)
    draw_text(
        frame, title, (132, 205), scale=1.42, color=NAVY, thickness=3, max_width=920, line_gap=18
    )
    y = 308
    for item in body:
        cv2.circle(frame, (146, y - 8), 7, accent, -1)
        y = (
            draw_text(
                frame,
                item,
                (172, y),
                scale=0.67,
                color=(68, 54, 40),
                thickness=1,
                max_width=930,
                line_gap=10,
            )
            + 22
        )
    return frame


def title_card(hero: np.ndarray, subtitle: str) -> np.ndarray:
    frame = fit_frame(hero)
    overlay = np.full_like(frame, NAVY)
    cv2.addWeighted(overlay, 0.38, frame, 0.62, 0, frame)
    cv2.rectangle(frame, (68, 112), (724, 518), (255, 255, 255), -1)
    cv2.rectangle(frame, (68, 112), (78, 518), BRAND_BLUE, -1)
    cv2.putText(frame, "MEYES", (116, 214), cv2.FONT_HERSHEY_SIMPLEX, 1.72, NAVY, 4, cv2.LINE_AA)
    draw_text(
        frame,
        "Hands-free Windows control",
        (116, 280),
        scale=0.83,
        color=NAVY,
        thickness=2,
        max_width=550,
    )
    draw_text(
        frame,
        "Eye gaze + simple face gestures + an ordinary webcam",
        (116, 344),
        scale=0.57,
        color=MUTED,
        thickness=1,
        max_width=520,
    )
    cv2.rectangle(frame, (116, 420), (630, 470), BRAND_BLUE, -1)
    cv2.putText(
        frame, subtitle, (138, 453), cv2.FONT_HERSHEY_SIMPLEX, 0.57, (255, 255, 255), 2, cv2.LINE_AA
    )
    return frame


def build_frame(
    t: float,
    *,
    hero: np.ndarray,
    main_capture: cv2.VideoCapture,
    live_capture: cv2.VideoCapture,
) -> tuple[np.ndarray, str]:
    if t < 13:
        return title_card(hero, "LOCAL-FIRST ACCESSIBILITY PROTOTYPE"), "Project overview"
    if t < 34:
        source_t = (t - 13) * (21 / 21)
        return read_at(main_capture, source_t), "Ordinary webcam · local processing"
    if t < 57:
        return card(
            "Face and gaze intent, processed locally",
            [
                "MediaPipe eye, face, and hand landmarks stay on this device.",
                "Winks, temple touches, and optional cheek gestures become deliberate actions.",
                "Camera frames are not intentionally stored or uploaded.",
            ],
            accent=GREEN,
        ), "Privacy-aware perception"
    if t < 85:
        source_t = 32 + (t - 57) * (25 / 28)
        return read_at(
            main_capture, min(57.0, source_t)
        ), "Smooth Pursuit calibration · 9 screen regions"
    if t < 128:
        source_t = 14 + (t - 85) * (46 / 43)
        return read_at(
            live_capture, min(60.0, source_t)
        ), "Explicit consent · real Windows pointer output"
    if t < 154:
        return card(
            "Built with Codex + GPT-5.6",
            [
                "Architecture planning and state-machine implementation",
                "Lifecycle debugging, code review, and regression-test generation",
                "Native Windows SendInput safety-boundary audit",
                "822 automated tests passing in the recorded iteration",
            ],
        ), "Engineering collaboration"
    return title_card(hero, "AFFORDABLE HANDS-FREE INTERACTION"), "What comes next"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose the MEYES Devpost demo visuals.")
    parser.add_argument(
        "--main", type=Path, default=Path("docs/media/demo/meyes-demo-real-raw.mp4")
    )
    parser.add_argument(
        "--live", type=Path, default=Path("docs/media/demo/meyes-demo-live-input-raw.mp4")
    )
    parser.add_argument(
        "--hero", type=Path, default=Path("docs/media/meyes-devpost-hero-final.png")
    )
    parser.add_argument(
        "--audio", type=Path, default=Path("docs/media/demo/meyes-demo-voiceover.wav")
    )
    parser.add_argument(
        "--subtitles", type=Path, default=Path("docs/media/meyes-demo-voiceover-en.srt")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/media/demo/meyes-demo-silent.webm")
    )
    parser.add_argument(
        "--output-subtitles",
        type=Path,
        default=Path("docs/media/demo/meyes-demo-devpost-final-en.srt"),
    )
    args = parser.parse_args()

    cues = load_srt(args.subtitles)
    audio_seconds = wave_duration(args.audio)
    duration = math.ceil(audio_seconds + 1.0)
    if duration >= 178:
        raise RuntimeError(
            f"Narration is too long for a safe sub-three-minute export: {audio_seconds:.2f}s"
        )
    timeline_scale = audio_seconds / CANONICAL_DURATION
    write_scaled_srt(args.output_subtitles, cues, timeline_scale)

    hero = cv2.imread(str(args.hero))
    if hero is None:
        raise RuntimeError(f"Could not read hero image: {args.hero}")
    main_capture = cv2.VideoCapture(str(args.main))
    live_capture = cv2.VideoCapture(str(args.live))
    if not main_capture.isOpened() or not live_capture.isOpened():
        raise RuntimeError("Could not open one or more source recordings")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(args.output), cv2.VideoWriter_fourcc(*"VP80"), FPS, (WIDTH, HEIGHT)
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open the VP8 WebM writer")

    total_frames = math.ceil(duration * FPS)
    try:
        for index in range(total_frames):
            t = index / FPS
            canonical_t = min(CANONICAL_DURATION, t / timeline_scale)
            frame, label = build_frame(
                canonical_t, hero=hero, main_capture=main_capture, live_capture=live_capture
            )
            draw_brand(frame, label)
            draw_subtitle(frame, cue_at(cues, canonical_t))
            writer.write(frame)
            if index % int(FPS * 10) == 0:
                print(f"Rendered {t:6.1f}s / {duration:.1f}s", flush=True)
    finally:
        writer.release()
        main_capture.release()
        live_capture.release()

    print(f"Visual export: {args.output.resolve()}")
    print(f"Timed subtitles: {args.output_subtitles.resolve()}")
    print(f"Duration: {duration:.2f}s; narration: {audio_seconds:.2f}s")


if __name__ == "__main__":
    main()

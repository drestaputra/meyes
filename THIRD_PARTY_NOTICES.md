# Third-party notices

This file records the primary third-party components relevant to the MEYES source build and Python
wheel. Exact resolved Python versions and hashes are locked in [`uv.lock`](./uv.lock). The wheel
bundles this notice, the Apache-2.0 text, model provenance, and the two verified MediaPipe task
bundles. A future standalone executable must repeat the license audit for every bundled transitive
component.

## Hallmark design methodology

- Project: [nutlope/hallmark](https://github.com/nutlope/hallmark)
- License: MIT
- Use in MEYES: methodology and review reference only.

MEYES does not copy Hallmark source code, generated pages, screenshots, or assets. The link in [`DESIGN.md`](./DESIGN.md) documents the requested design reference and the independent PySide6 interpretation.

## Google MediaPipe

- Project: [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe)
- Python package license: Apache License 2.0
- MediaPipe Solution API terms: [Google MediaPipe Terms of Service](https://developers.google.com/edge/mediapipe/legal/tos)
- License text supplied with this repository: [`LICENSES/Apache-2.0.txt`](./LICENSES/Apache-2.0.txt)

MEYES uses the MediaPipe Tasks API locally. Google states that input media is processed on-device and is not sent to Google servers. The same terms state that the Solution APIs may periodically contact Google for fixes, updated models, and accelerator compatibility information and may send usage, performance, application, and system metrics. This boundary is also disclosed in [`PRIVACY.md`](./PRIVACY.md).

### Face Landmarker model bundle

- Bundle: [official `face_landmarker.task`](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task)
- Components: BlazeFace detector, FaceMesh landmark model, and face blendshape model.
- Official model cards:
  - [BlazeFace short-range model card](https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20(Short%20Range).pdf)
  - [FaceMesh V2 model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf)
  - [Face Blendshape V2 model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf)
- License identified by each official model card: Apache License 2.0.
- Local integrity: 3,758,596 bytes; SHA-256 `64184E229B263107BC2B804C6625DB1341FF2BB731874B0BCC2FE6544E0BC9FF`.

### Hand Landmarker model bundle

- Bundle: [official `hand_landmarker.task`](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)
- Components: palm detector and hand landmark tracker.
- Official model card: [MediaPipe Hands Lite/Full](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20(Lite_Full)%20with%20Fairness%20Oct%202021.pdf)
- License identified by the official model card: Apache License 2.0.
- Local integrity: 7,819,105 bytes; SHA-256 `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1`.

The official documentation pages and model cards were rechecked on 2026-07-19. Bundle provenance and automated checksum coverage are detailed in [`resources/models/README.md`](./resources/models/README.md).

## Primary Python runtime dependencies

| Component | Purpose | Upstream license |
|---|---|---|
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) | Native Windows UI | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only in installed package metadata |
| [`opencv-contrib-python`](https://github.com/opencv/opencv-python) | Camera capture and color conversion | Apache License 2.0 |
| [NumPy](https://numpy.org/) | Numeric arrays | Composite BSD-3-Clause, 0BSD, MIT, Zlib, and CC0 metadata in the installed distribution |
| [Pydantic](https://github.com/pydantic/pydantic) | Validated configuration | MIT |
| [platformdirs](https://github.com/tox-dev/platformdirs) | Windows-appropriate data paths | MIT |

The current deliverable is source code installed through `uv`; it does not redistribute a PySide6/Qt executable bundle. Before shipping a binary, MEYES must include the applicable Qt notices and LGPL compliance materials, audit all resolved transitive packages, and preserve every required license and source-offer obligation.

## No runtime OpenAI component

GPT-5.6 and Codex were development tools for this Build Week project. They are not linked, embedded, or called by the MEYES runtime, and the application does not require an OpenAI API key.

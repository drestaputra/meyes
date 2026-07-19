# Vision model assets

The source submission includes the official task bundles below. Their official component
model cards identify Apache License 2.0, the repository supplies the Apache-2.0 text, and
automated tests verify the exact local sizes and SHA-256 digests. See
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) for the complete source-build audit.

## `face_landmarker.task`

- Source: [Google MediaPipe Face Landmarker, float16/latest](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task)
- Official documentation: [Face Landmarker models](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/index#models)
- Downloaded: 2026-07-19
- Size: 3,758,596 bytes
- SHA-256: `64184E229B263107BC2B804C6625DB1341FF2BB731874B0BCC2FE6544E0BC9FF`
- Runtime use: local face landmarks and face blendshapes.
- Components and official model cards:
  - [BlazeFace short-range detector](https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20(Short%20Range).pdf)
  - [FaceMesh V2](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf)
  - [Face Blendshape V2](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf)
- License identified in each component model card: Apache License 2.0.

The source-submission redistribution review was completed on 2026-07-19. A future packaged
binary must repeat the audit for every bundled runtime and transitive component.

## `hand_landmarker.task`

- Source: [Google MediaPipe Hand Landmarker, float16/1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)
- Official documentation: [Hand Landmarker models](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/index#models)
- Downloaded: 2026-07-19
- Size: 7,819,105 bytes
- SHA-256: `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1`
- Runtime use: local anatomical handedness and 21 normalized landmarks for up to two hands.
- Components: palm detector and hand landmark tracker.
- Official model card: [MediaPipe Hands Lite/Full](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20(Lite_Full)%20with%20Fairness%20Oct%202021.pdf)
- License identified in the component model card: Apache License 2.0.

The model is loaded from disk at runtime and its size and digest are covered by an automated integrity test.

## Processing and network disclosure

MEYES does not implement a camera-frame upload path. The current [MediaPipe Solution API
Terms](https://developers.google.com/edge/mediapipe/legal/tos) state that input media is
processed on-device and is not sent to Google servers. They also state that Solution APIs
may periodically contact Google for fixes, model updates, and hardware-accelerator
compatibility information and may send non-input usage, performance, application, and
system metrics. See [`PRIVACY.md`](../../PRIVACY.md) for the runtime boundary.

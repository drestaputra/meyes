# MEYES Native UI Design System

> **Implementation boundary:** This is the target design system for the planned MVP. The
> current Build Week build implements the native shell, camera dashboard, and Safe Mode
> diagnostics; several other views remain placeholders and operating-system input is
> disconnected. See [`README.md`](./README.md) and [`JUDGES.md`](./JUDGES.md) for the exact
> runnable scope.

Status: initial design baseline  
Applies to: PySide6 desktop application  
Reference methodology: [nutlope/hallmark](https://github.com/nutlope/hallmark)  
Design direction: **calm control room**

## 1. Context lock

The current product specification supplies enough context to establish the initial design direction:

- **Audience:** Windows users who need or prefer hands-free pointer control, plus a helper who may assist during setup.
- **Primary job:** reach a safe, calibrated “tracking active” state and understand immediately whether gaze, eyes, hands, and camera are working.
- **Tone:** utilitarian, calm, technical, and humane.
- **Genre:** modern-minimal adapted to a native accessibility application.
- **Trust model:** local processing, visible state, reversible actions, and no invented accuracy claims.

This is not a pixel copy of Hallmark examples. Hallmark provides the anti-generic design discipline; MEYES owns its native information architecture and visual identity.

## 2. Experience principles

### Safety is the visual hierarchy

Tracking state, pause/resume, camera health, and the emergency shortcut must be visible before secondary settings. “Active” must never be communicated by color alone.

### One screen, one job

- Dashboard: understand and control live tracking.
- Calibration: complete a guided gaze calibration.
- Bindings: map gestures to actions.
- Sensitivity: tune thresholds with explanations and safe defaults.
- Camera: select and validate capture input.
- Profiles: manage configuration sets.
- Diagnostics: inspect observations and events without injecting input.
- Privacy: understand what stays local and what can be recorded only by opt-in.

### Prefer a control surface over card soup

The dashboard uses one dominant live workspace with a narrow status rail. Do not turn every metric into a floating rounded card. Related values share a panel and alignment grid.

### State must be explicit

Use icon, label, value, and where useful a short remedy:

```text
Camera — Not found
Choose another camera or reconnect the device.
```

Avoid ambiguous green/red dots with no text.

### Honest copy

Do not claim accuracy, latency, privacy certification, medical suitability, or user counts unless verified. Use measured values with context or label them as unavailable.

## 3. Application macrostructure

### Main shell

```text
┌─────────────────────────────────────────────────────────────────────┐
│ MEYES    Profile: Default        TRACKING PAUSED      Resume [F6]  │
├──────────────┬───────────────────────────────────┬──────────────────┤
│ Dashboard    │                                   │ Camera   Ready   │
│ Calibration  │       Live camera workspace       │ Face     Found   │
│ Bindings     │       / current primary task      │ Left eye Ready   │
│ Sensitivity  │                                   │ Right eye Ready  │
│ Camera       │                                   │ Hands    —       │
│ Profiles     ├───────────────────────────────────┤                  │
│ Diagnostics  │ Recent event / guidance strip     │ Safe mode On     │
│ Privacy      │                                   │                  │
├──────────────┴───────────────────────────────────┴──────────────────┤
│ Ctrl + Alt + F12 pauses tracking immediately · Processing is local │
└─────────────────────────────────────────────────────────────────────┘
```

Rules:

- Persistent top command bar contains product, active profile, textual tracking status, and the primary pause/resume action.
- Left navigation stays stable across settings pages.
- Center workspace receives visual priority.
- Right status rail is present on live-tracking pages and may collapse on narrower windows.
- Bottom safety strip always exposes the emergency shortcut while tracking is active.
- Minimum supported content size is planned around 1024×720; layouts must also be checked at 125% and 150% Windows scaling.

### Dashboard

- Camera preview is the dominant region.
- Preview overlay is sparse: face guide, optional landmarks, and a clear safe-mode/tracking label.
- Live health values use aligned rows, not separate cards.
- Primary action changes between `Start tracking`, `Pause tracking`, and `Resume tracking`.
- Metrics such as FPS are secondary and never compete with safety status.

### Calibration

- Calibration switches to a distraction-free full-screen flow.
- One instruction and one target are shown at a time.
- Progress is visible as `Point 3 of 9` plus a visual map.
- Escape always cancels safely; cancellation never leaves live input enabled.
- Validation results describe quality in plain language and offer a clear retry path.

### Bindings

- Use a dense but readable table: Gesture, Current action, Parameters, Test, Reset.
- Tap and hold are distinct rows.
- Recording a shortcut visibly enters a temporary capture mode and never triggers the captured action.
- Unsupported values use inline error text with a corrective suggestion.

### Sensitivity

- Group settings by Eyes, Temple gestures, Cursor, and Scrolling.
- Show human-readable values beside sliders.
- Explain consequences such as “lower is easier to trigger and may increase false positives.”
- Provide `Restore safe defaults` at the group level.

### Diagnostics

- Use a restrained technical layout: aligned numeric readings, confidence bars, event timeline, and worker health.
- Diagnostics starts in no-input safe mode.
- Raw camera recording is absent unless a separate explicit opt-in is enabled.

## 4. Token system

PySide6 QSS does not provide CSS custom properties. Define tokens once in Python, expose typed theme roles, and generate QSS from those roles. No widget may introduce an ad hoc color or font family.

### Color roles — light baseline

| Token | Value | Use |
|---|---:|---|
| `canvas` | `#F5F7FA` | Application background |
| `surface` | `#FFFFFF` | Main working panels |
| `surface_subtle` | `#EDF1F5` | Grouped rows and quiet regions |
| `preview` | `#0C111B` | Camera/visualization backdrop |
| `ink` | `#172033` | Primary text |
| `ink_muted` | `#526079` | Secondary text |
| `border` | `#CBD4E1` | Dividers and controls |
| `accent` | `#1F5EFF` | Primary actions and selection |
| `accent_hover` | `#1748C8` | Hover/pressed emphasis |
| `focus` | `#005FCC` | Keyboard focus ring |
| `success` | `#197447` | Ready/healthy state with text/icon |
| `warning` | `#8A5A00` | Degraded or attention state |
| `danger` | `#B42318` | Failure and destructive actions |

Color rules:

- Status colors always appear with an icon or label.
- Large preview overlays use high-contrast text with an opaque or near-opaque backing.
- Custom QSS must not prevent Windows high-contrast behavior; provide a high-contrast token adapter rather than forcing the default palette.
- Gradients are not part of the baseline system.

### Typography roles

| Role | Font | Guidance |
|---|---|---|
| UI/body | `Segoe UI Variable`, fallback `Segoe UI` | Native, readable, familiar |
| Numeric/diagnostic | `Cascadia Mono`, fallback `Consolas` | FPS, timestamps, thresholds, event codes |
| Display | UI/body family at a stronger weight | No decorative display face in the MVP |

Rules:

- Use Windows point sizing and test at system text scaling.
- Headings remain upright; emphasis uses weight, color, or spacing, not italic display text.
- Avoid all-caps paragraphs. Short state labels may use sentence case or compact title case.
- Prefer tabular numerals for live metrics when supported.

### Spacing and shape

- Spacing scale: 4, 8, 12, 16, 24, 32, and 48 px equivalents.
- Control height: at least 36 px; primary and safety actions target 44 px where practical.
- Radius: 4 px for fields, 8 px for panels, 12 px only for dominant surfaces.
- Pills are reserved for compact status or mode labels, never for ordinary buttons and containers.
- Dividers and whitespace establish groups before shadows. Shadows are subtle and rare.

## 5. Component behavior

Every interactive component must define applicable states:

1. default;
2. hover;
3. keyboard focus;
4. pressed/active;
5. disabled;
6. loading or pending;
7. error;
8. success or confirmed.

Native controls should retain semantic roles and keyboard behavior. A custom visual treatment must not remove:

- visible focus;
- tab order;
- accessible name and description;
- shortcut discoverability;
- disabled-state clarity;
- sufficient target size.

### Primary controls

- Only one primary action per task region.
- Pause is always visually prominent while tracking is active.
- Destructive actions such as profile deletion use explicit wording and confirmation.
- Icon-only controls require tooltips and accessible names; critical actions also require text.

### Feedback

- Inline feedback is preferred for field errors.
- A non-blocking banner communicates recoverable camera/config warnings.
- Modal dialogs are reserved for destructive confirmation or failures that prevent progress.
- Toasts must not be the sole carrier of critical state.

## 6. Motion and responsiveness

- Motion is restrained and functional: 120–180 ms for hover, selection, and panel transitions.
- Continuous decorative animation is prohibited.
- Tracking indicators may pulse only when this materially clarifies active capture, and must respect reduced-motion preferences.
- Window resizing must preserve the primary action and safety status before secondary metrics.
- At narrower widths, the right status rail collapses into an expandable status panel; it must not disappear silently.

## 7. Content voice

Use short, direct, reassuring language without hiding problems.

Preferred:

- `Tracking paused`
- `Camera not found`
- `No input will be sent while Safe mode is on`
- `Move closer until your full face is inside the guide`
- `Calibration quality is low. Try again with steadier lighting.`

Avoid:

- `Something went wrong`
- `AI-powered precision`
- `Perfect hands-free control`
- technical exception strings without a user action;
- blaming the user for low-confidence observations.

## 8. Accessibility checklist

- Full keyboard operation and logical tab order.
- Visible focus on every interactive element.
- No state communicated by color alone.
- Scalable text and layout at Windows 100%, 125%, and 150% scaling.
- High-contrast mode verification.
- Labels remain visible; placeholders are not labels.
- Touch/click targets remain comfortably sized.
- Preview overlays do not obscure critical instructions.
- Emergency pause works independently of the current page.
- Setup and diagnostics default to no-input safe mode.

## 9. Hallmark-inspired review gate

Before a UI phase is accepted, score it from 1–5 on:

- Philosophy: does safety and user control lead the design?
- Hierarchy: is the current state and next action obvious?
- Execution: do states, focus, scaling, and error recovery work?
- Specificity: does the screen feel designed for gaze control rather than a generic settings app?
- Restraint: have unnecessary decoration, cards, pills, and motion been removed?
- Variety: do different workflows use structures appropriate to their job while staying in one system?

Any score below 3 requires revision before handoff.

## 10. Initial design deliverables

The implementation phase should produce and visually verify, in order:

1. application shell with top safety bar and left navigation;
2. camera dashboard in disconnected, ready, active, paused, and error states;
3. setup wizard camera step;
4. calibration target screen;
5. bindings table and shortcut capture state;
6. sensitivity groups with keyboard-operable controls;
7. diagnostics safe-mode view;
8. tray menu and shutdown confirmation behavior.

No visual direction is considered complete from code inspection alone. Each major screen must be rendered at the target window sizes and Windows scaling levels before acceptance.

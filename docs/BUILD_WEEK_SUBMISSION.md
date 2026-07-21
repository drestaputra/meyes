# OpenAI Build Week submission record

Last verified against the official Hackathon Website and Official Rules: 2026-07-21.

This is a readiness and evidence record, not a substitute for the [Official
Rules](https://openai.devpost.com/rules). The Official Rules, the [Hackathon
Website](https://openai.devpost.com/), and organizer [updates](https://openai.devpost.com/updates)
control if any summary here differs from them. The entrant must recheck those sources before
submitting because the Rules may change.

## Dates and current state

- Submission period: July 13, 2026 at 09:00 Pacific Time through **July 21, 2026
  at 17:00 Pacific Time**.
- UTC+7 deadline: **July 22, 2026 at 07:00**.
- The authenticated Devpost account was already registered when checked on 2026-07-19.
- Devpost project `1342722` exists in `submission_pre_draft` state and is still named
  `Untitled`. It has not been edited or submitted by this repository workflow.
- The recommended category is **Apps for Your Life**. The human entrant must confirm the
  final category in Devpost.
- The Git remote is `https://github.com/drestaputra/meyes.git`. Treat it as private until
  public visibility or both required judge invitations have been verified.

The Official Rules list judging as July 22 through August 5, 2026 and winners on or around
August 12. Devpost's machine-readable dates currently show a later judging end date; the
Official Rules are treated as controlling.

The 2026-07-21 recheck confirmed the same four categories, required working project and text
description, public YouTube demo shorter than three minutes with audio covering both the project
and Codex/GPT-5.6 use, judge-accessible repository, README collaboration account, `/feedback`
Session ID, English-or-translated materials, and free judging access through the judging period.

## Truthful submission scope

The current runnable build is a Windows-first, local vision diagnostics application. It:

- presents a three-step first-run privacy/camera/Safe Mode orientation without starting capture or
  native output, and records completion only after explicit acknowledgement plus durable save;
- conditionally exposes system-tray Show, Pause/Resume, Return to Safe Mode, and Quit actions when
  the desktop supports them, without changing full main-window shutdown semantics;
- captures an ordinary webcam through OpenCV;
- exposes requested capture size/rate/mirroring and live health in a dedicated Camera view, while
  keeping device selection, preview, and lifecycle controls on Dashboard;
- runs independent local MediaPipe face and hand landmark pipelines;
- reports normalized eye openness and semantic left/right wink events;
- pairs fresh face and hand observations and reports aspect-correct,
  face-width-normalized fingertip-to-temple distances;
- stabilizes independent left/right Near/Far/Unknown proximity states with hysteresis and an
  independent tracking-loss timeout;
- classifies independent semantic temple tap, hold-start, and hold-end events with cooldown,
  capture-time ordering, and lifecycle-safe hold termination;
- validates a closed action vocabulary and complete logical binding profiles, and exercises
  them through a synchronous fake-only dispatcher with fail-safe release behavior;
- connects semantic events to a Qt-owned fake trace and, only while explicitly armed, a separate
  Windows `SendInput` dispatcher using the same validated binding rules;
- provides a durable local profile catalog with all-disabled creation, pause-first activation,
  preference rollback, and a read-only preview of all six simulated bindings;
- provides an isolated binding draft editor for the complete validated action vocabulary, with
  inline correction, last-valid preview, and save-as-copy that never activates runtime input;
- protects active and built-in profiles while allowing inactive profile rename,
  exact-name-confirmed recoverable deletion, and restore from the built-in Default bindings;
- imports bounded, complete profile JSON only as a new inactive snapshot and exports selected
  profiles through exclusive creation or atomically confirmed replacement without runtime change;
- derives a fail-closed binocular iris-to-eye feature, expires it with the tracking watchdog, and
  labels it in Diagnostics as uncalibrated rather than claiming cursor coordinates;
- provides a distraction-free primary-display nine-point collection flow with normalized target
  placement, Space/Enter/R/Escape controls, bounded volatile samples, quality/replay rejection,
  robust per-target median/MAD filtering, and fail-safe presentation-close cancellation;
- fits a volatile replaceable quadratic mapper after complete user collection, with fail-closed
  numerical guards and visible deterministic per-target holdout metrics, without automatically
  accepting or activating its output;
- evaluates a mapper only when a complete four-limit acceptance policy is explicitly configured,
  otherwise reports `Review Required`; the submission claims no universal accuracy threshold;
- provides a configurable One Euro 2D filter with deterministic jitter, rapid-step,
  timestamp-order, independent-axis, reset, and stale-gap tests in the candidate pipeline;
- provides a validated Sensitivity view that releases Live Input before persisting One Euro and
  temple-gate settings, then rebuilds only a still-valid accepted cursor pipeline;
- provides a physical-pixel primary-screen mapper with explicit clamping and boundary tests;
- reads primary-monitor physical bounds through a temporary restored Windows Per-Monitor V2 DPI
  scope;
- captures non-overwriting read-only display evidence for native geometry, system DPI, Qt logical
  geometry/DPR, and consistency; the 100% row is committed and 125%/150% remain pending;
- constructs the production executor-independent candidate pipeline only from proof-carrying accepted
  calibration plus validated geometry, applies configured smoothing/gate values, and tears it down
  on acceptance loss or native failure;
- stores only an accepted mapper's coefficients, exact acceptance policy, and holdout evidence in a
  versioned, checksummed local envelope with UTC creation time and physical display geometry;
- retains an existing envelope when a new fit is accepted and requires exact-phrase confirmation
  plus successful Live Input release before atomically replacing it;
- recovers accepted calibration once at SAFE startup under the exact stored policy and can configure
  only cursor candidates when current display geometry also matches; consent and Live Input arming
  are never restored;
- offers an exact-phrase calibration-forget control that clears cursor provisioning and moves the
  envelope to a recoverable timestamped backup without changing Live Input state;
- shows only newest deleted-backup timestamp/size metadata and requires a second exact phrase before
  checksum, policy, display, provisioning, and rollback-gated restore;
- permanently deletes only the exact newest cataloged backup after a separate exact phrase and
  path/link/type/size revalidation, without changing active calibration or Live Input state;
- provides a fail-closed cursor gate for overlapping temple holds, tap pulses, tracking suspension,
  and delayed resume;
- composes accepted calibration, smoothing, screen mapping, and gating in an executor-independent
  pipeline, then forwards candidates only through the explicitly armed Live Input boundary;
- wires a Qt-owned cursor diagnostics controller to freshness and lifecycle signals and routes
  accepted, display-matched pixels to absolute primary-monitor `SendInput` only while armed,
  revalidating current geometry against the exact provisioned display before every movement;
- exposes a dedicated Live Input view requiring volatile exact-phrase consent, successful global
  hotkey registration, a clear physical-input preflight, and release-first initialization;
- releases and gates native output on the emergency shortcut, user disarm, camera pause/stop/fault,
  profile transition, backend fault, page destruction, and application shutdown;
- exposes health, latency, freshness, observations, dispatcher state, and a bounded fake
  primitive trace through a native PySide6 Safe Mode UI;
- starts every application session with operating-system input disconnected and never persists
  Live Input consent.

The current build does **not** provide evidence-backed default calibration limits, broad
physical-device reach validation, bulk calibration-backup cleanup, a packaged installer, a medical
assessment, or a remote OpenAI-powered runtime. Those capabilities must not appear in the video or
description as completed functionality.

## Requirement audit

| Official requirement | MEYES evidence | Status |
|---|---|---|
| Build a working project with Codex and GPT-5.6 | Codex collaboration is documented in `README.md`; explicit GPT-5.6 work begins with commit `57e08f2`. | Implementation evidence present; required Session ID pending |
| Fit one category | Hands-free personal-computing exploration fits Apps for Your Life. | Human confirmation required |
| Run as depicted on the stated platform | Source build and deterministic checks run on Windows; a fresh clone passed locked sync/import/full gate on the same Windows 11 host. | Second-machine/clean-user live check pending |
| New work during the submission period | Git history begins on 2026-07-19 and remains unsquashed; the timeline through `57e08f2` is below and later evidence remains in `git log`. | Evidence ready; human originality attestation required |
| Explain features and functionality | Current scope and exclusions are recorded above; an English draft is in [`DEVPOST_DRAFT.md`](./DEVPOST_DRAFT.md). | Human review/edit pending |
| Public YouTube demo under three minutes | Must show the working build and include audio explaining the project, Codex, and GPT-5.6. | Pending |
| Repository available to judges | Public with a relevant license, or private and shared with `testing@devpost.com` and `build-week-event@openai.com`. | Pending external verification |
| README setup and collaboration story | Setup, run, verification, Codex acceleration, human decisions, and GPT-5.6 evidence are present. | Ready |
| `/feedback` Session ID | Must identify the project thread where most core functionality was built. | Pending human retrieval |
| Free, unrestricted judging access | Source setup requires no paid service, API key, or proprietary hardware beyond a Windows PC and webcam. Access must remain free and unrestricted through the official judging period. | Repo access, clean setup, and retention pending |
| English submission materials | Repository submission guides are English. The description, video/audio, and testing instructions must be English or include English translations. | External materials pending |
| Authorized third-party use | MIT project license, Apache-2.0 text, MediaPipe model-card evidence, checksums, and dependency notices are recorded. | Documentation ready; human rights attestation required |
| No unauthorized demo content | Video must not contain unlicensed music, third-party marks, private information, or people recorded without consent. | Pending video review |
| Submission finalized before deadline | Devpost must show submitted, not draft, before 17:00 PT on July 21. Material cannot normally be changed afterward. | Pending |

MEYES is not a plugin or developer tool, so the optional plugin/developer-tool installation
field is not required. The source quickstart still gives judges a complete testing path.

## Live Devpost form inventory

The authenticated submission form inventory below was last checked on 2026-07-19; the public
requirements and Official Rules were rechecked on 2026-07-21. The human entrant must re-open the
authenticated form before submission. Its previously observed custom fields are:

| Field | Required | MEYES status |
|---|---:|---|
| Submitter Type: Individual, Team of Individuals, or Organization | Yes | Human answer pending |
| Country of Residence | Yes | Human answer and Rules eligibility check pending |
| Category | Yes | Apps for Your Life recommended; human confirmation pending |
| Public or private code-repository URL | Yes | URL known; visibility/invitations pending |
| Judge test link and necessary instructions | No | `JUDGES.md` ready; decide whether to paste it |
| `/feedback` Session ID for the primary project task | Yes | Pending |
| Plugin/developer-tool installation and testing details | No | Not applicable to MEYES |

The country dropdown contains general platform values that are not proof of eligibility;
the entrant must independently satisfy Section 3 of the Official Rules. The global Devpost
project must also have a human-approved name, tagline, description, Built With list, and
required video URL before it is submittable. A website and zip upload are not required by the
current form.

## Build-period evidence through `57e08f2`

All times below are commit author times in UTC+7. History is preserved without squashing or
rewriting.

| Commit | Time | Evidence |
|---|---:|---|
| `4a7574c` | 2026-07-19 18:54 | Initial repository and planning baseline |
| `51b9250` | 2026-07-19 19:12 | Typed Python/Qt repository foundation |
| `f2ed617` | 2026-07-19 19:20 | Camera capture core and deterministic lifecycle |
| `a6bc5e5` | 2026-07-19 19:31 | Native camera dashboard |
| `1de97e3` | 2026-07-19 19:43 | Face observation pipeline |
| `27953f5` | 2026-07-19 19:49 | Wink gesture state machine |
| `2b544c7` | 2026-07-19 20:00 | Safe Mode diagnostics |
| `9844b38` | 2026-07-19 20:07 | Normalized hand observations |
| `48c8264` | 2026-07-19 20:22 | Lower-cadence hand worker |
| `09b4201` | 2026-07-19 20:35 | Normalized temple proximity features |
| `57e08f2` | 2026-07-19 21:05 | Live face/hand composition and first recorded post-switch GPT-5.6 iteration |

The human entrant should preserve the relevant Codex task and record its `/feedback` Session
ID. The commit history supports timing but does not replace the entrant's representations
about authorship, eligibility, rights, or tool use.

Subsequent readiness and implementation commits remain visible in `git log` and the dated
records under `docs/changelog/`; the table is an implementation baseline, not a frozen final
commit list.

## Codex, GPT-5.6, and human decisions

Codex was used throughout the repository for planning, implementation, tests, concurrency
review, native visual QA, physical smoke testing, and documentation. GPT-5.6 was explicitly
selected before the live face/hand composition iteration in `57e08f2` and is also being used
for subsequent Build Week readiness and implementation work.

Human decisions include the MEYES name, local-first architecture, Safe Mode boundary,
gesture vocabulary, Hallmark-inspired review direction, phase acceptance criteria, and the
policy of verifying, committing, and pushing every completed iteration. The human entrant
must understand and approve the submitted code and must rewrite or edit the final Devpost
description in their own voice rather than submitting AI-generated copy unchanged.

## Judging alignment

| Equally weighted criterion | Evidence to demonstrate |
|---|---|
| Technological Implementation | Typed adapters, latest-only buffers, lifecycle generation gates, Qt-thread serialization, independent model cadence, eye-local binocular gaze features, bounded nine-point sample collection with robust outlier rejection, a rank/condition-guarded quadratic mapper with holdout metrics, hysteretic proximity and semantic tap/hold state machines, fail-closed durable profiles, pause-first profile transitions with rollback, bounded duplicate-key-safe profile transfer, a typed isolated binding-draft codec, parallel fake/live action dispatch, an owned-state `SendInput` backend, exact-consent/hotkey/physical-preflight safety gates, freshness watchdogs, deterministic race tests, and an unsquashed Codex collaboration record. |
| Design | A coherent native Windows information architecture, readable Safe Mode diagnostics, a responsive profile catalog, an inline-validating six-binding editor and preview, accessible labels/focus behavior, aspect-correct preview, explicit error states, and independent Hallmark-inspired design tokens. |
| Potential Impact | A concrete exploration of ordinary-webcam hands-free interaction for people who want alternative personal-computing input; the demo must present this as a product direction, not a medical claim. |
| Quality of the Idea | Independent face and hand signals are composed into same-side, scale-normalized temple states and tap/hold intent events while real OS output stays behind an explicit, volatile safety boundary. |

Stage One is pass/fail for theme fit and required-technology use. Stage Two uses the four
criteria above equally; Technological Implementation is the first tie-breaker.

## Human and external submission gate

The following items cannot be inferred or completed safely from repository code alone:

- [ ] Confirm every entrant is at least the age of majority where they reside, or otherwise
  qualifies exactly as stated in the Official Rules.
- [ ] Confirm residence/domicile is supported and not prohibited by local or United States
  law; review every exclusion in Section 3 of the Official Rules.
- [ ] Confirm no promotion-entity, judge, employee/agent, immediate-family, household,
  affiliate, financial-support, or real/apparent conflict makes the entrant ineligible.
- [ ] If entering as a team or organization, appoint the authorized representative and make
  sure every teammate accepts the Devpost invitation before the deadline.
- [ ] Confirm the entrant owns the submission and has permission for every dependency,
  model, image, voice, mark, and person appearing in submitted materials.
- [ ] Confirm **Apps for Your Life** as the final category.
- [ ] Complete the required submitter-type and country fields with the entrant's actual
  information; do not infer them from the repository or system time zone.
- [ ] Rename and complete Devpost project `1342722`; keep the description in the entrant's
  own voice.
- [ ] Record the `/feedback` Codex Session ID from the primary build task.
- [ ] Run the judge quickstart on a clean Windows 10/11 x64 environment.
- [ ] Either make the repository public with `LICENSE`, or share the private repository with
  both required judge email addresses and verify access.
- [ ] Record a clear YouTube demo shorter than 3:00 that is publicly visible by link, with
  audio covering the product, Codex, and GPT-5.6. The [July 18 organizer
  update](https://openai.devpost.com/updates/45371-tuesday-last-minute-tips) says Unlisted is
  acceptable; verify the final interpretation and link in an incognito/private session.
- [ ] Open the video and repository/test path in an incognito/private session.
- [ ] Keep the repository, video, and testing path free and accessible until the judging
  period ends. The current Official Rules say August 5, 2026 at 17:00 PT; recheck for changes
  and retain access through any later official judging end.
- [ ] Recheck the Official Rules, Updates, submission fields, and deadline immediately before
  submitting; save the final confirmation time.
- [ ] Verify Devpost says **Submitted**, not Draft, before the deadline.

Submitting constitutes agreement to the Official Rules and incorporated Devpost terms. It
also carries representations about eligibility, ownership, conflicts, releases, publicity,
privacy, dispute resolution, tax/prize obligations, and the sponsor's limited judging and
promotion rights. The human entrant must read and accept those legal terms directly.

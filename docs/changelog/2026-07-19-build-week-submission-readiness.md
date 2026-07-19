# 2026-07-19 — OpenAI Build Week submission readiness

## Summary

Audited MEYES against the OpenAI Build Week Official Rules, live submission requirements,
judging criteria, dates, and organizer updates. Added a source-build evidence package without
editing or submitting the external Devpost project.

## Added

- MIT project license and full Apache License 2.0 text.
- Primary dependency, Hallmark methodology, MediaPipe package, and model notices.
- Official component model-card links, bundle sizes, and SHA-256 evidence.
- Build Week submission record with deadline conversion, commit timeline, requirement audit,
  judging alignment, and human/external gates.
- Judge source quickstart, deterministic verification path, expected live flow, current scope,
  troubleshooting, and repository-access requirements.
- Precise privacy record for in-memory frames and landmarks, local configuration, rotating
  logs, MediaPipe network caveat, OpenAI development-only boundary, and manual deletion.
- Urgent Build Week checklist in `docs/TODO.md`.
- Roadmap warnings in `MEYES_CODEX_SPEC.md` and `DESIGN.md` so intended-MVP product and UI
  copy cannot be confused with the runnable Safe Mode build.

## Changed

- Replaced mouse-control claims in README and package metadata with the working local vision
  diagnostics scope.
- Separated Codex use across the repository from explicit GPT-5.6 evidence beginning at
  commit `57e08f2`.
- Changed “repository began” to the narrower, auditable claim that Git history begins during
  the submission period.
- Replaced absolute model/network language with the disclosure in Google's current
  MediaPipe Solution API terms.
- Marked Windows 10/11 as target compatibility and recorded the actual Windows 11 x64 QA
  environment separately.

## Compliance evidence reviewed

- Official Rules, overview, submission fields, dates, judging criteria, and all organizer
  announcements were rechecked on 2026-07-19.
- Registration was already active; Devpost project `1342722` remained an unsubmitted
  `submission_pre_draft` named `Untitled`.
- The complete Git history starts on 2026-07-19 and contains the first explicit post-switch
  GPT-5.6 implementation commit `57e08f2`.
- Official FaceMesh, Blendshape, BlazeFace, and Hands model-card license pages were extracted
  and visually reviewed; each identified Apache License 2.0.
- Included model files matched their recorded official URLs, byte sizes, and SHA-256 digests.
- Installed primary dependency license metadata was reviewed; a future packaged executable
  still requires a complete Qt and transitive redistribution audit.

## Verification

```powershell
.\scripts\check.ps1
```

Measured results:

- Ruff formatting: passed, 58 files checked.
- Ruff lint: passed.
- mypy strict: passed, 58 source files checked.
- pytest: 93 passed in 6.59 seconds.
- Frozen `uv.lock` sync: passed with `python -m uv sync --frozen --group dev`.
- Local Markdown-link audit: passed across 24 Markdown files.
- New readiness documents: no trailing whitespace.
- Git diff whitespace check: passed.

## Remaining human and external gates

- Entrant eligibility, residence, conflicts, originality, rights, representative status, and
  copyright-holder name must be confirmed by the human entrant.
- Submitter type, country, category selection, project rename, human-edited description,
  `/feedback` Session ID, team invitations, and final submission remain pending.
- Repository public visibility or both judge invitations must be verified.
- A publicly visible-by-link YouTube demo under three minutes with required audio must be
  recorded and checked in an incognito session. The [July 18 organizer
  update](https://openai.devpost.com/updates/45371-tuesday-last-minute-tips) says Unlisted is
  acceptable, but the final Rules/Updates interpretation must be rechecked.
- Repository, video, and free testing access must remain available through the official
  judging end (currently August 5, 2026 at 17:00 PT under the Rules).
- A clean Windows setup should be tested before the submission scope is frozen.
- The Rules and Updates must be rechecked immediately before final submission.

## Next task

Continue Phase 3 with a pure, independently timed temple-proximity hysteresis state machine.
Keep its Near/Far/Unknown diagnostics in Safe Mode and do not emit tap, hold, mouse, keyboard,
or scrolling actions in that iteration.

# Windows display evidence

This folder contains read-only display observations captured on the native Windows host. A record
is evidence for only the configuration named in that file; it is not evidence for other scaling
values or physical pointer reach.

Capture a new configuration after a human changes and confirms Windows display scaling:

```powershell
.\scripts\capture_display_evidence.ps1 `
  -OutputPath docs\evidence\display\YYYY-MM-DD-SCALE-percent.json
```

The command refuses to replace an existing file. A consistent record should show:

- the intended `reported_scale_percent` and `system_dpi`;
- `qt_dpr_matches_reported_scale: true`;
- `qt_scaled_size_matches_native: true`;
- physical geometry matching the display used for calibration and pointer QA.

The probe does not change DPI awareness, display scaling, resolution, calibration, or Live Input.

## Matrix

| Windows scale | Evidence | Status |
|---|---|---|
| 100% | `2026-07-21-100-percent.json` | Captured; geometry and Qt consistency passed |
| 125% | — | Pending human display configuration and capture |
| 150% | — | Pending human display configuration and capture |

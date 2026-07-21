# MEYES icon

`meyes.svg` is the original repository-native vector asset for the MEYES window and system tray.
It uses the locked `accent`, `surface`, and `ink` roles from `DESIGN.md`; it does not copy Hallmark
code or artwork. The asset is distributed under the repository's MIT license.

- Size: 524 bytes
- SHA-256: `ba44e15e0eacf011dbcbf978364cf8f64d2a8d93d477810de54efa86417508a8`

`meyes.ico` is a deterministic Windows delivery derivative containing PNG frames at 16, 20, 24,
32, 40, 48, 64, 96, 128, and 256 physical pixels.

- Size: 19,906 bytes
- SHA-256: `64f9ad51118096b8103b8c2cefc7931d3fc4d196e92d59c70968ac8d9a8b48a9`

The SVG remains the source of truth. Run `scripts/verify_icon_assets.ps1` to reproduce the expected
ICO in memory and compare it byte-for-byte. Updating the derivative requires the explicit
`python -m uv run --frozen python scripts/generate_icon_assets.py --write` command. A selected
Windows delivery must still wire the ICO and verify shell/taskbar appearance; MSIX-specific image
assets are not claimed.

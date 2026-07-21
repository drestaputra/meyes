# 2026-07-21 - Windows signing requirements

## Summary

Documented the fail-closed signing boundary for a future packaged Windows delivery without claiming
that the current wheel is signed or standalone.

## Decisions captured

- Signing depends on the still-open packager and distribution-channel decision.
- The current wheel retains checksum/integrity evidence and explicitly reports signing as not
  configured; Authenticode is not applicable to the ZIP archive.
- Future production requirements cover trusted publisher identity, current Smart App Control RSA
  compatibility, SHA-256 digests, RFC 3161 timestamping, private-key isolation, post-sign hashing,
  signature verification, clean-machine validation, and downloaded-byte parity.
- Self-signed certificates are limited to controlled local testing.
- Users must never be told to disable Windows security controls to run a release.

## Sources and verification

- Reviewed current official Microsoft code-signing options, MSIX signing/certificate requirements,
  SignTool behavior, and Smart App Control signing/testing guidance on 2026-07-21.
- Checked every local and official documentation link.
- No key, certificate, signing-service account, package, or Windows trust setting was created or
  changed.

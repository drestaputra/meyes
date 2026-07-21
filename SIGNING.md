# MEYES Windows signing requirements

Status: requirements only - no signing certificate, standalone executable, installer, MSIX, or
automated signing pipeline is configured. The current release builder produces a Python wheel and
records signing as not configured. Authenticode is not applicable to that ZIP-based wheel.

Last reviewed against official Microsoft documentation: 2026-07-21.

## Distribution decision comes first

The maintainer must select the Windows package format and distribution channel before implementing
signing:

| Delivery | Signing requirement for MEYES |
|---|---|
| Current Python wheel | Retain SHA-256, exact revision, installed-asset verification, and explicit `code_signing.configured=false`. Do not report Authenticode success or imply a standalone app. |
| Microsoft Store MSIX | Submit through Partner Center and rely on Store signing after certification. The publisher identity/manifest still needs to be correct. |
| Direct-download MSIX | Sign the package with a certificate that is trusted on the target device. Microsoft states that MSIX packages must be signed to deploy. |
| Direct-download EXE/MSI | Authenticode-sign the application binaries, installer/bootstrapper, and uninstaller with a trusted production code-signing identity. |
| Local development package | A self-signed certificate is acceptable only for controlled testing where the tester explicitly trusts it. Never describe this as public production trust. |

Microsoft currently recommends Store distribution for most new Windows apps and Azure Artifact
Signing (formerly Trusted Signing) for non-Store distribution, subject to its current eligibility.
An OV certificate from a trusted CA is the documented alternative. See Microsoft's
[code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
and [MSIX signing overview](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview).

This repository does not choose a provider, purchase a certificate, accept provider terms, create a
publisher identity, or enroll in Partner Center. Those are explicit human/owner decisions.

## Certificate and algorithm baseline

For a future production build:

- use a code-signing certificate whose chain is trusted by the intended Windows distribution path;
- use an RSA-based certificate while targeting Smart App Control, because Microsoft currently says
  its signature check does not support ECC signatures;
- require the Code Signing enhanced key usage where the selected provider/tooling exposes it;
- use SHA-256 as the file digest and SHA-256 for the RFC 3161 timestamp digest;
- timestamp during signing, and fail the release if a required timestamp cannot be obtained;
- keep the publisher subject consistent with the selected package manifest and product identity.

References: [Smart App Control signing](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control),
[SignTool options](https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe), and
[MSIX certificate requirements](https://learn.microsoft.com/en-us/windows/msix/package/create-certificate-package-signing).

## Private-key handling

- Never commit a PFX, private key, certificate password, access token, or signing-service credential.
- Prefer a managed signing service, hardware-backed key, or protected CI identity over an exported
  private key.
- Grant signing access only to the release job and authorized maintainers; development and pull
  request builds must not receive production signing authority.
- Prevent secrets and full signing responses from entering build logs or release manifests.
- Document revocation, renewal, account recovery, and emergency key-compromise ownership before the
  first public signed release.
- Retain only public certificate metadata needed for audit: subject, issuer, serial/thumbprint,
  validity window, signature digest, timestamp authority/result, and artifact hashes.

## Future release order

Signing changes artifact bytes, so the required order is:

1. require a clean exact revision matching the intended remote branch;
2. run the frozen judge gate and package/install diagnostics;
3. build the selected executable/package into a new non-overwriting directory;
4. enumerate the exact executable, DLL, installer/bootstrapper, and uninstaller targets;
5. sign each required target through the approved identity and RFC 3161 timestamp service;
6. verify every embedded/package signature and timestamp under the intended Windows policy;
7. perform clean-machine install, launch, Safe Mode, uninstall, and Smart App Control checks;
8. compute final SHA-256 values only after signing;
9. write a manifest that binds final hashes to Git revision, version, signer public metadata,
   verification results, and any limitations;
10. publish only the exact verified bytes, then independently download and re-verify them.

For a selected EXE/MSI delivery, the automated verification gate should use the Windows SDK
SignTool and treat every nonzero result as failure. A representative verification command is:

```powershell
signtool verify /pa /all /v path\to\artifact.exe
```

The exact sign command must be supplied by the chosen provider and must not expose a password on the
command line. Microsoft documents explicit `/fd SHA256`, `/tr`, and `/td SHA256` requirements for
SignTool and recommends timestamping. See the official
[SignTool reference](https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe).

## Fail-closed release policy

A future signing workflow must stop and leave the candidate unpublished when:

- the expected target list is empty, incomplete, duplicated, or contains an unexpected binary;
- a certificate is expired, revoked, untrusted for the target policy, wrong-publisher, or missing
  required usage;
- signing or timestamping reports a warning/error, or any required signature cannot be verified;
- a signed target changes before hashing/publication;
- a clean-machine installation or launch requires disabling Windows security controls;
- the downloaded artifact differs from the published manifest.

Do not instruct users to disable Smart App Control, antivirus, signature enforcement, or certificate
validation as a workaround. Microsoft's Smart App Control guidance explains that unknown unsigned
code may be blocked and recommends testing all app binaries and code paths; signing does not itself
guarantee immediate reputation. See the official [Smart App Control overview](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview)
and [signature testing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control).

## Remaining implementation decisions

- Select and measure Nuitka versus `pyside6-deploy`, then choose EXE/MSI/MSIX delivery.
- Confirm the legal publisher identity and target distribution countries.
- Choose Store, Azure Artifact Signing, or a suitable trusted CA based on owner eligibility and cost.
- Define the complete binary target inventory produced by the selected packager.
- Add credential-isolated signing and verification automation.
- Record clean-machine, install/uninstall, Smart App Control, and downloaded-artifact evidence.

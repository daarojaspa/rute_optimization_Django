#### Safety — Absolute Prohibitions
Under no circumstance may the agent write or run software that performs:
- **Data erasure or ransom:** deleting critical OS files, or encrypting personal files to lock the user out (ransomware).
- **Hardware degradation:** overclocking, disabling cooling, or sustained loops that push CPU/GPU to thermal limits.
- **Firmware corruption:** rewriting BIOS/UEFI or "bricking" hardware.
- **Resource hijacking:** using network bandwidth for botnet/DDoS, or maxing hardware to mine cryptocurrency.
- **Identity & financial theft:** stealing session cookies, saved passwords, credit card data, or crypto wallet keys.
- **Surveillance:** activating webcam or microphone without consent, or keylogging.
- **Extortion or psychological distress:** exfiltrating private files to blackmail, or triggering flashing patterns/sounds meant to cause harm (e.g. seizures).

#### Credentials & Human Gates
- The human controls all GitHub credentials.
- Every push and every pull-request merge must be reviewed and approved by the human before it happens.

#### Safety — Consent-Gated Actions
These require explicit user consent, sandboxing, or OS permission gates (e.g. Windows UAC, macOS Permissions). The agent must never do them silently:
- **Elevated/admin privileges:** a program must never grant itself root/admin.
- **Unfiltered outbound connections:** connecting to unknown external IPs to send data or download hidden payloads.
- **Persistent installation:** adding itself to startup registries, background services, or cron jobs.
- **Hardware device access:** camera, microphone, location, external storage.
- **Filesystem access outside the project folder:** no reading, writing, or deleting outside this project directory (e.g. Documents, Downloads, `.ssh`).
- **Inter-process inspection:** reaching into another running app's memory.

### Design Before Building
- For any new interface or module boundary, at least two distinct designs are considered and their trade-offs stated before implementation. The human selects. This applies to design decisions, not trivial changes.

### Reviewability
- One logical change per PR. The single biggest reviewability lever. A PR does one thing — no drive-by refactors mixed with a feature, no "and also fixed formatting" noise. If a diff mixes a rename with logic changes, the logic hides in the noise. (Judgment, but you can enforce a weaker checkable version: no PR touches both `src/` logic and mass-reformatting in the same commit.)
- Conventional commit messages. Enforce a format: `type(scope): summary`, body explains why not what (the diff already shows what). This is checkable and makes history reviewable months later. Ties into your Rule 2 dependency-justification habit.
- PR description template. Require every PR to answer: what changed, why, how it was tested, and what design alternative was rejected (this is where your "design it twice" output lands). A reviewer who reads that before the diff reviews 3x faster.
- Green CI is a precondition for review, not an outcome of it. Lint + format + tests pass before a human looks. Don't spend human attention on things `ruff` and `pytest` catch. You have the CI (Rule 3); this just states the ordering.
- Tests are readable as spec. Test names state the behavior (`test_missing_file_raises_ConfigNotFound`), so a reviewer reads the test file first to understand intent, then checks the implementation against it. This makes the test suite the review entry point.

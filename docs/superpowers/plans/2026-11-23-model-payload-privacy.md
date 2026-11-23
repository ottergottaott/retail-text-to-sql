# Model payload privacy implementation plan

Approved scope: preserve stored Trio fields and values; sanitize copies on model egress.

- Add a local spaCy PERSON detector and rules for contact details, street addresses,
  postal codes, exact coordinates and raw customer IDs. Preserve aggregate geography.
  Keep stable customer pseudonyms with the configured secret. Fail closed when the
  detector cannot load; no network fallback or runtime model downloads.
- Exercise sanitization before both generation/review and embedding transports.
  Cover question, report, SQL literals and nested history/tool context. Preserve
  structure, source storage and idempotence; version embedding keys after change.
- Verify with local real-detector and mocked-transport tests. No provider calls.
- Update architecture Markdown/HTML with both outbound boundaries and detector
  limitations. Move the existing WebUI screenshot directly below the README intro.

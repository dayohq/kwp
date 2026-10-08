# Security design backlog

These are future design tasks, not implemented capabilities.

## Optional encrypted financial-account identifiers

Packet 6B preserves optional last_four and stores no full financial-account identifier. A full identifier is not required for ledger/accounting correctness or account creation.

A later design may support an optional encrypted identifier plus scheme/type and useful country/jurisdiction metadata. Examples include Nigerian NUBAN, IBAN, wallet identifiers and other local schemes. Identifiers can be alphanumeric; do not impose Nigeria's ten-digit numeric format globally. Scheme-specific validation and metadata must remain optional where appropriate.

Before adding storage:

- Choose a maintained encryption-at-rest mechanism and threat model; no custom/fake encryption or plaintext account_number/account_identifier convenience field.
- Design encryption-key provisioning, storage/access, separation from ciphertext, rotation, backup/restore and failure behavior before accepting full identifiers. Encryption/key management is a security architecture decision, not a display formatter.
- Define safe masking separately. Displaying ******1234 is not encryption of the stored value.
- Preserve last_four for current low-risk recognition; its four-ASCII-digit format is not the future full identifier format.
- Keep identifiers optional and independent from posting/balance correctness.
- Never log full identifiers or unnecessarily return them through APIs. Review permissions, admin visibility, serializers, exports and retention before exposure.

No secure encrypted field mechanism currently exists in KWP. No encryption, keys, full identifier storage, scheme/country columns or identifier API is introduced by Packet 6B.

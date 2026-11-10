"""Consent to processing health data (152-FZ art. 10; docs/texts.md, section 5).

The evidence hash covers what the person was shown: the policy version, the checkbox label and
the policy text, `SHA-256(UTF-8(version + "\\n" + label + "\\n") + bytes(docs/policy.md))`. It is
the same for everyone who accepted a version, so it is fixed here per version; a unit test
recomputes it from docs/ and fails when the label or the policy changes.
"""

POLICY_VERSION = "2026-11-10"
EVIDENCE_SHA256 = bytes.fromhex("c524b77751cffb2204d28fa4eb47656577f9afa7963787df90568335cca8c23a")

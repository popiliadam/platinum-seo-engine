# Release Notes — v2.1.4 (2026-10-02)

**Theme:** *Same fix, second surface.* The secret scanner no longer mistakes an `sk-`
inside a word for an API key, so writes carrying a long `task-…` id are not blocked —
and it now catches the `sk-proj-` / `sk-ant-` key shapes it used to miss.

## Why this release exists

1. **Writes carrying a task id were blocked.** v2.1.3 gave `events_writer`'s `sk-`
   redaction a left word boundary and listed the canonical scanner as having the same
   root cause. That scanner (`scripts/security/check_secrets.sh`) is what the
   PreToolUse secret hook (`scripts/hooks/scan_pending_secret.py`) and CI step 6 call.
   Its `openai_or_anthropic_sk_prefix` pattern had no left boundary, so `task-` followed
   by 20+ letters/digits was flagged (rc=1) and the hook blocked the write. While
   v2.1.3 was being prepared, one command was blocked this way. Replaying that command
   through the new scanner, it is no longer flagged.
2. **Two real key shapes were not caught at all.** The scanner's `sk-` body was
   alphanumeric-only, so `sk-proj-…` and `sk-ant-…` keys (whose bodies contain `-` and
   `_`) never matched. The event redactor already redacted them; the scanner, the hook
   and CI did not. `rules/secrets-management.md` describes them as caught.

## Changes

- **Left boundary + key-shape branch for `sk-`** (`3fa692d`): `sk-` must now be preceded
  by line start, a non-alphanumeric byte, a JSON-escaped `\n` / `\r` / `\t`, or a
  URL-encoded byte (`%3D`). The escaped and encoded cases keep recall on keys that
  appear inside escaped or encoded text. A second branch matches
  `sk-proj-` / `sk-ant-` followed by 20+ `[A-Za-z0-9_-]`. This is still one class:
  same label, no other class changed, so CI, the hook and the redactor parity
  tripwire all keep their 17-label set.
- **Tests** (+57, written first, 38 red against the previous pattern):
  - `tests/scripts/test_check_secrets.py`: in-word ids (`task-`, `disk-`, `risk-`,
    digit-prefixed, `-proj-` / `-ant-` variants) are clean. Each of the 3 key shapes is
    flagged in 14 contexts: line start, space, tab, newline, `=`, both quote styles,
    `:`, `(`, `_`, `/`, escaped `\n` / `\t`, `%3D`. A real key on the same line as a
    task id is still flagged, and full-tree mode (the CI path) behaves the same way.
  - `tests/hooks/test_scan_pending_secret.py`: hook end-to-end. A task id in a Write
    or a Bash heredoc is allowed (exit 0). A `sk-`, `sk-proj-` or `sk-ant-` key in a
    Bash heredoc is blocked (exit 2), and the matched value is never echoed.

## Replay

The previous and new scanners were run in `--scan-stdin` mode over 59,838 real Bash
commands from the last 45 days. 2,027 commands contain `sk-`, but none carries a run
of 20+ characters after it (the longest is 14). Both scanners flag 0, so neither the
boundary nor the new branch changes a verdict on that corpus. The one command
actually blocked during v2.1.3 preparation (`task-` followed by 30 alphanumerics) is
flagged by the previous scanner and clean under the new one.

## Known failures

None at release time. With the workspace bound (2026-10-02): 3657 passed, 0 failed,
35 skipped. The skips are live SF/GSC fixtures that are absent, the opt-in smoke
test, `CLIENT_SLUG_PATTERN` unset, and version-sync waiting for the tag.

## Not measured by the gate

- GNU grep: the pattern is POSIX ERE and was exercised with macOS BSD grep. CI's
  Ubuntu runner uses GNU grep and was not run locally.
- Other `sk-` key families (for example `sk-svcacct-`, `sk-admin-`) have no branch.
  The redactor's broader `sk-[A-Za-z0-9_-]{20,}` still redacts them in events. The
  scanner, the hook and CI do not flag them.
- The event redactor treats only a non-alphanumeric byte as a boundary. Its values are
  decoded strings, so an escaped `\n` cannot occur there. A URL-encoded `%3Dsk-…` value
  is still not redacted.
- An `sk-` key glued directly to a letter or digit (for example `xsk-…`) is no longer
  flagged by design. That is the same trade-off the redactor made in v2.1.3.

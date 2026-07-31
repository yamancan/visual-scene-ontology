# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | Yes                |
| 1.0.x   | No — upgrade to 1.1 |

Only the latest 1.1 patch line receives fixes. There are no backports.

## Reporting a vulnerability

Report privately — please do not open a public issue for an unfixed
vulnerability.

- **Email:** yamancandev@gmail.com
- **GitHub:** if private vulnerability reporting is enabled on this repository,
  the "Report a vulnerability" button under the Security tab works too.

Useful things to include: affected component (ontology/SHACL shapes, the Rust
`vson` CLI, the Python tooling, or the web studio), version or commit, and the
smallest input that reproduces the issue.

## What to expect

This project is maintained by one person on a best-effort basis. There is no
paid on-call rotation and no guaranteed response SLA. Realistically: an
acknowledgement within about a week, and a fix timeline that depends on
severity and on how much of the stack the issue touches. If a week passes with
no reply, a follow-up email is welcome.

Fixes are released as a new 1.1.x patch, with the issue described in
`spec/CHANGELOG.md` once a fix is public. Credit is given to the reporter
unless anonymity is requested.

## Scope notes

- The web studio proxies extraction requests to OpenRouter using a server-side
  key (`OPENROUTER_API_KEY`, see `web/src/lib/server/openrouter.ts`). Anything
  that could leak that key, or let a visitor spend it in ways the deployment
  did not intend, is in scope.
- Untrusted VSON/VSON-X input parsed by the CLI or the Python tooling is in
  scope (crashes, unbounded resource use, path traversal).
- The ontology and shapes themselves are static data; findings there are
  usually correctness bugs rather than vulnerabilities — a normal issue is
  fine for those.

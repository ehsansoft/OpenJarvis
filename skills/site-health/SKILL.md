---
name: site-health
description: Read-only HTTP health checks — status, redirects, mixed content, headers, meta, sitemap — for local sites and user-approved public URLs.
version: 0.1.0
author: Ehsan OpenJarvis
---

# Site Health

Bounded, read-only HTTP checks producing a health report. No logins, no form
submissions, no writes, no aggressive scanners or fingerprinting.

## Scope

- Default: local WAMP vhosts and local dev servers.
- Public sites: only the URLs the reviewer lists for that specific run; keep
  request rates trivial (sequential, ≤ 1 req/s, honor robots).

## Checks (per URL set)

1. HTTP status + redirect chain: hop count, final target, HSTS after the first
   hop.
2. Mixed content: any `http://` subresources on `https://` pages.
3. Response headers (informational): HSTS, CSP, X-Frame-Options /
   frame-ancestors, Referrer-Policy.
4. Meta essentials: title length, meta description presence/length, canonical,
   robots meta; `sitemap.xml` / `robots.txt` presence.
5. Optional homepage link-target statuses (depth 0) unless the run config sets
   `links: { depth: N }`.

## Outputs

- `D:\AI-Control\OpenJarvis\support\site-health\<date>-<site>\health.json`
- `reports\<date>-health-<site>.md` — table of URLs × checks with pass/warn/fail
  (warn and fail clearly separated), ending with at most 3 prioritized fixes.

Instruction-only workspace procedure. No executable resources or additional authority.

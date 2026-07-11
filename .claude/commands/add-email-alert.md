---
description: Add an email alert with visitor IP and location when the landing page is opened
argument-hint: [recipient-email]
allowed-tools: Read, Edit, Write, Bash
---

Add a feature to this web application that sends an email alert to $ARGUMENTS whenever the landing page is opened/visited, including visitor IP address and approximate location.

Requirements:

1. Detect the tech stack first (check requirements.txt / pyproject.toml, package.json, .csproj, etc.) and match existing patterns in the codebase.
2. Trigger point: fire the alert server-side, on the landing page's route/view/handler — not client-side only.
3. Capture visitor data server-side:
   - IP address: get the real client IP, not the load balancer's — check `X-Forwarded-For` / `X-Real-IP` headers first (common behind reverse proxies like Nginx, Cloudflare, or cloud load balancers), falling back to the raw connection IP.
   - Location: resolve IP → city/country using an IP geolocation service. Ask me which provider I want (e.g. ip-api.com, ipinfo.io, MaxMind GeoLite2 for an offline/local option) before adding a new dependency or external call — this affects both privacy and rate limits.
   - Also capture timestamp and user-agent.
4. Privacy: note that IP-based geolocation is only approximate (usually city-level, not exact address), and that storing/emailing IP + location data may have privacy/legal implications (e.g. GDPR if EU visitors) — flag this to me rather than silently proceeding if the project looks like it could have EU users.
5. Make the whole thing non-blocking:
   - Flask/Django: use a background thread or task queue (Celery) so the geolocation API call and email send don't delay the page response.
   - FastAPI: use `BackgroundTasks`.
6. Add rate-limiting/debouncing (e.g. max 1 email per IP per X minutes) so it doesn't spam the inbox on repeated visits or crawlers — ask me for my preferred throttle window if not obvious.
7. Store secrets (SMTP credentials, geolocation API keys) in environment variables / existing config, never hardcoded.
8. Show me the diff before finishing, and briefly summarize what was added.

If anything is ambiguous given the current codebase (framework, existing email setup, whether a geolocation service is already in use), stop and ask me rather than guessing.

# Browser end-to-end check

Drives a freshly generated app through register → verify email → dashboard → profile update →
validation errors → logout → wrong password → login, with Playwright. Not part of `pytest`.

```bash
uv run aso new /tmp/e2eapp --dev          # from this repo
cd /tmp/e2eapp && npm run build && uv run aso serve --port 8766 &
cd tests/e2e && npm i playwright
APP_URL=http://127.0.0.1:8766 APP_DB=/tmp/e2eapp/database/database.sqlite node browser.mjs
```

Set `CHROME=/usr/bin/chromium` to use a system browser instead of Playwright's download.
Last run (2026-10-16): 10/10.

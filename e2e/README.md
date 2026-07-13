# Gridar E2E (Playwright)

End-to-end tests that run against the **live production** app (gridar.app) with a
dedicated test account. Isolated from the (legacy Vite) root package.json.

## Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

Create `.env` (gitignored) with the test-account credentials:

```
E2E_BASE_URL=https://gridar.app
E2E_API_URL=https://api.gridar.app
E2E_EMAIL=tokamdarius+e2e@gmail.com
E2E_PASSWORD=<the e2e_admin password>
```

The `e2e_admin` account is a superuser on the `agency` plan, provisioned on prod
via `railway ssh` (see the session notes). Recreate/reset it with a Django shell
script if needed.

## Run

```bash
npx playwright test                 # everything
npx playwright test --project=public    # no-auth flows only
npx playwright test --project=dashboard # authenticated flows (runs auth setup first)
npx playwright show-report          # open the last HTML report
```

## Structure

- `tests/auth.setup.ts` - logs in through the real UI, saves the cookie storage
  state (`.auth/user.json`) + the sessionStorage access token (`.auth/token.txt`).
- `tests/fixtures.ts` - re-injects the sessionStorage token (Playwright's
  storageState does not persist sessionStorage).
- `tests/lib/state.ts` - shares the created test site id across specs.
- `tests/public/*.spec.ts` - marketing, public audit + lead capture, landings.
- `tests/dashboard/*.spec.ts` - auth, site CRUD, navigation smoke of all pages,
  keywords, AI generation, billing, logout. File-number prefixes enforce order.

## Guardrails (prod target)

- Billing tests let the backend create a Stripe session but **abort the redirect**
  so no payment page is ever completed.
- AI generation runs **once** per full suite.
- Test data (site, tracked keyword, captured lead) lands in the test account and
  the `tokamdarius+...` inbox. Clean up the test site to remove it.

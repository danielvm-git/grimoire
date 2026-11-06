# CI v3 Ops Preflight — danielvm-git/grimoire

Status as of 2026-07-24.

| Check | Status | Notes |
|-------|--------|-------|
| `production` GitHub Environment | **Y** | Created on fork (`id` 18719689579, 2026-07-24T23:30:15Z). Required by v3 `deploy.yml`. |
| Secrets present | **Y** | `BIGBASE_DEPLOY_TOKEN`, `BIGBASE_SITE_ID`, `BIGBASE_SITE_URL` all configured (names verified via `gh secret list`). |
| Deploy key rotation | **N — blocked (human)** | No BigBase admin CLI on this machine; cannot rotate safely without live console/API auth. |

## Human steps: rotate `BIGBASE_DEPLOY_TOKEN`

After [bigbase#161](https://github.com/danielvm-git/bigbase/issues/161) / [bigbase#162](https://github.com/danielvm-git/bigbase/issues/162) site-key ownership fix is deployed:

1. Open **BigBase Console** → site **grimoire** (`https://grimoire.bigbase.click`).
2. **Deploy Keys** tab (e74 self-service) — or `POST /api/sites/{BIGBASE_SITE_ID}/deploy-keys` with a session/API key that is **not** a `bb_dep_*` token.
3. **Revoke** the old deploy key (if still listed).
4. **Create** a new deploy key; copy the raw `bb_dep_*` token once (shown only at creation).
5. Update fork secret:
   ```bash
   gh secret set BIGBASE_DEPLOY_TOKEN --repo danielvm-git/grimoire
   ```
6. Confirm `BIGBASE_SITE_URL` is `https://grimoire.bigbase.click` and `BIGBASE_SITE_ID` matches the site.
7. After Track B merges to `main`, verify a green **Deploy** workflow run (closes #5).

## Verify after rotation + CI v3 merge

```bash
gh run list --repo danielvm-git/grimoire --workflow deploy.yml --limit 3
```

Expect `conclusion: success` on `main` after **Test Build Release** completes.

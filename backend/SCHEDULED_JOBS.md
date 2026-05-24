# Scheduled Jobs

Gridar has several recurring background jobs implemented as Django management
commands. They are scheduled via **Railway native cron services** (1 service
per command), not Celery, GitHub Actions, or APScheduler.

## Why Railway cron?

- Already in the deployment platform; no new infra
- Each cron service shares the same repo + Dockerfile - just a different start command
- Overlap-skip semantics: if a previous run is still going, the next tick is skipped (not killed) - exactly what we want for multi-minute autopilot generations
- Billed only for actual runtime + minimal idle (~$1-3/svc/mo)
- Per-run logs visible in Railway UI

## The 4 scheduled jobs

| Command | Cadence | Purpose |
|---|---|---|
| `python manage.py run_autopilot` | `0 * * * *` (hourly) | Generate 1 draft article per due site |
| `python manage.py rank_snapshot` | `0 6 * * *` (daily 6am UTC) | Pull SERP positions via Serper for all tracked keywords |
| `python manage.py publish_scheduled` | `*/15 * * * *` (every 15 min) | Flip status=scheduled -> published when scheduled_at <= now |
| `python manage.py send_lead_sequence` | `0 14 * * 1` (Mondays 2pm UTC) | Weekly nurture emails to leads captured via /audit |

All cron expressions are in **UTC**. Adjust for America/Toronto when defining if needed.

## One-time setup per job (Railway UI)

1. Railway dashboard > project `gridar` > **+ New** > **Empty Service** OR **Service from Repo**
2. Connect to the same `TokDar2410621/blog-dashboard` repo (the backend Dockerfile / Procfile is reused)
3. Settings > **Cron Schedule**: paste the cron expression (e.g. `0 * * * *`)
4. Settings > **Start Command**: override with `python manage.py <command>` (e.g. `python manage.py run_autopilot`)
5. Variables: link/copy the same env vars as the web service (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `SERPER_API_KEY`, `VOYAGE_API_KEY`, etc.)
6. **IMPORTANT**: in Service Settings, make sure the service is **not** exposing a public domain (cron services don't serve HTTP).
7. Deploy. First run fires at the next matching minute.

Repeat for each of the 4 commands.

## Verifying a cron job

- Railway UI > the cron service > Deployments tab > shows each run with its logs
- For autopilot, also check the Site's "Dernier run autopilote" field in the dashboard (Parametres > Autopilote tab)
- For rank_snapshot, check Suivi des positions - new snapshots dated today

## Adding a new scheduled job

1. Write a new `backend/sites_mgmt/management/commands/<name>.py` (subclass `BaseCommand`)
2. Test locally with `python manage.py <name>` and any flags
3. Spin up a new Railway cron service as above
4. Add an entry to this table

## Cost ballpark

4 cron services on Railway Hobby/Pro: ~$5-15/month total. Each service idles cheaply (no web traffic, no always-on workers); compute is billed only during the few seconds-to-minutes the cron actually runs.

## Why not Celery?

Tried/considered. For our scale (~4 jobs, low frequency, no fan-out) Celery + Redis would be:
- Heavier ops (broker downtime = silent job loss)
- 2-3x more expensive (Redis addon + worker service + beat service)
- More failure modes to debug

If we ever need fan-out (e.g. autopilot tick spawning 50 parallel generations), the upgrade path is `django-q2` with a Postgres broker - **not** Celery.

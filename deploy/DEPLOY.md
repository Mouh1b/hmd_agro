# HMD Agro — Deployment

Production deploy on top of [`frappe_docker`](https://github.com/frappe/frappe_docker) (vanilla upstream).

## Requirements

- Docker + Docker Compose
- Public domain pointing to the server (for SSL)
- Ports 80 / 443 open
- ~4 GB RAM minimum

## Deploy

```bash
# 1. Clone the official toolkit + this repo
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
git clone https://github.com/hmdbackup/ERPnext /tmp/hmd_agro

# 2. Overlay HMD-specific files
cp /tmp/hmd_agro/deploy/apps.json /tmp/hmd_agro/deploy/.env.hmd /tmp/hmd_agro/deploy/build-hmd.sh .
chmod +x build-hmd.sh

# 3. Build the custom image
./build-hmd.sh

# 4. Configure environment — edit DB_PASSWORD, LETSENCRYPT_EMAIL, SITES_RULE
cp .env.hmd .env
$EDITOR .env

# 5. Launch
docker compose --env-file .env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  -f overrides/compose.backup-cron.yaml up -d

# 6. Create the site (name must match SITES_RULE in .env)
docker compose exec backend bench new-site hmd.agro \
  --mariadb-user-host-login-scope=% \
  --db-root-password "$DB_PASSWORD" \
  --admin-password CHANGE_ME \
  --install-app erpnext
docker compose exec backend bench --site hmd.agro install-app hmd_agro
```

Change the `Administrator` password at first login.

## Updates

**App code** — push to `hmdbackup/ERPnext` main, then:

```bash
./build-hmd.sh
docker compose --env-file .env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  -f overrides/compose.backup-cron.yaml up -d
docker compose exec backend bench --site hmd.agro migrate
```

**Frappe/ERPNext version** — edit `ERPNEXT_VERSION` in `.env`, same 2 commands above.

**frappe_docker infrastructure** — `cd frappe_docker && git pull && docker compose pull && docker compose up -d`.

## Backups

Every 6 h via ofelia (see `overrides/compose.backup-cron.yaml`). Stored in the `sites` volume under `sites/hmd.agro/private/backups`. For disaster recovery, sync off-host:

```bash
docker compose cp backend:/home/frappe/frappe-bench/sites/hmd.agro/private/backups ./backups
# Manual one-off:
docker compose exec backend bench --site hmd.agro backup --with-files
```

## Notes

- `.env` is not committed. Only `.env.hmd` (template) is tracked.
- `apps.json` pulls hmd_agro from `hmdbackup/ERPnext`. If the repo is private, pass a GitHub token as a build arg (see frappe_docker docs).
- Architecture details, volumes list, full env variable reference: see [`frappe_docker/docs/`](https://github.com/frappe/frappe_docker/tree/main/docs).

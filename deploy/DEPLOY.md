# HMD Agro — Deployment

Production deploy on top of [`frappe_docker`](https://github.com/frappe/frappe_docker) (vanilla upstream).
Works on Linux, macOS, and Windows (via Git Bash, WSL, or PowerShell with Git for Windows installed).

## Requirements

- Docker + Docker Compose
- Public domain pointing to the server (for SSL)
- Ports 80 / 443 open
- ~4 GB RAM minimum

## Deploy

```bash
# 1. Clone both repos as siblings
git clone https://github.com/frappe/frappe_docker
git clone -b sprint4 https://github.com/Mouh1b/hmd_agro hmd_agro
cd frappe_docker

# 2. Overlay HMD-specific files
cp ../hmd_agro/deploy/apps.json ../hmd_agro/deploy/.env.hmd ../hmd_agro/deploy/build-hmd.sh .

# 3. Build the custom image (bash works on every OS — Git for Windows ships it)
bash build-hmd.sh

# 4. Configure environment
cp .env.hmd .env
# Open .env in your editor and set:
#   DB_PASSWORD, LETSENCRYPT_EMAIL, SITES_RULE

# 5. Launch the stack (COMPOSE_FILE is read from .env automatically)
docker compose --env-file .env up -d

# 6. Create the site (replace YOUR_DB_PASSWORD with the value from .env)
docker compose exec backend bench new-site hmd.agro \
  --mariadb-user-host-login-scope=% \
  --db-root-password YOUR_DB_PASSWORD \
  --admin-password CHANGE_ME \
  --install-app erpnext
docker compose exec backend bench --site hmd.agro install-app hmd_agro
```

Change the `Administrator` password at first login.

## Updates

**App code** — push to `Mouh1b/hmd_agro` (sprint4 branch as set in `apps.json`), then on the server:

```bash
bash build-hmd.sh
docker compose --env-file .env up -d
docker compose exec backend bench --site hmd.agro migrate
```

**Frappe / ERPNext version** — edit `ERPNEXT_VERSION` in `.env`, then run the same 3 commands above.

**`frappe_docker` infrastructure** —

```bash
cd frappe_docker
git pull
docker compose pull
docker compose --env-file .env up -d
```

## Backups

Every 6 h via ofelia (see `overrides/compose.backup-cron.yaml`). Stored in the `sites` volume under `sites/hmd.agro/private/backups`. For disaster recovery, sync off-host:

```bash
docker compose cp backend:/home/frappe/frappe-bench/sites/hmd.agro/private/backups ./backups
# Manual one-off:
docker compose exec backend bench --site hmd.agro backup --with-files
```

## Testing locally (no real domain)

For a laptop demo without a public DNS:

1. Add to `C:\Windows\System32\drivers\etc\hosts` (admin) or `/etc/hosts` (sudo):
   ```
   127.0.0.1 hmd-prod.local
   ```
2. In `.env`, set:
   ```
   SITES_RULE=Host(`hmd-prod.local`)
   FRAPPE_SITE_NAME_HEADER=hmd.agro
   ```
   The header override tells Frappe to serve the internal `hmd.agro` site regardless of the URL hostname.
3. Recreate the stack so Traefik picks up the new rule:
   ```bash
   docker compose --env-file .env up -d --force-recreate
   ```
4. Visit `https://hmd-prod.local` and accept the self-signed SSL warning.

## Notes

- `.env` is not committed. Only `.env.hmd` (template) is tracked.
- `apps.json` pulls hmd_agro from a public repo (`Mouh1b/hmd_agro`). If you switch to a private one, pass a GitHub token as a build arg (see frappe_docker docs).
- On Windows, `bash` ships with Git for Windows — both Git Bash and PowerShell can run `bash build-hmd.sh` once Git is installed.
- Architecture details, volumes list, full env variable reference: see [`frappe_docker/docs/`](https://github.com/frappe/frappe_docker/tree/main/docs).

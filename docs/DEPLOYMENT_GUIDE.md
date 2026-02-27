# Deployment Guide

## Prerequisites (Server)

- Docker Engine installed
- Docker Compose plugin installed (`docker compose`)
- SSH access for deployment user
- Open inbound TCP port `57631` on firewall/security group

## Configure Environment

In project root on server, create `.env`:

```bash
cp .env.example .env
```

Set at least:
- `ADMIN_PASSWORD`
- `SECRET_KEY`

## Manual Deploy (SSH into server)

```bash
cd /opt/amul-feedback-ui
docker compose up -d --build
```

App URL:
- `http://<server-host>:57631`

## SCP Deploy Script (from local machine)

Use script:

```bash
./scripts/deploy_scp.sh --host <server-name> --user <ssh-user>
```

Optional flags:
- `--port <ssh-port>`
- `--remote-dir <remote-path>`
- `--key <ssh-private-key-path>`
- `--no-run` (only upload/extract)

Equivalent via env vars:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_PORT`
- `REMOTE_DIR`
- `SSH_KEY_PATH`
- `RUN_REMOTE`

Example:

```bash
DEPLOY_HOST=my-server.example.com \
DEPLOY_USER=ubuntu \
SSH_KEY_PATH=~/.ssh/id_rsa \
./scripts/deploy_scp.sh
```

## First-Time Data Initialization

If `INIT_FROM_SHEETS=1` (default in compose), container startup runs:

```bash
python3 scripts/init_from_sheets.py --sync-active
```

That will:
- upsert golden questions
- sync users + assignments from eval sheet
- keep admin auth independent (from `ADMIN_EMAIL` / `ADMIN_PASSWORD`)

## Common Operations

Restart:
```bash
docker compose restart
```

View logs:
```bash
docker compose logs -f
```

Rebuild:
```bash
docker compose up -d --build
```

## Rollback (simple)

If previous deploy directory snapshot exists:
1. restore old files
2. run:
```bash
docker compose up -d --build
```

For DB rollback, restore `app.db` backup before restart.

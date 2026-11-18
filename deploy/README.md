# Deployment

Invite-only public version on a home server, behind a Cloudflare tunnel (no open ports, home IP stays hidden, HTTPS is automatic).

```
browser --HTTPS--> Cloudflare (your domain) --tunnel--> home server
                                                        ├─ cloudflared   (one for all projects, network "web")
                                                        └─ essay-coach   (API + frontend, SQLite in a volume)
```

## 1. Google sign-in (once, works locally too)

1. Go to <https://console.cloud.google.com/>, create a project (e.g. "Essay Coach").
2. **APIs & Services → OAuth consent screen**: type *External*, app name, your email. Scopes: only the default `email`, `profile`, `openid`. These are non-sensitive, so the app does not need Google's verification review.
   Under *App privacy policy link* put `https://essaycoach.your-domain.com/#privacy`.
3. **Publish** the consent screen (status *In production*). While it is in *Testing*, only test users you add by hand can sign in.
4. **Credentials → Create credentials → OAuth client ID**, type *Web application*. Under **Authorized JavaScript origins** add:
   - `http://localhost:5173` (Vite dev server)
   - `http://localhost:8000` (Docker, locally)
   - `https://essaycoach.your-domain.com` (production)

   No redirect URIs are needed.
5. Put the client ID into `backend/.env` as `GOOGLE_CLIENT_ID`, and your own email into `ADMIN_EMAILS`.

## 2. Try the production setup locally

```powershell
docker compose up --build
# open http://localhost:8000, sign in with your admin account
docker compose exec essay-coach python -m app.admin invite --count 3 --note "friends"
```

## 3. On the server

Once:

```bash
docker network create web
# Cloudflare dashboard: add your domain, then Zero Trust -> Networks -> Tunnels -> Create tunnel (cloudflared).
# Copy the token. Under "Public hostnames" add: essaycoach.your-domain.com -> http://essay-coach:8000
cp -r deploy/cloudflared ~/infra/cloudflared && cd ~/infra/cloudflared
echo "TUNNEL_TOKEN=<token>" > .env
docker compose up -d
```

The app (and later every other project the same way: join the `web` network, add a hostname in the dashboard):

```bash
git clone <repo> essay-coach && cd essay-coach
cp backend/.env.example backend/.env   # fill in the key, GOOGLE_CLIENT_ID, ADMIN_EMAILS, PRIVACY_CONTACT, limits
mkdir backups                          # daily database copies land here (see Backups)
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build
```

Update after a `git pull`: run the same `up -d --build` command again.

## Admin commands

Run inside the container (locally: `cd backend` and `python -m app.admin ...`):

```bash
docker compose exec essay-coach python -m app.admin invite --count 3 --note "classmates"
docker compose exec essay-coach python -m app.admin invites          # who used which code
docker compose exec essay-coach python -m app.admin usage            # spend this month, per user
docker compose exec essay-coach python -m app.admin assign-orphans you@gmail.com  # essays from before login
docker compose exec essay-coach python -m app.admin delete-user someone@gmail.com   # deletion request by email
```

## Backups

The `backup` service copies the database to `./backups` once a day (a consistent copy, safe while the app runs,
checked with `PRAGMA integrity_check`) and keeps the newest `BACKUP_KEEP` copies (default 14). The privacy page
promises that deleted data is gone from backups after that many days, so keep the two in line.

- The container runs as uid 1000. If your user on the server has another id: `sudo chown 1000 backups`.
- Check it works: `docker compose logs backup` should say `Backup written to /backups/essay_coach-...db`.
- A backup on the same disk does not survive a dead disk. Copy `backups/` somewhere else too, for example
  with a cron job and `rclone` to cloud storage, or to another machine. That part depends on what you have.

Restore:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml stop essay-coach
docker compose -f docker-compose.yml -f docker-compose.server.yml run --rm -v "$PWD/backups:/backups"   essay-coach cp /backups/essay_coach-<date>.db /data/essay_coach.db
docker compose -f docker-compose.yml -f docker-compose.server.yml start essay-coach
```

## Privacy and account deletion

- Privacy page: `https://essaycoach.your-domain.com/#privacy` (linked in the footer of every page).
  Set `PRIVACY_CONTACT` to the email address for data requests.
- Users delete their account themselves on the privacy page (they type their email to confirm). This deletes
  their essays, revisions, issues and sessions. Cost records stay without a link to the person, so the
  monthly budget stays correct, and their invite code stays used.

## Before going public

- Set a spend limit in the Anthropic Console, as a second line of defence behind `MONTHLY_BUDGET_USD`.
- Set up the off-server copy of `backups/` (see Backups).

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
cp backend/.env.example backend/.env   # fill in the key, GOOGLE_CLIENT_ID, ADMIN_EMAILS, limits
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
```

## Before going public (not done yet)

- Nightly backup of the SQLite volume to somewhere off the server.
- A short privacy page (essays are personal data, GDPR) and a "delete my account" option.
- Also set a spend limit in the Anthropic Console, as a second line of defence behind `MONTHLY_BUDGET_USD`.

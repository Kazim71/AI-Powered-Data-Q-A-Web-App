# 06 · Deployment

Target: **free tier only.**

## There is no separate database to host

DuckDB is embedded — it runs in-process inside the FastAPI backend, not as a server you connect
to. A session's "database" is one `.duckdb` file on the backend's own disk
(`.sessions/<id>/data.duckdb`, see [ADR-0004](decisions/0004-session-model.md)). There is
nothing resembling a managed Postgres or Oracle DB instance in this stack, and nothing to
provision separately. **Choosing where to host is entirely about where the backend process (and
its disk) lives** — the two questions collapse into one.

## Chosen setup

| Piece | Platform | Why |
|---|---|---|
| Frontend | **Vercel** (Hobby) | Native Next.js, zero config, instant previews |
| Backend | **Render** (free web service, Docker) | Simplest free Python + Docker host — see the comparison below for why Oracle Cloud is the stronger alternative if cold starts or ephemeral disk are a problem |
| LLM | **Groq** free API | Open-weights model (`openai/gpt-oss-120b`), fast, no GPU to host |

## Backend hosting: Render vs. Oracle Cloud free VM

Both are genuinely free. The trade-off is setup time vs. what you get for it.

| | **Render** (chosen default) | **Oracle Cloud Always Free VM** |
|---|---|---|
| Setup time | ~5 min — connect repo, done | ~45–60 min — VM, firewall, Docker, reverse proxy, TLS |
| Cost | Free tier, forever (with limits) | Free tier, forever (Oracle's is the most generous of any cloud) |
| Cold starts | **Yes** — sleeps after ~15 min idle, ~50s to wake | **No** — it's a real VM, always on |
| Session disk | **Ephemeral** — wiped on restart/redeploy | **Persistent** — survives restarts, until you reboot the VM itself |
| Compute | Shared, modest | Up to 4 OCPU / 24 GB RAM (Ampere A1), genuinely large for free |
| Ops you own | None | Yours: OS updates, firewall, TLS renewal, the box itself |
| Good fit for | Getting a working link out fast for the assignment deadline | A backend you want to feel like a real always-on service, or one where you also want to demo Ollama running for real (that machine is big enough) |

**Recommendation:** if the deadline is close, ship on Render first — it's a working link in five
minutes, and the cold-start/ephemeral-disk caveats are already handled (documented below, and
the app's session model was designed around disposability from the start). **Then**, since you
already have Oracle experience, moving the backend to the Oracle VM afterward removes both of
Render's real weaknesses (cold start ruining a live demo; a mid-session restart losing an
upload) with no ongoing cost. It's not either/or — do both, cheaply, in that order.

## Render — backend

1. New → **Web Service** → connect the repo.
2. **Root directory:** `backend` · **Runtime:** Docker (uses `backend/Dockerfile`).
3. **Health check path:** `/api/health`
4. Environment variables:

| Key | Value |
|---|---|
| `CORS_ORIGINS` | `https://<your-app>.vercel.app` |
| `GROQ_API_KEY` | your Groq key (console.groq.com) |
| `LLM_PROVIDER` | `groq` |

The Dockerfile honours Render's injected `$PORT`.

### Free-tier caveats — by design, documented

- **Spins down after ~15 min idle**; the next request takes ~50 s to cold-start.
  **Before a demo, hit `/api/health` once to warm it.**
- **Ephemeral disk.** Uploaded files and session databases vanish on restart or redeploy.
  That matches the product model — sessions are disposable, with a 2-hour TTL anyway
  ([ADR-0004](decisions/0004-session-model.md)) — but a user mid-session during a restart
  loses their upload and must re-upload.
- **Single instance.** Sessions live in process memory, so the app must not scale
  horizontally without a shared session store.

## Vercel — frontend

1. Import repo → **Root directory:** `frontend`.
2. Env var `NEXT_PUBLIC_API_URL` = `https://<your-backend>.onrender.com/api` (or your Oracle
   VM's URL, if using that instead — see below).

## Oracle Cloud free VM — backend (alternative to Render)

Oracle's Always Free tier includes a real, always-on Ampere A1 (ARM) VM — up to 4 OCPU / 24 GB
RAM, free forever, no card charge after the trial. This runs the backend with no cold start and
a persistent disk. The trade-off is that you're now the one managing the box.

**One thing this isn't:** *Oracle Autonomous Database*, a separate Always Free product, is
Oracle's own managed RDBMS (like a free-tier Postgres). It doesn't fit this app at all — the
whole design is DuckDB embedded in the backend process (see above), and moving to a real
client-server database would mean re-architecting how every session's tables are created and
queried. If you've used Oracle Cloud before for "a database," it may well have been this
product — for this app, what you actually want is just the **Compute VM**, not Autonomous DB.

**Why HTTPS is required, not optional, here:** Vercel serves the frontend over HTTPS. A browser
blocks an HTTPS page from calling an HTTP API ("mixed content"), so the backend must also be
HTTPS — plain `http://<ip>:8000` will not work once the frontend is live. That means you need a
domain name pointed at the VM (a bare IP can't get a valid certificate) and a reverse proxy
that provisions one. The steps below use [Caddy](https://caddyserver.com), which does this
automatically from just a domain name — no manual certbot renewal to remember.

### Setup

1. **Create (or reuse) the VM.** OCI Console → *Compute → Instances → Create Instance*.
   Shape: **VM.Standard.A1.Flex** (Ampere, Always Free–eligible) — 1–2 OCPU / 6–12 GB is plenty
   for this app and leaves the rest of your free allowance for other things. Image: **Ubuntu
   22.04**. Save the SSH key.

2. **Open ports 80 and 443.** Two separate firewalls both need this, and forgetting the second
   one is the classic Oracle-VM gotcha:
   - **OCI Security List / Network Security Group** (in the console, on the VM's subnet):
     add ingress rules for `0.0.0.0/0` → TCP `80` and `443`.
   - **The VM's own firewall.** Oracle's Ubuntu images ship with `iptables` rules that block
     almost everything by default, independent of the console setting above:
     ```bash
     sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     ```

3. **Get a free subdomain pointed at the VM's public IP.** The VM's IP alone can't get a TLS
   certificate. Easiest free option: [duckdns.org](https://www.duckdns.org) — sign in, create
   e.g. `your-app.duckdns.org`, point it at the VM's public IP. (If you already own a domain,
   a subdomain there works the same way — just add an A record.)

4. **Install Docker:**
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # log out/in once for this to take effect
   ```

5. **Get the code onto the VM and add Caddy as a reverse proxy.** Clone the repo, then add a
   `Caddyfile` next to `docker-compose.yml`:
   ```
   your-app.duckdns.org {
       reverse_proxy backend:8000
   }
   ```
   and a `caddy` service to `docker-compose.yml`:
   ```yaml
     caddy:
       image: caddy:2
       ports: ["80:80", "443:443"]
       volumes:
         - ./Caddyfile:/etc/caddyfile:ro
         - caddy_data:/data
       command: caddy run --config /etc/caddyfile
   volumes:
     caddy_data:
   ```
   Caddy requests and renews the Let's Encrypt certificate automatically the first time it
   starts — nothing else to configure.

6. **Set the backend's environment** (`backend/.env` on the VM): `CORS_ORIGINS` to your Vercel
   URL, `GROQ_API_KEY`, `LLM_PROVIDER=groq`.

7. **Bring it up:**
   ```bash
   docker compose up -d --build
   ```
   `https://your-app.duckdns.org/api/health` should return `{"status": "ok"}` within a minute.

8. **Point the frontend at it:** Vercel env var `NEXT_PUBLIC_API_URL` =
   `https://your-app.duckdns.org/api`.

**Now that the disk is persistent, `purge_expired()`** (built in `core/session.py`, never
scheduled — see [ADR-0004](decisions/0004-session-model.md)) **actually matters**: on Render,
old sessions vanish for free on every restart; on a VM that never restarts, they'll accumulate
on disk indefinitely without it. Wire it to a periodic task (e.g. FastAPI's `lifespan` with an
`asyncio` loop, or a cron hitting a small admin endpoint) before leaving this running long-term.

## Other alternatives considered

| Platform | Pros | Cons | Verdict |
|---|---|---|---|
| **Railway** | No cold starts, best DX | Trial credit, not truly free long-term | Good middle ground if the Oracle setup is more than you want to do |
| **Hugging Face Spaces** (Docker) | Free, no sleep, on-brand for open-source AI | Less conventional for a web backend | Strong single-container option |
| **Fly.io** | Fast, global | Free allowance has tightened; card required | Not chosen |

## Demo-day checklist

- [ ] Warm the backend: open `/api/health`
- [ ] Upload the sample files once to confirm the end-to-end path
- [ ] Record the demo video against **local**, so a cold start never appears in it
- [ ] Keep `docker compose up` instructions in the README as the reliable fallback

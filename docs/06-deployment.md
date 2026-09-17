# 06 · Deployment

Target: **free tier only.**

## Chosen setup

| Piece | Platform | Why |
|---|---|---|
| Frontend | **Vercel** (Hobby) | Native Next.js, zero config, instant previews |
| Backend | **Render** (free web service, Docker) | Simplest free Python + Docker host |
| LLM | **Groq** free API | Open-weights Llama 3.3 70B, fast, no GPU to host |

## Render — backend

1. New → **Web Service** → connect the repo.
2. **Root directory:** `backend` · **Runtime:** Docker (uses `backend/Dockerfile`).
3. **Health check path:** `/api/health`
4. Environment variables:

| Key | Value |
|---|---|
| `CORS_ORIGINS` | `https://<your-app>.vercel.app` |
| `GROQ_API_KEY` | *(milestone 2)* |
| `LLM_PROVIDER` | `groq` *(milestone 2)* |

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

## Vercel — frontend *(milestone 3)*

1. Import repo → **Root directory:** `frontend`.
2. Env var `NEXT_PUBLIC_API_URL` = `https://<your-backend>.onrender.com/api`.

## Alternatives considered

| Platform | Pros | Cons | Verdict |
|---|---|---|---|
| **Railway** | No cold starts, best DX | Trial credit, not truly free long-term | Best if cold starts hurt the demo |
| **Hugging Face Spaces** (Docker) | Free, no sleep, on-brand for open-source AI | Less conventional for a web backend | Strong single-container option |
| **Oracle Cloud Always Free** (ARM, up to 4 OCPU / 24 GB) | Genuinely free forever; big enough to run Ollama locally | Manual VM, nginx, TLS, systemd — ~1 h setup | Only if demoing the fully-offline LLM path |
| **Fly.io** | Fast, global | Free allowance has tightened; card required | Not chosen |

## Demo-day checklist

- [ ] Warm the backend: open `/api/health`
- [ ] Upload the sample files once to confirm the end-to-end path
- [ ] Record the demo video against **local**, so a cold start never appears in it
- [ ] Keep `docker compose up` instructions in the README as the reliable fallback

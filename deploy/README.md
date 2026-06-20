# Med AI Adviser — Docker deploy

All Docker configuration lives in this directory. Run commands from here:

```bash
cd deploy
```

Full plan: [docs/plans/phase5-impl-plan.md](../docs/plans/phase5-impl-plan.md) (§10 local, §11 CI/Pi).

## Configuration (`deploy/config/`)

The **`api`** container reads all YAML from **`deploy/config/`**, mounted at `/app/config` (nothing baked into the image except `prompts/` and code).

| File | Purpose |
|------|---------|
| `aliases.yaml`, `api.yaml`, `chat.yaml`, … | App defaults; edit here for deploy-specific tuning |
| `llm.yaml` | **Operator file** (gitignored) — LLM provider + secrets via env |
| `llm-*.yaml.example` | Templates → copy to `llm.yaml` |

Root repo [`config/`](../config/) is for local dev **without** Docker. Keep `deploy/config/` in sync when you change defaults in the repo (or copy files before upgrade).

## Local (Docker Desktop)

```bash
git submodule update --init --recursive
cd deploy
cp .env.example .env
cp docker-compose.override.example.yml docker-compose.override.yml
mkdir -p .data/db .data/logs
cp config/llm-nvidia.yaml.example config/llm.yaml   # or llm-openai / llm-ollama
# Edit .env — set NVIDIA_API_KEY or OPENAI_API_KEY if using cloud LLM

docker compose --profile local build
docker compose --profile local up -d
```

Open **http://localhost:8080** (edge `gateway` → `api` + `web`).

Health check:

```bash
curl http://localhost:8080/health
```

Stop:

```bash
docker compose --profile local down
```

## Services

| Service | Role |
|---------|------|
| `api` | FastAPI backend (`adviser-api`) |
| `web` | SPA static files (`adviser-web`, nginx inside) |
| `gateway` | Edge nginx (`--profile local` only), port **8080** |

## Pi / production

Use Release tarball and Hub images — see phase5-impl-plan §11. Do not enable profile `local` on Pi; use host nginx + `nginx/host-adviser.conf.template`.

After unpacking the bundle, ensure `config/llm.yaml` exists and adjust other YAML under `config/` if needed.

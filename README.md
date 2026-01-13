# Soumetsu API

REST API for Soumetsu, providing endpoints for users, scores, beatmaps, clans, leaderboards, and osu! legacy API compatibility.

## Quick Start

```bash
# Copy environment files
for f in configuration/*.example; do cp "$f" "${f%.example}"; done

# Create .env for Docker Compose
cat > .env << 'EOF'
APP_EXTERNAL_PORT=8000
MYSQL_DATA_PATH=./mysql_data
EOF

# Build and run
make build
make run
```

API available at `http://localhost:8000/api/v2/health`

## Endpoints

| Prefix | Description |
|--------|-------------|
| `/api/v2/auth` | Login, register, logout, session |
| `/api/v2/users` | Profiles, settings, avatar/banner uploads |
| `/api/v2/users/{id}/scores` | Best, recent, firsts, pinned scores |
| `/api/v2/scores` | Score lookup, pin/unpin |
| `/api/v2/beatmaps` | Beatmap search, lookup, scores |
| `/api/v2/leaderboard` | Global/country rankings |
| `/api/v2/clans` | Clan CRUD, membership, invites |
| `/api/v2/friends` | Friend list management |
| `/api/v2/comments` | User profile comments |
| `/api/v2/admin` | Admin operations (requires privileges) |
| `/api/v2/peppy` | osu! legacy API compatibility |

## Configuration

Environment files in `configuration/`:

| File | Purpose |
|------|---------|
| `app.env` | CORS, session TTL, hCaptcha, storage paths |
| `mysql.env` | Database credentials |
| `redis.env` | Redis connection |

## Make Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make run` | Run (foreground) |
| `make run-d` | Run (background) |
| `make lint` | Run linters |

## Authentication

Include session token in requests:
```
Authorization: Bearer <token>
```

Tokens obtained from `/api/v2/auth/login`.

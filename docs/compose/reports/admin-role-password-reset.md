---
feature: admin-role-password-reset
status: delivered
specs: []
plans:
  - docs/compose/plans/2026-06-13-admin-role-password-reset.md
branch: master
commits: cadaf33..e96dde1
---

# Admin Role + Password Reset — Final Report

## What Was Built

Added admin role system with password reset capability. A pre-configured `admin` user is created on first startup (when `ADMIN_PASSWORD` env var is set and `system.db` is empty). Admins can list users, reset passwords, and change user roles via API endpoints.

## Architecture

### Database Changes

- `accounts` table gained `role TEXT NOT NULL DEFAULT 'user'` column
- Migration in `ensure_system_schema()` adds column to existing DBs
- `AccountRecord` dataclass includes `role` field

### New Components

- `ensure_admin_user()` — bootstrap function in `src/services/auth.py:37`
- `src/api/routers/admin.py` — admin API endpoints
- `require_admin` dependency in `src/api/deps.py:28`

### Admin API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/users` | List all users |
| POST | `/api/v1/admin/users/{username}/reset-password` | Reset password |
| POST | `/api/v1/admin/users/{username}/role` | Change role |

### UserContext Changes

- `UserContext` now includes `role: str` field
- Admin users have empty `db_path` (sentinel value)
- Admin login skips profile check
- `/auth/me` returns `role` in response

## Usage

### First Start (Bootstrap)

```bash
# Set ADMIN_PASSWORD in .env
ADMIN_PASSWORD=your_secure_password

# Start application
docker compose --profile local up -d

# Login as admin
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_secure_password"}'
```

### Admin Operations

```bash
# List users
curl -b cookies.txt http://localhost:8080/api/v1/admin/users

# Reset user password
curl -b cookies.txt -X POST http://localhost:8080/api/v1/admin/users/alice/reset-password \
  -H "Content-Type: application/json" \
  -d '{"new_password":"newpass12345"}'

# Promote user to admin
curl -b cookies.txt -X POST http://localhost:8080/api/v1/admin/users/alice/role \
  -H "Content-Type: application/json" \
  -d '{"role":"admin"}'
```

### Security Rules

- Password minimum 8 characters
- Cannot demote the last admin
- Password reset invalidates all user sessions
- Admin endpoints require `AUTH_ENABLED=true`

## Verification

- 6 unit tests in `tests/services/test_admin.py` — all pass
- 7 integration tests in `tests/integration/test_admin_api.py` — all pass
- Docker rebuild and smoke test — health check OK
- 204 tests pass total (7 pre-existing failures unrelated to this feature)

## Journey Log

- [pivot] Initially `ensure_admin_user` raised RuntimeError when `ADMIN_PASSWORD` was not set — changed to skip bootstrap (log info) so existing tests and single-user deployments continue working
- [lesson] `deploy/` directory is gitignored — needed `git add -f` for docker-compose.yml and .env.example

## Source Materials

| File | Role | Notes |
|------|------|-------|
| `docs/compose/plans/2026-06-13-admin-role-password-reset.md` | Implementation plan | Complete |

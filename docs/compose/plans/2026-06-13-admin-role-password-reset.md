# Admin Role + Password Reset Implementation Plan

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/admin-role-password-reset.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin role system with password reset capability via API.

**Architecture:** Add `role` column to `accounts`, bootstrap `admin` on first empty `system.db`, admin-only endpoints for user list / password reset / role change. Admin is a **system account** without a per-user knowledge DB; admin routes do not require a complete profile.

**Tech Stack:** Python, FastAPI, SQLite, Argon2

**Scope (explicit non-goals):** No admin UI in this plan — API + OpenAPI only. Frontend admin screens are a follow-up.

---

## Scope tags (S1–S5)

| Tag | Meaning |
|-----|---------|
| **S1** | Schema migration for existing `system.db` |
| **S2** | Store layer (`AccountRecord`, SQL) |
| **S3** | Auth service + bootstrap admin |
| **S4** | Role in session resolution (`UserContext`, login, `/auth/me`) |
| **S5** | Admin API + authorization |

---

## Design decisions (read before coding)

### Admin account model

- Username `admin` is already in `RESERVED_USERNAMES` — created only via bootstrap, not `/register`.
- Admin has `role="admin"` and **no user knowledge DB**. Use a sentinel `db_path` value documented in code, e.g. `""` (empty string), and **never** call `UserContextFactory.get()` for admin except where unavoidable.
- **Login (`POST /auth/login`):** if `account.role == "admin"`, skip `user_factory.get()` and profile check; return `AuthMeResponse(username, profile_complete=True, role="admin")`.
- **Session resolution (`resolve_user_context`):** if `account.role == "admin"`, return a lightweight `UserContext` with `role="admin"`, services stubbed or omitted — admin router uses `AuthService` only via `require_admin`, not `documents_service` etc.
- **Profile gate:** `require_admin` depends on `get_user_context`, **not** `require_complete_profile`. Admin can call admin endpoints without filling profile.

### Existing deployments

- Fresh DB: `CREATE TABLE` in `system_schema.sql` includes `role`.
- Existing DB: migration in `ensure_system_schema()` (Task 1) adds column if missing.
- If `accounts` is **non-empty** and no user has `role='admin'`: bootstrap does **not** run automatically. Operator promotes a user via one-shot SQL or future CLI (document in README); optional Task 3b covers manual promote script.

### Security rules

- Password reset: enforce `MIN_PASSWORD_LEN` (8), hash via `AuthService`, then **`delete_sessions_for_username`** so old sessions invalidate.
- Role change: reject demoting the **last** admin; reject invalid roles.
- `AUTH_ENABLED=false` (dev): admin endpoints return **403** with message «Admin API requires AUTH_ENABLED» — do not bypass auth in dev.

### Error handling

Use existing `AppError` pattern (`http_status`, `code`), not raw `HTTPException`, except where FastAPI validation applies.

```python
class ForbiddenError(AppError):
    code = "forbidden"
    http_status = 403
```

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `src/store/sql/system_schema.sql` | Modify | `role` column on `accounts` |
| `src/api/schema_init.py` | Modify | Migration for existing DBs |
| `src/store/sql/sqlite_system_store.py` | Modify | `role` on `AccountRecord`, list/update helpers |
| `src/services/auth.py` | Modify | Bootstrap admin, `admin_reset_password`, role guards |
| `src/api/factory.py` | Modify | Call `ensure_admin_user` after `ensure_system_schema` |
| `src/api/user_context.py` | Modify | `role` on `UserContext`; admin stub context |
| `src/api/user_resolver.py` | Modify | Pass `role` from account |
| `src/api/routers/auth.py` | Modify | Admin login without user DB |
| `src/api/deps.py` | Modify | `require_admin` |
| `src/services/errors.py` | Modify | `ForbiddenError` |
| `src/api/routers/admin.py` | Create | Admin endpoints |
| `src/api/schemas.py` | Modify | Admin DTOs, `role` on `AuthMeResponse` |
| `src/api/app.py` | Modify | Register admin router |
| `docs/openapi/openapi.json` | Modify | New admin paths |
| `deploy/docker-compose.yml` | Modify | `ADMIN_PASSWORD` |
| `deploy/.env.example` | Modify | `ADMIN_PASSWORD` |
| `README.md` | Modify | Document env + bootstrap |
| `tests/services/test_admin.py` | Create | Store + auth unit tests |
| `tests/integration/test_admin_api.py` | Create | API tests (`TestClient`) |

---

### Task 1: Schema + migration for `role`

**Covers:** [S1, S2]

**Files:**
- Modify: `src/store/sql/system_schema.sql`
- Modify: `src/api/schema_init.py`

- [ ] **Step 1: Update `system_schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS accounts (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    db_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

- [ ] **Step 2: Add migration in `ensure_system_schema()`**

After `executescript`, check `PRAGMA table_info(accounts)`; if `role` missing:

```sql
ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
```

Idempotent — safe on fresh and existing DBs.

- [ ] **Step 3: Document upgrade path in README**

Note: existing accounts get `role='user'`. Promote first admin manually if DB already had users (see Task 3b).

- [ ] **Step 4: Commit**

```bash
git add src/store/sql/system_schema.sql src/api/schema_init.py README.md
git commit -m "feat: add role column to accounts with migration"
```

---

### Task 2: Update `AccountRecord` and system store

**Covers:** [S2]

**Files:**
- Modify: `src/store/sql/sqlite_system_store.py`

- [ ] **Step 1: Add `role` to `AccountRecord`**

```python
@dataclass(frozen=True, slots=True)
class AccountRecord:
    username: str
    password_hash: str
    role: str  # 'admin' | 'user'
    db_path: str
    created_at: str
```

- [ ] **Step 2: Update `insert_account` / `get_account` SELECTs** to include `role`.

- [ ] **Step 3: Update `AuthService.register`** to pass `role="user"` in `AccountRecord`.

- [ ] **Step 4: Add methods**

- `list_accounts() -> list[AccountRecord]` (ORDER BY `created_at`)
- `update_password(username, password_hash) -> None`
- `update_role(username, role) -> None`
- `count_admins() -> int` — `SELECT COUNT(*) FROM accounts WHERE role = 'admin'`

- [ ] **Step 5: Commit**

```bash
git add src/store/sql/sqlite_system_store.py src/services/auth.py
git commit -m "feat: add role support to system store"
```

---

### Task 3: Bootstrap admin on first run

**Covers:** [S3]

**Files:**
- Modify: `src/services/auth.py`
- Modify: `src/api/factory.py`

- [ ] **Step 1: Add `ensure_admin_user(system_store)`**

```python
async def ensure_admin_user(store: SqliteSystemStore) -> None:
    """Create admin account when system.db has zero accounts."""
    if await store.list_accounts():
        return
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError(
            "ADMIN_PASSWORD is required when bootstrapping the first account (admin)"
        )
    if len(admin_password) < MIN_PASSWORD_LEN:
        raise RuntimeError("ADMIN_PASSWORD must be at least 8 characters")
    await store.insert_account(
        AccountRecord(
            username="admin",
            password_hash=_ph.hash(admin_password),
            role="admin",
            db_path="",  # sentinel: no user DB
            created_at=datetime.now(UTC).isoformat(),
        )
    )
```

- [ ] **Step 2: Call from `create_shared_context()`** after `ensure_system_schema()`.

- [ ] **Step 3: Commit**

```bash
git add src/services/auth.py src/api/factory.py
git commit -m "feat: bootstrap admin user on empty system.db"
```

---

### Task 3b (optional): Promote existing user to admin

**Covers:** [S3]

**Files:**
- Create: `scripts/promote_admin.py` (or document SQL one-liner in README)

- [ ] **Step 1: Script / docs**

```bash
# Example SQL (backup system.db first):
# UPDATE accounts SET role = 'admin' WHERE username = 'alice';
```

- [ ] **Step 2: Commit** (if script added)

---

### Task 4: `ForbiddenError` + `require_admin` + `UserContext.role`

**Covers:** [S4, S5]

**Files:**
- Modify: `src/services/errors.py`
- Modify: `src/api/deps.py`
- Modify: `src/api/user_context.py`
- Modify: `src/api/user_resolver.py`
- Modify: `src/api/routers/auth.py`
- Modify: `src/api/schemas.py`

- [ ] **Step 1: Add `ForbiddenError`**

```python
class ForbiddenError(AppError):
    code = "forbidden"
    http_status = 403
```

- [ ] **Step 2: Add `role: str` to `UserContext`** (default `"user"`).

- [ ] **Step 3: `resolve_user_context`**

Load `account.role`. If `admin`, return admin stub `UserContext(username, role="admin", db_path="", ...)` without opening SQLite user DB.

If `AUTH_ENABLED=false`, raise `ForbiddenError` for any caller of `require_admin` (check in `require_admin` via `auth_enabled()`).

- [ ] **Step 4: `require_admin` in `deps.py`**

```python
async def require_admin(
    user: UserContext = Depends(get_user_context),
) -> UserContext:
    if not auth_enabled():
        raise ForbiddenError("Admin API requires AUTH_ENABLED=true")
    if user.role != "admin":
        raise ForbiddenError("Admin access required")
    return user
```

- [ ] **Step 5: Fix `login` for admin** — skip `user_factory.get` when `account.role == "admin"`.

- [ ] **Step 6: Extend `AuthMeResponse`** with `role: str = "user"`. Update `/login`, `/register`, `/me`.

- [ ] **Step 7: Commit**

```bash
git add src/services/errors.py src/api/deps.py src/api/user_context.py \
  src/api/user_resolver.py src/api/routers/auth.py src/api/schemas.py
git commit -m "feat: role-aware UserContext and require_admin"
```

---

### Task 5: Admin service methods + router

**Covers:** [S5]

**Files:**
- Modify: `src/services/auth.py`
- Create: `src/api/routers/admin.py`
- Modify: `src/api/app.py`
- Modify: `src/api/schemas.py`

- [ ] **Step 1: Add to `AuthService`**

- `list_accounts()` — delegate to store, strip password hashes in router
- `admin_reset_password(username, new_password)` — validate length, hash, update, invalidate sessions
- `admin_set_role(username, role, *, actor_username)` — validate role, forbid demoting last admin, forbid self-demotion if last admin

- [ ] **Step 2: Create `admin.py` router**

Use `Depends(_auth)` → `AuthService`, `Depends(require_admin)`. Raise `NotFoundError`, `ValidationError`, `ForbiddenError` — not `HTTPException`.

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/users` | List users (no password hashes) |
| POST | `/api/v1/admin/users/{username}/reset-password` | Body: `{ "new_password": "..." }` |
| POST | `/api/v1/admin/users/{username}/role` | Body: `{ "role": "admin" \| "user" }` |

- [ ] **Step 3: Register router in `app.py`**

- [ ] **Step 4: Commit**

```bash
git add src/services/auth.py src/api/routers/admin.py src/api/app.py src/api/schemas.py
git commit -m "feat: admin API for users, password reset, and roles"
```

---

### Task 6: Environment variables + docs

**Covers:** [S3]

**Files:**
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/.env.example`
- Modify: `README.md`

- [ ] **Step 1: Docker env**

```yaml
ADMIN_PASSWORD: ${ADMIN_PASSWORD:-}
```

- [ ] **Step 2: `.env.example`**

```env
# Required on first start when system.db has no accounts (creates admin)
ADMIN_PASSWORD=changeme
```

- [ ] **Step 3: README** — table row for `ADMIN_PASSWORD`, bootstrap behaviour, promote script.

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml deploy/.env.example README.md
git commit -m "docs: document ADMIN_PASSWORD bootstrap"
```

---

### Task 7: OpenAPI

**Covers:** [S5]

**Files:**
- Modify: `docs/openapi/openapi.json`

- [ ] **Step 1: Add admin paths and schemas** (mirror router).

- [ ] **Step 2: Regenerate frontend client** (manual step in `frontend/`: `npm run gen:api`) — note in commit message, separate repo/submodule commit if needed.

- [ ] **Step 3: Commit** backend OpenAPI

```bash
git add docs/openapi/openapi.json
git commit -m "docs: OpenAPI for admin endpoints"
```

---

### Task 8: Unit tests

**Covers:** [S2, S3]

**Files:**
- Create: `tests/services/test_admin.py`

- [ ] **Step 1: Bootstrap admin**

Use `ensure_system_schema(path)` + `SqliteSystemStore`, not `store.initialize()`.

- [ ] **Step 2: Tests**

- `test_ensure_admin_user_creates_admin`
- `test_ensure_admin_user_skips_when_accounts_exist`
- `test_update_role`
- `test_admin_reset_password_invalidates_sessions`
- `test_cannot_demote_last_admin`

- [ ] **Step 3: Run**

```bash
pytest tests/services/test_admin.py -v
```

- [ ] **Step 4: Commit**

---

### Task 9: Integration tests

**Covers:** [S5]

**Files:**
- Create: `tests/integration/test_admin_api.py`

Use existing patterns from `tests/integration/test_auth_api.py`: **`TestClient`**, `monkeypatch` for `SYSTEM_DB_PATH`, cookie jar after login.

- [ ] **Step 1: Tests**

- `GET /api/v1/admin/users` → 401 without session
- Register user → login as user → admin list → **403** `forbidden`
- Bootstrap admin (env `ADMIN_PASSWORD`) → login admin → list users → **200**
- Admin resets user password → user old session invalid, new login works
- Non-admin cannot reset passwords

- [ ] **Step 2: Run**

```bash
pytest tests/integration/test_admin_api.py -v
```

- [ ] **Step 3: Commit**

---

### Task 10: End-to-end verification

**Covers:** [S1–S5]

- [ ] **Step 1: Full suite**

```bash
pytest
```

- [ ] **Step 2: Manual curl** (save cookie from login response)

```bash
# API direct (dev)
API=http://localhost:8000

curl -s "$API/api/v1/admin/users"          # expect 401

curl -s -c cookies.txt -X POST "$API/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}'

curl -s -b cookies.txt "$API/api/v1/admin/users"

curl -s -b cookies.txt -X POST "$API/api/v1/admin/users/alice/reset-password" \
  -H "Content-Type: application/json" \
  -d '{"new_password":"newpass12345"}'
```

Docker gateway: replace `$API` with `http://localhost:8080`.

- [ ] **Step 3: Docker smoke** (optional)

```bash
cd deploy && docker compose --profile local up -d --build
curl http://localhost:8080/health
```

---

## Task order summary

```
Task 1 (schema+migration) → Task 2 (store) → Task 3 (bootstrap)
→ Task 4 (authz + UserContext) → Task 5 (admin API)
→ Task 6 (env docs) → Task 7 (OpenAPI) → Task 8–9 (tests) → Task 10 (E2E)
```

Task 3b anytime after Task 2 if needed for existing installs.

---

## Checklist before merge

- [ ] Existing `system.db` migrates without data loss
- [ ] Admin can log in without user DB / profile
- [ ] Regular user gets 403 on admin routes
- [ ] Password reset invalidates sessions
- [ ] Last admin cannot be demoted
- [ ] `register` sets `role=user`
- [ ] OpenAPI updated
- [ ] No secrets in logs or commits

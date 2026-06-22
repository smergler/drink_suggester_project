# Backend Spec — Drink Suggester

**Status:** Authoritative. All P6 implementation must follow this document.
**Scope:** Multi-user persistence layer. Supabase Auth + Postgres (via supabase-py + user JWT).
**Constraint:** NO raw asyncpg for user-scoped data. See `docs/adr-001-data-isolation.md`.

---

## Data Model

### `bottles` (user inventory)

```sql
id          uuid primary key default gen_random_uuid()
user_id     uuid not null references auth.users(id) on delete cascade
name        text not null
category    text not null        -- e.g. "bourbon", "mezcal", "liqueur"
subcategory text                 -- e.g. "amaro", "sweet", "joven"
is_active   boolean not null default true  -- soft-delete; false = removed from bar
created_at  timestamptz not null default now()
updated_at  timestamptz not null default now()

UNIQUE(user_id, name)
```

### `companions`

```sql
id         uuid primary key default gen_random_uuid()
user_id    uuid not null references auth.users(id) on delete cascade
name       text not null
created_at timestamptz not null default now()
updated_at timestamptz not null default now()

UNIQUE(user_id, name)
```

### `companion_preferences`

Preferences are immutable — create or delete only, no update. No `updated_at` column.

```sql
id           uuid primary key default gen_random_uuid()
companion_id uuid not null references companions(id) on delete cascade
type         text not null check (type in ('like', 'dislike'))
value        text not null     -- category-level, e.g. "bourbon", "mezcal", "sweet"
created_at   timestamptz not null default now()

UNIQUE(companion_id, value)    -- only one preference (like or dislike) per value per companion
```

Note: `UNIQUE(companion_id, value)` (not `type`) so a value cannot be both liked and disliked
simultaneously. Preference reversal replaces the row (handled atomically via RPC — see below).

### `sessions`

```sql
id         uuid primary key default gen_random_uuid()
user_id    uuid not null references auth.users(id) on delete cascade
occasion   text not null
mood       text
created_at timestamptz not null default now()
ended_at   timestamptz          -- null = session is open
```

Partial unique index to prevent multiple open sessions per user:

```sql
CREATE UNIQUE INDEX one_open_session_per_user
  ON sessions(user_id)
  WHERE ended_at IS NULL;
```

### `session_companions` (join: which companions were in a session)

```sql
session_id   uuid not null references sessions(id) on delete cascade
companion_id uuid not null references companions(id) on delete cascade
primary key (session_id, companion_id)
```

**Application-layer guard (enforced in endpoint code, not just RLS):** before inserting a
`session_companions` row, verify that the companion's `user_id` matches the session's `user_id`.
The RLS policy on `sessions` allows user A to write `session_companions` for their own sessions —
but does not prevent associating a foreign companion ID. The application must validate ownership
explicitly and return 400 if any companion ID doesn't belong to the authenticated user.

### `session_drinks`

Ingredient `source` values (from `recommender.schemas.IngredientSource`):
`"inventory"` | `"pantry"` | `"perishable"` | `"missing"`

```sql
id          uuid primary key default gen_random_uuid()
session_id  uuid not null references sessions(id) on delete cascade
name        text not null
ingredients jsonb not null    -- list of {name, quantity, source} objects
steps       jsonb not null default '[]'
why         text not null default ''
verdict     text check (verdict in ('liked', 'disliked', 'neutral'))  -- null = not yet rated
created_at  timestamptz not null default now()
```

---

## Resolved Design Questions

### Error-body contract

All errors use FastAPI's default `{"detail": "..."}` format. Exception handlers
in `app/main.py` map domain errors to this format. Clients must always read
`response.json().detail` on non-2xx responses.

### Pagination

`limit` / `offset` on every list endpoint. Defaults: `limit=20`, max `limit=100`.
Every list response is a plain JSON array (no envelope). Singleton endpoints
(`GET /sessions/active`, `GET /sessions/{id}`) return a single object, not an array.

### Unique keys

- `UNIQUE(user_id, name)` on `bottles` and `companions`.
- `UNIQUE(companion_id, value)` on `companion_preferences` (one sentiment per value).
- Partial unique index `one_open_session_per_user` on `sessions`.
- POST to create; 409 Conflict if constraint violated.
- PUT to update by ID; 404 if not found or belongs to another user.
- No upsert endpoints.

### "Current session" definition

A session is **current** if `ended_at IS NULL` (enforced unique per user by partial index).
The endpoint is `GET /sessions/active` (not `/sessions/current` — see routing note below).

If no open session exists when `POST /recommend` is called, one is created automatically
using the request's `occasion` and `mood`. Companion IDs in the request are recorded in
`session_companions` (see MINOR 5 fix). Any companion ID not owned by the authenticated
user returns 400 before the session is created.

`POST /sessions/{id}/end` closes a session explicitly (`ended_at = NOW()`).

### Companion feedback → like/dislike rule

When `PATCH /session-drinks/{id}/verdict` is called:

- **`liked`**: for each companion in the session, add the drink's inventory ingredient
  categories (from `session_drinks.ingredients` where `source == "inventory"`, resolved
  to `bottles.category` for that user) as `type=like` preferences. Implemented via
  `supabase.rpc("upsert_companion_like", {...})` — see RPC spec below.

- **`disliked`**: same, but `type=dislike`. A `dislike` for a value that already has a
  `like` row must replace it atomically — this is a DELETE + INSERT and **must run in a
  Postgres transaction**. Implemented via `supabase.rpc("upsert_companion_dislike", {...})`.
  The supabase-py REST path cannot do two-step operations atomically; an RPC is mandatory.

- **`neutral`**: no preference updates.

**Category-level is intentional:** if a companion liked a Boulevardier, we record they
like "bourbon" — not "Four Roses Small Batch" — so preferences generalize across bottles.

### Required Postgres RPCs

```sql
-- Atomically set a like (remove any existing dislike first)
CREATE OR REPLACE FUNCTION upsert_companion_like(
  p_companion_id uuid, p_value text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO companion_preferences(companion_id, type, value)
  VALUES (p_companion_id, 'like', p_value)
  ON CONFLICT (companion_id, value) DO UPDATE SET type = 'like';
END;
$$;

-- Atomically set a dislike (remove any existing like first)
CREATE OR REPLACE FUNCTION upsert_companion_dislike(
  p_companion_id uuid, p_value text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO companion_preferences(companion_id, type, value)
  VALUES (p_companion_id, 'dislike', p_value)
  ON CONFLICT (companion_id, value) DO UPDATE SET type = 'dislike';
END;
$$;
```

Note: `ON CONFLICT ... DO UPDATE` replaces the UNIQUE constraint approach and makes the
DELETE+INSERT atomic in a single statement. `SECURITY DEFINER` is required because RLS
on `companion_preferences` is row-level; the function runs as the definer but only
operates on the passed companion ID (which the endpoint validates for ownership first).

---

## Endpoint Surface

All endpoints require `Authorization: Bearer <supabase_jwt>` except `POST /auth/*`.

### Auth (Supabase-managed, thin proxy)

```
POST /auth/signup          body: {email, password}  → {access_token, refresh_token, user}
POST /auth/login           body: {email, password}  → {access_token, refresh_token, user}
POST /auth/refresh         body: {refresh_token}    → {access_token}
```

### Inventory

```
GET    /inventory                        → list[Bottle]        (?limit=20&offset=0, active only)
POST   /inventory                        → Bottle              (201; 409 if name exists)
PUT    /inventory/{id}                   → Bottle              (404 if not found/not owned)
DELETE /inventory/{id}                   → 204                 (soft-delete: is_active=false)
```

`GET /inventory?include_inactive=true` returns all bottles including soft-deleted.

### Companions

```
GET    /companions                        → list[Companion]     (?limit=20&offset=0)
POST   /companions                        → Companion           (201; 409 if name exists)
PUT    /companions/{id}                   → Companion           (rename only; 404 if not owned)
DELETE /companions/{id}                   → 204                 (cascades preferences)
GET    /companions/{id}/preferences       → list[Preference]
POST   /companions/{id}/preferences       → Preference          (409 if value already has a preference)
DELETE /companions/{id}/preferences/{pid} → 204
```

`GET /companions` returns companions without embedded preferences (avoids N+1).
Use `GET /companions/{id}/preferences` to fetch preferences for a specific companion.

### Sessions

```
GET    /sessions                          → list[Session]       (?limit=20&offset=0)
GET    /sessions/active                   → Session             (404 if no open session)
GET    /sessions/{id}                     → Session             (404 if not found/not owned)
POST   /sessions/{id}/end                 → Session             (sets ended_at=now())
GET    /sessions/{id}/drinks              → list[SessionDrink]
```

**Route registration order:** `GET /sessions/active` MUST be registered before
`GET /sessions/{id}` to prevent FastAPI matching "active" as a UUID path parameter.

Sessions are created implicitly by `POST /recommend`, never by an explicit POST endpoint.

### Session drinks

```
PATCH  /session-drinks/{id}/verdict       → SessionDrink        (body: {verdict: "liked"|"disliked"|"neutral"})
```

Note: uses `/session-drinks/{id}` not `/sessions/{session_id}/drinks/{id}` — the session
context is already encoded in the drink row and the frontend will always have the drink ID.

### Recommend

```
POST   /recommend    body: RecommendRequest  → Recommendation
```

Changes from v1:
- Uses the authenticated user's active bottles (not the hardcoded fixture).
- Companion IDs in the request must belong to the authenticated user (400 otherwise).
- On success: creates or reuses the current session, saves returned suggestions as
  `session_drinks`, records companion IDs in `session_companions`.
- Returns the `Recommendation` (same schema as v1); session ID returned in a
  `X-Session-Id` response header so the frontend can display drink cards with verdict buttons.

---

## RLS Policies

```sql
ALTER TABLE bottles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE companions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_companions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_drinks   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own bottles" ON bottles
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "own companions" ON companions
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "own preferences" ON companion_preferences
  FOR ALL USING (
    companion_id IN (SELECT id FROM companions WHERE user_id = auth.uid())
  );

CREATE POLICY "own sessions" ON sessions
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "own session_companions" ON session_companions
  FOR ALL USING (
    session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid())
  );

CREATE POLICY "own session_drinks" ON session_drinks
  FOR ALL USING (
    session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid())
  );
```

---

## `updated_at` trigger

Applied to `bottles` and `companions` only. `sessions` uses `ended_at` instead.
`companion_preferences` and `session_drinks` are append-only (no updates to track).

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bottles_updated_at
  BEFORE UPDATE ON bottles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER companions_updated_at
  BEFORE UPDATE ON companions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## Response shapes

### Bottle
```json
{"id": "uuid", "name": "Four Roses Small Batch", "category": "bourbon",
 "subcategory": null, "is_active": true, "created_at": "...", "updated_at": "..."}
```

### Companion (list view — no embedded preferences)
```json
{"id": "uuid", "name": "wife", "created_at": "...", "updated_at": "..."}
```

### Preference
```json
{"id": "uuid", "companion_id": "uuid", "type": "like", "value": "mezcal", "created_at": "..."}
```

### Session
```json
{"id": "uuid", "occasion": "movie night", "mood": "cozy",
 "created_at": "...", "ended_at": null, "companion_ids": ["uuid"]}
```

### SessionDrink
```json
{"id": "uuid", "session_id": "uuid", "name": "Boulevardier",
 "ingredients": [{"name": "Four Roses Small Batch", "quantity": "1.5 oz", "source": "inventory"}],
 "steps": ["Stir with ice", "Strain into coupe"],
 "why": "Spirit-forward and warming.",
 "verdict": null, "created_at": "..."}
```

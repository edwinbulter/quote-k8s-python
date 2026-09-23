# quote-k8s-python: Flask + HTMX + uv port of quote-k8-java

## Context

The user wants a new application, functionally and visually comparable to
`https://github.com/edwinbulter/quote-k8-java` (a Quarkus/Java + MongoDB backend with a
React/TypeScript SPA frontend), but built with **Python, Flask, and `uv`**, running in the
existing local **kind** cluster (`single-node`, context `kind-single-node`). Unlike the
Java original — which splits into a separate backend (`quote-api`) and frontend
(`quote-frontend`) container — the user explicitly wants the new app built as **one Flask +
HTMX monolith**: a single container serving server-rendered HTML (Jinja2 templates) with
HTMX for interactivity, replacing the React SPA + JSON REST API entirely. The database
does not need to be MongoDB — a lightweight embedded store (SQLite) is preferred, avoiding
a second pod. The whole thing lives in one git monorepo (app code, k8s manifests, scripts,
docs), mirroring the layout style of the reference repo.

The reference app was fully read (resources, services, models, k8s manifests, frontend
components, API contracts) directly from GitHub via `gh api` — see the file list at the
bottom. Key functionality to replicate: random quotes for anonymous visitors, sequential
per-user quote progress for authenticated users (auto-backfilling from the ZenQuotes API
when the pool runs low), like/unlike/reorder favourites, viewed-quote history with
delete-all, and admin screens for user-role management and quote management (search, sort,
paginate, force-fetch more quotes, stats). One known bug in the reference React app (the
User Management screen expects capitalized JSON field names the backend doesn't actually
send) will **not** be carried forward, since server-rendered Jinja has no such
serialization boundary to get wrong.

## Repository layout

```
quote-k8s-python/
├── .gitignore
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── .dockerignore
├── wsgi.py                        # gunicorn entrypoint
├── app/
│   ├── __init__.py                # create_app() factory
│   ├── config.py                  # Base/Dev/Test/Prod config via env vars
│   ├── extensions.py              # db = SQLAlchemy()
│   ├── models.py                  # Quote, User, UserRole, UserLike, UserProgress
│   ├── auth/
│   │   ├── routes.py              # register/login/logout/change-password/unregister
│   │   ├── decorators.py          # login_required, roles_required
│   │   └── seed.py                # dev-only POST /seed-users
│   ├── quotes/
│   │   ├── routes.py              # new/by-id/like/unlike, favourites strip
│   │   └── service.py             # random/sequential quote logic + progress tracking
│   ├── favourites/routes.py       # reorder / delete (Manage Favourites screen)
│   ├── viewed/routes.py           # toggle like, delete-all-viewed
│   ├── admin/
│   │   ├── routes.py              # users table/roles/delete, quotes table, fetch-zen, stats
│   │   └── service.py             # search/sort/paginate quotes, dedup-add from ZenQuotes
│   ├── pages/routes.py            # full-page routes (/, /login, /profile, /manage, /manage/*)
│   ├── services/zen_quotes.py     # requests-based ZenQuotes client
│   ├── health/routes.py           # /healthz
│   ├── templates/
│   │   ├── base.html              # shell: sidebar/button-bar, #toast-container, htmx script tag
│   │   ├── pages/                 # quote_view, auth_form, profile, management_menu,
│   │   │                          # manage_favourites, manage_viewed, user_management,
│   │   │                          # quote_management
│   │   └── partials/              # quote_card, favourites_strip, favourites_table/_row,
│   │                              # viewed_row, admin_users_table/_row, admin_quotes_table,
│   │                              # auth_form_fragment, toast
│   └── static/
│       ├── css/app.css            # hand-ported from the reference App.scss
│       └── js/app.js              # anon client-side quote nav, toast auto-dismiss
├── migrations/                    # Flask-Migrate/Alembic
├── k8s/
│   ├── namespace.yaml
│   ├── pvc.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── scripts/
│   ├── setup-kind.sh
│   └── teardown-kind.sh
├── doc/
│   ├── architecture.md
│   └── local-kind-setup.md
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_quotes.py
    ├── test_favourites.py
    ├── test_admin_users.py
    ├── test_admin_quotes.py
    └── test_health.py
```

## Data model (SQLAlchemy, `app/models.py`)

Five tables mirroring the Java version's five MongoDB collections field-for-field, adapted
to SQL:

- **`Quote`** — `quote_id` (PK, autoincrement), `quote_text`, `author`, `like_count`
  (default 0, denormalized counter kept in sync on like/unlike), `created_at`, `source`
  (`"Local"` / `"ZenQuotes"`). Indexes on `quote_text` and `author` for admin search.
- **`User`** — `username` (PK, natural key — matches how the Java collections reference
  users by username string rather than an ObjectId), `email` (unique), `password_hash`,
  `created_at`, `updated_at`, `is_active`.
- **`UserRole`** — `id` PK, `username` (FK), `role` (`ADMIN`/`USER`), `created_at`,
  `created_by`; `UNIQUE(username, role)` — a user can hold multiple role rows, grant/revoke
  stay idempotent (pre-check, matching `AuthService.updateUserRole`).
- **`UserLike`** — `id` PK, `username` (FK), `quote_id` (FK), `order` (int, user-reorderable),
  `liked_at`; `UNIQUE(username, quote_id)` for idempotent like/unlike.
- **`UserProgress`** — `username` (PK/FK), `last_quote_id`, `updated_at`.

## Backend design

- **App factory** (`create_app()`), Flask-SQLAlchemy + Flask-Migrate for schema management
  (the Mongo original was schemaless; SQL needs a migration story).
- **Blueprints**: `pages`, `auth`, `quotes`, `favourites`, `viewed`, `admin`, `health`.
- **Auth**: Flask signed-cookie sessions (`session["username"]` only) instead of the
  original's JWT-in-localStorage — appropriate now that a real browser talks to a
  server-rendered app rather than an SPA calling a JSON API. `before_request` loads
  `g.user`/`g.roles` from the DB each request (cheap at this scale, avoids stale-role bugs
  after a promotion). Password hashing via `werkzeug.security` (`pbkdf2:sha256`) replacing
  the original's custom salted-SHA256 — no migration needed since this is a fresh DB.
- **`login_required`/`roles_required(*roles)`** decorators in `app/auth/decorators.py`:
  redirect to `/login` normally, or send `HX-Redirect: /login` when the request came from
  HTMX (`HX-Request` header) so a partial-swap request still forces a full client redirect.
  This is the only place that branches on `HX-Request` — everywhere else uses a clean split
  instead (see below).
- **Fragment vs. full page — one consistent rule**: page-level routes (`/`, `/login`,
  `/profile`, `/manage`, `/manage/favourites`, `/manage/viewed`, `/manage/users`,
  `/manage/quotes`) always render a full page extending `base.html`; the sidebar nav uses
  `hx-boost="true"` so in-app navigation is swap-based without duplicating templates.
  Everything else (quote card, favourites strip, a single table row, a resorted table body,
  a toast) is served by its own dedicated fragment route, only ever invoked via
  `hx-get/post/put/delete`, never linked to directly — no route needs to guess whether it
  was hit via HTMX.
- **Toasts / cross-region updates**: a persistent `#toast-container` in `base.html`; fragment
  routes append `partials/toast.html` out-of-band (`hx-swap-oob="true"`). Actions that must
  update two DOM regions in one round trip (e.g. liking a quote updates both the quote card
  and the favourites strip) render both, the second tagged OOB — this replaces the original
  React app's optimistic-update-then-rollback pattern, since the response already reflects
  true post-write state.
- **Destructive actions** (delete-all-viewed, delete favourite, delete user) use
  `hx-confirm="..."` directly on the button instead of custom JS confirm dialogs.
- **Debounced admin search**: `hx-trigger="keyup changed delay:400ms, search"` with
  `hx-push-url="true"` so the query string (search/sort/page) stays bookmarkable, replacing
  React state with the URL as source of truth.
- **Anonymous quote navigation** (Previous/Next/First/Last for logged-out users) is handled
  entirely client-side in `app/static/js/app.js`, maintaining a small in-memory array of
  quotes seen this session (matches the original's array-based nav for anon users);
  `POST /quote/new` receives the accumulated excluded-ids via `hx-vals` so the server never
  repeats a quote within the session.

### Route table (method, path, auth, purpose)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | — | Main quote view |
| GET | `/login` | — | Login/Register form |
| GET | `/profile` | login | Profile screen |
| GET | `/manage` | login | Management menu |
| GET | `/manage/favourites` | login | My Favourites page |
| GET | `/manage/viewed` | login | My Viewed Quotes page |
| GET | `/manage/users` | ADMIN | User Management page |
| GET | `/manage/quotes` | ADMIN | Manage Quotes page |
| GET | `/healthz` | — | Liveness/readiness probe |
| POST | `/auth/register` | — | Register (default role USER) |
| POST | `/auth/login` | — | Login (username or email) |
| POST | `/auth/logout` | login | Logout |
| POST | `/auth/change-password` | login | Self-service password change |
| POST | `/auth/unregister` | login | Delete own account (password-verified, cascades) |
| POST | `/seed-users` | — (dev-flag gated) | Seed `admin`/`user-1` demo accounts |
| POST | `/quote/new` | — | New quote (random+exclusions anon / sequential-next authed) |
| GET | `/quote/<id>` | login | Re-fetch by id for Previous/Next/First/Last (authed) |
| POST | `/quote/<id>/like` | login | Idempotent like; quote-card + OOB favourites-strip |
| DELETE | `/quote/<id>/unlike` | login | Idempotent unlike; quote-card + OOB favourites-strip |
| GET | `/favourites/strip` | login | Refresh favourites quick-view strip |
| PUT | `/favourites/<id>/reorder` | login | Move up/down; swaps neighbor order |
| DELETE | `/favourites/<id>` | login | Unlike from Manage Favourites |
| POST | `/viewed/<id>/toggle-like` | login | ❤️/🤍 toggle from Viewed Quotes table |
| POST | `/viewed/delete-all` | login | Deletes all likes, resets progress to 0 |
| GET | `/admin/users/table` | ADMIN | Users table fragment |
| POST | `/admin/users/<username>/roles/<role>` | ADMIN | Grant role (idempotent) |
| DELETE | `/admin/users/<username>/roles/<role>` | ADMIN | Revoke role (blocked for own ADMIN) |
| DELETE | `/admin/users/<username>` | ADMIN | Delete another user, cascades (blocked for self) |
| GET | `/admin/quotes/table` | ADMIN | Paginated/sorted/searchable quotes table + stats |
| POST | `/admin/quotes/fetch-zen` | ADMIN | Force-fetch from ZenQuotes, dedup text+author |

### ZenQuotes integration (`app/services/zen_quotes.py`)

Plain `requests`-based module, `fetch_many(timeout=5, retries=2)` hitting
`https://zenquotes.io/api/random` and `https://zenquotes.io/api/quotes`, returning `[]` on
any failure (never raises) so quote serving degrades gracefully — matches
`ZenQuotesService.java`. Triggered when `max(quote_id) < 5`, the next needed sequential id
exceeds the max, or (anon) the exclusion set exhausts the pool. Dedup rule differs
intentionally by call site, matching the Java original: quote-serving dedupes by exact
`quote_text`; the admin "Add Quotes from ZEN" action dedupes by `quote_text` **and**
`author`, case-insensitive.

## Dependencies & running (`pyproject.toml`, `uv`)

Runtime: `flask`, `flask-sqlalchemy`, `flask-migrate`, `requests`, `gunicorn`,
`python-dotenv` (dev-only `.env` loading). Dev group: `pytest`, `pytest-cov`, `ruff`.

- Dev: `uv sync`, then `uv run flask --app app:create_app run --debug --port 5000`.
- Tests: `uv run pytest`.
- Container: `uv run gunicorn -w 1 --threads 4 --worker-class gthread -b 0.0.0.0:8080 wsgi:app`.

**SQLite concurrency**: run gunicorn with a **single worker process, multiple threads**
(`--workers 1 --threads 4 --worker-class gthread`) — multiple worker *processes* would
contend for the same SQLite file lock. One pod replica is already the natural ceiling for a
file-backed DB, so this isn't a scaling regression. Enable WAL mode + a busy timeout at
startup for extra headroom under brief contention.

## Dockerfile

Multi-stage, `python:3.12-slim` + the `uv` static binary copied from
`ghcr.io/astral-sh/uv`: `uv sync --frozen --no-dev --no-install-project` (deps layer, cached
separately from source) then `uv sync --frozen --no-dev` again after copying `app/`/`wsgi.py`
(standard uv Docker layering). Runtime stage runs as a non-root user, `EXPOSE 8080`, `CMD`
runs gunicorn as above.

## Kubernetes manifests (`k8s/`)

Namespace: **`quote-k8s-python`**. One Deployment/Service/Ingress for the whole app — no
more `/api` vs `/` path-splitting since there's only one container.

- `namespace.yaml`
- `pvc.yaml` — `quote-data-pvc`, `ReadWriteOnce`, ~1Gi, backing the SQLite file.
- `deployment.yaml` — `quote-app`, `replicas: 1`, `imagePullPolicy: Never`, env `SECRET_KEY`
  from a Secret, env `DATABASE_PATH=/data/quotes.db`, PVC mounted at `/data`,
  liveness/readiness probes on `GET /healthz:8080`.
- `service.yaml` — ClusterIP, port 80 → targetPort 8080.
- `ingress.yaml` — single rule, path `/` → `quote-app-service:80`.

No `secret.yaml` is committed. `SECRET_KEY` is created **imperatively** by
`scripts/setup-kind.sh` (`openssl rand -base64 32` piped into
`kubectl create secret generic ... --dry-run=client -o yaml | kubectl apply -f -`) —
simpler than the Java original's gitignored JWK file, at the cost of rotating (and thus
invalidating open sessions) on every setup rerun, which is fine for a local dev cluster.

### `scripts/setup-kind.sh`

Mirrors the Java original's flow: verify the `single-node` cluster exists → ensure
ingress-nginx is installed (idempotent check-then-apply) → `docker build` the image →
`kind load docker-image` → apply namespace + PVC → create/update the session secret →
apply deployment/service/ingress → `kubectl rollout status` wait → seed demo accounts via a
retrying `curl -X POST http://localhost/seed-users` loop → print pod status, the URL, and
demo credentials (`admin`/`Admin123!`, `user-1`/`Hello-user-1`).

### `scripts/teardown-kind.sh`

`kubectl delete namespace quote-k8s-python --wait=true` (cascades everything including the
PVC and secret); leaves the shared `ingress-nginx` controller in place, same as the Java
original.

The dev-only `/seed-users` route must be gated by an env flag (`SEED_USERS_ENABLED`,
default on for the kind Deployment) and documented as unsafe to expose on any
production-facing deployment — same caveat the Java version calls out.

## Styling

Hand-port `quote-frontend/src/App.scss`'s visual language into a single
`app/static/css/app.css` (no bundler/Sass step needed): CSS custom properties instead of
SCSS variables, the same left sidebar with "CODE-BULTER" logo header + green "Quote"
wordmark, centered quote card, green pill buttons with a disabled state, circular green
user-initial avatar. Deliberate deviation: replace the original's per-button
`position: absolute` placement with a flex column layout, since buttons here are
conditionally rendered server-side (not always-rendered-but-disabled), which would leave
gaps under absolute positioning. Preserve the two responsive breakpoints (768px/480px) as
plain `@media` blocks.

## Testing

`tests/conftest.py` builds the app against an in-memory SQLite DB (`StaticPool`,
`check_same_thread=False`) with a `login_as(client, user, pw)` helper. Cover:

- **Auth**: register success/mismatch/duplicate-username/duplicate-email; login by
  username/email, wrong password, inactive account; logout clears session.
- **Quotes**: anon `/quote/new` never repeats an excluded id; authed `/quote/new` advances
  `last_quote_id` by one, skipping missing ids; `GET /quote/<id>` for id < last_quote_id
  does not advance progress; low-pool/exhausted-pool triggers a (mocked) ZenQuotes fetch.
- **Likes/reorder**: double-like and double-unlike are no-ops; first like gets `order=1`;
  reorder swaps exactly the two neighboring `order` values.
- **Admin**: idempotent role grant; self-demotion from ADMIN blocked; self-deletion blocked;
  deleting another user cascades (likes/progress/roles/account all removed); quote search is
  case-insensitive substring match; sort by id/quotetext/author supports asc/desc, sort by
  likes is desc-only; page-size variants return correct slices.
- **Seeding**: idempotent; re-seed recreates `admin` fresh but skips existing `user-1`
  (matches `UserSeeder.java`'s asymmetric behavior); 404 when the dev flag is off.
- **Health**: `/healthz` returns 200 with DB reachable.

### Manual end-to-end verification (after `./scripts/setup-kind.sh`)

1. `curl -i http://localhost/healthz` → 200.
2. Load `http://localhost/`: "New Quote" cycles with no repeats while anonymous.
3. Log in as `admin`/`Admin123!`: Next/Previous/First/Last become sequential and persist
   across reloads; liking a quote updates the favourites strip without a full reload.
4. Manage → My Favourites: reorder (ends disabled correctly), delete with toast feedback.
5. Manage → My Viewed Quotes: toggle like; Delete All (confirm dialog fires), verify
   progress resets to 0 and the next quote starts at #1.
6. Manage → User Management: toggle USER/ADMIN on `user-1`; confirm self-demotion and
   self-deletion are blocked; delete a scratch user and confirm cascade.
7. Manage → Manage Quotes: search, sort (Likes column descending-only), page size,
   pagination, and "Add Quotes from ZEN" (toast reports count added).
8. Log in as `user-1`/`Hello-user-1`: confirm User Management / Manage Quotes menu items
   are disabled with a role-requirement tooltip.
9. `./scripts/teardown-kind.sh`, then confirm
   `kubectl get namespace quote-k8s-python --context kind-single-node` is NotFound while
   `ingress-nginx` remains installed.

## Reference material consulted

Fetched directly from `github.com/edwinbulter/quote-k8-java` via `gh api` (repo not present
locally): `doc/architecture.md`, `doc/local-kind-setup.md`, `CLAUDE.md`, all of
`quote-api/src/main/java/com/quote/k8/{resource,service,model,util}/*.java`,
`quote-api/src/main/resources/application.properties`, all of `k8s/local/**`,
`scripts/{setup-kind,teardown-kind}.sh`, and the frontend's `App.tsx`, `App.scss`
(referenced, not fetched verbatim), `constants.tsx`, `api/{authApi,quoteApi,adminApi}.ts`,
`contexts/AzureAuthContext.tsx`, `components/{AzureLogin,Login,FavouritesComponent,
ManagementScreen,ManageFavouritesScreen,ViewedQuotesScreen,UserManagementScreen,
QuoteManagementScreen}.tsx`, `package.json`, `nginx.conf`, `Dockerfile`.

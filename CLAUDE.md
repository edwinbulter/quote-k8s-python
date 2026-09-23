# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project overview

`quote-k8s-python` is a Flask + HTMX quote-browsing app, packaged as a single
monolithic container (server-rendered Jinja2 templates, HTMX for AJAX partial
swaps, SQLite for storage) and deployed into a local kind cluster. It is a
from-scratch Python port of the backend logic and UI functionality of
[quote-k8-java](https://github.com/edwinbulter/quote-k8-java) (Quarkus/Java +
MongoDB backend + React SPA), deliberately collapsed into one process instead
of a separate API + SPA.

For the full architecture (components, data model, route table, auth flow) see
**`doc/architecture.md`** - read it before making non-trivial changes.

## Commands

```bash
uv sync                                              # install dependencies
uv run flask --app app:create_app run --debug --port 5000   # dev server, live reload
uv run pytest                                        # run tests
uv run pytest --cov=app                              # with coverage
uv run ruff check .                                  # lint
```

Dev mode uses a file-backed SQLite DB at `instance/quotes.db` (Flask's default
instance-relative resolution for a relative `SQLALCHEMY_DATABASE_URI`) unless
`DATABASE_PATH` is set to an absolute path.

Docker image build:
```bash
docker build -t quote-app:latest .
```

### Local kind deployment

Full walkthrough in `doc/local-kind-setup.md`; the short version, from repo root:

```bash
./scripts/setup-kind.sh      # builds the image, loads it into kind, deploys everything, seeds admin/user-1
./scripts/teardown-kind.sh   # removes the quote-k8s-python namespace (cluster + ingress-nginx untouched)
```

Check status with `kubectl get pods -n quote-k8s-python --context=kind-single-node`.
The app is then reachable at `http://localhost/`.

## Gotchas

- **`POST /seed-users`** is an unauthenticated dev-only endpoint that seeds
  `admin`/`Admin123!` and `user-1`/`Hello-user-1`. It's gated by the
  `SEED_USERS_ENABLED` env var (defaults on) so it can be disabled outright
  for anything production-facing - it is not otherwise access-controlled.
- **SQLite + gunicorn**: the container runs gunicorn with `--workers 1
  --threads 4 --worker-class gthread`. Do not raise `--workers` above 1 -
  multiple worker *processes* would contend for the same SQLite file lock.
  One pod replica is already the natural ceiling for a file-backed DB.
- **`SECRET_KEY`** (Flask session signing) is generated fresh by
  `scripts/setup-kind.sh` on every run via `kubectl create secret` - it is
  never committed to git. This means every `setup-kind.sh` rerun invalidates
  existing browser sessions; fine for a local dev cluster.
- The local kind cluster is named `single-node` (kubectl context
  `kind-single-node`).
- The admin `User Management` screen's field names (username/email/roles/...)
  are consistent end-to-end since this is server-rendered Jinja, not a
  separate JSON API consumed by a JS client - there is no serialization
  boundary where a field-name mismatch bug (as existed in the reference
  React app) could be reintroduced. Keep it that way: avoid adding a
  parallel JSON API surface with its own, possibly drifting, field names.

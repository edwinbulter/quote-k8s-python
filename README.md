# quote-k8s-python

A Python/Flask + HTMX port of [quote-k8-java](https://github.com/edwinbulter/quote-k8-java):
a quote-browsing app with per-user favourites, viewed-quote history, and admin
screens for user and quote management, running in a local
[kind](https://kind.sigs.k8s.io/) Kubernetes cluster.

Unlike the Java original (a separate Quarkus API + React SPA + MongoDB), this
version is a **single Flask monolith**: server-rendered HTML (Jinja2) with
[HTMX](https://htmx.org/) for interactivity, backed by SQLite on a PVC. One
container, one pod, one Deployment.

## Project structure

- `app/` - the Flask application (blueprints, models, templates, static assets)
- `k8s/` - Kubernetes manifests for the local kind cluster
- `scripts/` - setup/teardown scripts for the kind cluster
- `doc/` - architecture and setup documentation
- `tests/` - pytest suite

## Getting started

See the documentation in `doc/`:

- [`doc/architecture.md`](doc/architecture.md) - components, data model, routes, auth
- [`doc/local-kind-setup.md`](doc/local-kind-setup.md) - build and run in the local kind cluster
- [`doc/new-quote-flow.md`](doc/new-quote-flow.md) - a detailed request/response
  trace of what happens when a logged-in user clicks "New Quote" (also available
  in [Dutch](doc/new-quote-flow.nl.md))

### Local development (no Kubernetes)

```bash
uv sync
uv run flask --app app:create_app run --debug --port 5001
```

Then open http://localhost:5001/.

> Port 5001, not 5000: on macOS, port 5000 is usually already taken by the
> AirPlay Receiver (`ControlCenter`), which answers HTTP requests with a bare
> `403 Forbidden`. If you hit that, either use a different port (as above) or
> disable AirPlay Receiver under System Settings > General > AirDrop & Handoff.

A fresh database has no user accounts yet, so logging in as `admin` or
`user-1` will fail until you seed them:

```bash
curl -X POST http://localhost:5001/seed-users
```

This creates `admin`/`Admin123!` (ADMIN role) and `user-1`/`Hello-user-1`
(USER role); it's safe to call again later, it skips users that already
exist. The kind deployment does this automatically as the last step of
`scripts/setup-kind.sh` - only local dev requires the manual call.

### Tests

```bash
uv run pytest
```

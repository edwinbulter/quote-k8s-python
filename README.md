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

### Local development (no Kubernetes)

```bash
uv sync
uv run flask --app app:create_app run --debug --port 5000
```

Then open http://localhost:5000/.

### Tests

```bash
uv run pytest
```

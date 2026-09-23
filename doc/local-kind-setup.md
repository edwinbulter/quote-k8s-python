# Local Setup: kind Cluster `single-node`

Quick day-to-day workflow for building the app and running it in the local
`single-node` kind cluster (context `kind-single-node`). Two scripts install
or remove everything in one command.

See [`architecture.md`](architecture.md) for how the app fits together, and
[`test-api.http`](test-api.http) (with [`http-client.env.json`](http-client.env.json))
for a ready-made set of manual requests against every route - open it in an
IDE with an HTTP client (IntelliJ/PyCharm's built-in client, or the VS Code
"REST Client" extension) and pick the `local-dev` or `local-k8` environment.

## Prerequisites

- Docker
- A kind cluster named `single-node` already running, with kubectl context `kind-single-node`
- kubectl
- `uv` (only needed for local dev outside the cluster / running tests)

Verify the cluster is up:

```bash
kind get clusters
kubectl config get-contexts kind-single-node
```

## Step 1: Install everything

```bash
./scripts/setup-kind.sh
```

This script:
- Verifies the `single-node` kind cluster exists
- Installs the NGINX ingress controller if it isn't already present
- Builds the `quote-app:latest` Docker image and loads it into the kind cluster
- Applies the `quote-k8s-python` namespace and the SQLite data PVC
- Generates a fresh Flask session-signing key and creates/updates it as the
  `quote-session-secret` Secret (safe to rerun - each run rotates the key,
  which signs everyone out, which is fine for local dev)
- Applies the Deployment, Service, and Ingress
- Waits for the Deployment to become ready
- Seeds the `admin`/`user-1` demo accounts by calling `POST /seed-users`
  (safe to run repeatedly - it skips users that already exist)

Check progress at any time with:

```bash
kubectl get pods -n quote-k8s-python --context=kind-single-node
```

## Step 2: Try it out

```bash
curl -i http://localhost/healthz
```

Or open `http://localhost/` in a browser. Port 80 on the kind node is already
mapped to `localhost` on the host, so no port-forwarding is needed.

Log in with one of the accounts seeded in Step 1 (the login field accepts
either username or email):

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin123!` | ADMIN |
| `user-1` | `Hello-user-1` | USER |

## Step 3: Remove everything

```bash
./scripts/teardown-kind.sh
```

This deletes the `quote-k8s-python` namespace, which cascades to the
Deployment, Service, Ingress, PVC, and Secret created in Step 1. It does
**not** delete the kind cluster itself or the shared ingress-nginx
controller - rerun Step 1 any time to reinstall.

## Manual verification checklist

1. `curl -i http://localhost/healthz` -> `200`.
2. Load `http://localhost/`: "New Quote" cycles with no repeats while
   anonymous.
3. Log in as `admin`/`Admin123!`: Next/Previous/First/Last become sequential
   and persist across reloads; liking a quote updates the favourites strip
   without a full reload.
4. Manage -> My Favourites: reorder (ends disabled correctly), delete with
   toast feedback.
5. Manage -> My Viewed Quotes: toggle like; Delete All (confirm dialog
   fires), verify progress resets to 0 and the next quote starts at #1.
6. Manage -> User Management: toggle USER/ADMIN on `user-1`; confirm
   self-demotion and self-deletion are blocked; delete a scratch user and
   confirm cascade.
7. Manage -> Manage Quotes: search, sort (Likes column descending-only),
   page size, pagination, and "Add Quotes from ZEN" (toast reports count
   added).
8. Log in as `user-1`/`Hello-user-1`: confirm User Management / Manage
   Quotes menu items are disabled with a role-requirement tooltip.

## Troubleshooting

```bash
# Pod status
kubectl get pods -n quote-k8s-python --context=kind-single-node

# Logs
kubectl logs -l app=quote-app -n quote-k8s-python --context=kind-single-node -f

# Pod events
kubectl describe pod <pod-name> -n quote-k8s-python --context=kind-single-node
```

If a pod is stuck in `ImagePullBackOff` for `quote-app:latest`, the image
wasn't loaded into the cluster - redo the `docker build` +
`kind load docker-image` steps (or just rerun `scripts/setup-kind.sh`).

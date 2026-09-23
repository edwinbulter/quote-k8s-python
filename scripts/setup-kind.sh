#!/bin/bash

set -e

# Change to project root directory
cd "$(dirname "$0")/.."

CLUSTER_NAME="single-node"
CONTEXT="kind-${CLUSTER_NAME}"
NAMESPACE="quote-k8s-python"
IMAGE="quote-app:latest"

echo "=========================================="
echo "Installing quote-k8s-python into kind cluster '${CLUSTER_NAME}'"
echo "=========================================="
echo ""

# Check the kind cluster exists
if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
    echo "ERROR: kind cluster '$CLUSTER_NAME' not found"
    echo "Create it first, e.g.: kind create cluster --name $CLUSTER_NAME"
    exit 1
fi
echo "✓ kind cluster '$CLUSTER_NAME' found"
echo ""

# Ensure the NGINX ingress controller is installed in this cluster
if ! kubectl --context="$CONTEXT" get namespace ingress-nginx &> /dev/null; then
    echo "Installing NGINX ingress controller..."
    kubectl apply --context="$CONTEXT" -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml
    echo "Waiting for ingress controller to be ready..."
    kubectl wait --context="$CONTEXT" --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=90s
    echo "✓ Ingress controller installed"
else
    echo "✓ Ingress controller already installed"
fi
echo ""

# Build and load the image into the cluster
echo "Building Docker image..."
docker build -t "$IMAGE" .
echo "Loading image into kind cluster..."
kind load docker-image "$IMAGE" --name "$CLUSTER_NAME"
echo "✓ Image built and loaded"
echo ""

# Create namespace and PVC
echo "Applying namespace and PVC..."
kubectl apply --context="$CONTEXT" -f k8s/namespace.yaml
kubectl apply --context="$CONTEXT" -f k8s/pvc.yaml
echo "✓ Namespace and PVC applied"
echo ""

# Create/update the Flask session-signing secret. Generated fresh on every
# run rather than committed to git - simpler than a gitignored key file,
# at the cost of invalidating open browser sessions on each rerun, which is
# fine for a local dev cluster.
echo "Creating session secret..."
SECRET_KEY=$(openssl rand -base64 32)
kubectl create secret generic quote-session-secret \
    --from-literal=SECRET_KEY="$SECRET_KEY" \
    -n "$NAMESPACE" --context="$CONTEXT" \
    --dry-run=client -o yaml | kubectl apply --context="$CONTEXT" -f -
echo "✓ Session secret applied"
echo ""

# Deploy the app
echo "Applying deployment, service, and ingress..."
kubectl apply --context="$CONTEXT" \
    -f k8s/deployment.yaml \
    -f k8s/service.yaml \
    -f k8s/ingress.yaml
echo "✓ Deployment, service, and ingress applied"
echo ""

# Wait for rollout
echo "Waiting for deployment to become ready..."
kubectl rollout status deployment/quote-app -n "$NAMESPACE" --context="$CONTEXT" --timeout=120s
echo ""

# Seed the admin/user-1 accounts (safe to call repeatedly - the seeder skips users that already exist)
echo "Seeding admin/user-1 accounts..."
SEED_OK=false
for i in $(seq 1 10); do
    if curl -sf -X POST http://localhost/seed-users > /dev/null; then
        SEED_OK=true
        break
    fi
    sleep 2
done
if [ "$SEED_OK" = true ]; then
    echo "✓ Users seeded (admin/Admin123!, user-1/Hello-user-1)"
else
    echo "WARNING: could not reach http://localhost/seed-users - seed manually with:"
    echo "  curl -X POST http://localhost/seed-users"
fi
echo ""

echo "=========================================="
echo "✓ Setup complete"
echo "=========================================="
echo ""
kubectl get pods -n "$NAMESPACE" --context="$CONTEXT"
echo ""
echo "App:   http://localhost/"
echo "Login: admin / Admin123!  (or user-1 / Hello-user-1)"

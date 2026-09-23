#!/bin/bash

set -e

cd "$(dirname "$0")/.."

CLUSTER_NAME="single-node"
CONTEXT="kind-${CLUSTER_NAME}"
NAMESPACE="quote-k8s-python"

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
    echo "ERROR: kind cluster '$CLUSTER_NAME' not found"
    exit 1
fi

echo "Deleting namespace '$NAMESPACE' (cascades Deployment/Service/Ingress/PVC/Secret)..."
kubectl delete namespace "$NAMESPACE" --context="$CONTEXT" --ignore-not-found=true --wait=true
echo "✓ Namespace deleted"
echo ""
echo "Note: the shared ingress-nginx controller was left in place."
echo "Rerun scripts/setup-kind.sh at any time to reinstall the app."

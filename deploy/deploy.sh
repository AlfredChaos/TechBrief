#!/usr/bin/env bash
# ============================================================
# TechBrief — One-click Kubernetes deployment script
# ============================================================
# Usage:
#   bash deploy/deploy.sh [OPTIONS]
#
# Options:
#   --registry REGISTRY    Container registry (e.g. ghcr.io/org)
#   --tag TAG              Image tag (default: git SHA or "latest")
#   --namespace NS         Kubernetes namespace (default: techbrief)
#   --skip-build           Skip Docker build & push
#   --dry-run              Print commands without executing
#   --help                 Show this help
# ============================================================
set -euo pipefail

# Defaults
REGISTRY="${REGISTRY:-}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
NAMESPACE="${NAMESPACE:-techbrief}"
SKIP_BUILD=false
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)   REGISTRY="$2"; shift 2 ;;
    --tag)        TAG="$2"; shift 2 ;;
    --namespace)  NAMESPACE="$2"; shift 2 ;;
    --skip-build) SKIP_BUILD=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --help|-h)
      head -15 "$0" | tail -12
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Derived values
IMAGE_NAME="techbrief-app"
if [[ -n "$REGISTRY" ]]; then
  FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"
else
  FULL_IMAGE="${IMAGE_NAME}:${TAG}"
fi

# Helper: run or dry-run
run() {
  if $DRY_RUN; then
    echo "[DRY-RUN] $*"
  else
    echo "[RUN] $*"
    "$@"
  fi
}

echo "============================================"
echo " TechBrief K8s Deployment"
echo "============================================"
echo " Image:      ${FULL_IMAGE}"
echo " Namespace:  ${NAMESPACE}"
echo " Skip build: ${SKIP_BUILD}"
echo " Dry run:    ${DRY_RUN}"
echo "============================================"
echo

# ---------- Step 1: Build & Push ----------
if ! $SKIP_BUILD; then
  echo ">>> Step 1: Building Docker image..."
  run docker build -t "$FULL_IMAGE" "$PROJECT_DIR"

  if [[ -n "$REGISTRY" ]]; then
    echo ">>> Step 1b: Pushing to registry..."
    run docker push "$FULL_IMAGE"
  fi
else
  echo ">>> Step 1: Skipping build (--skip-build)"
fi

echo

# ---------- Step 2: Check secrets ----------
SECRETS_FILE="${PROJECT_DIR}/deploy/k8s/secrets.yaml"
if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "WARNING: deploy/k8s/secrets.yaml not found!"
  echo "Copy deploy/k8s/secrets.yaml.template to deploy/k8s/secrets.yaml and fill in values."
  if ! $DRY_RUN; then
    exit 1
  fi
fi

# ---------- Step 3: Apply K8s manifests ----------
echo ">>> Step 2: Applying Kubernetes manifests..."

# Update image tag in deployments (using sed for portability)
MANIFESTS=(
  "${PROJECT_DIR}/deploy/k8s/deployment-web.yaml"
  "${PROJECT_DIR}/deploy/k8s/deployment-worker.yaml"
  "${PROJECT_DIR}/deploy/k8s/deployment-beat.yaml"
)

for manifest in "${MANIFESTS[@]}"; do
  if $DRY_RUN; then
    echo "[DRY-RUN] sed -i 's|techbrief-app:latest|${FULL_IMAGE}|g' $manifest"
  else
    sed -i "s|techbrief-app:latest|${FULL_IMAGE}|g" "$manifest"
  fi
done

# Apply in order
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/namespace.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/configmap.yaml"

if [[ -f "$SECRETS_FILE" ]]; then
  run kubectl apply -f "$SECRETS_FILE"
fi

run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/deployment-web.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/deployment-worker.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/deployment-beat.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/service.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/ingress.yaml"
run kubectl apply -f "${PROJECT_DIR}/deploy/k8s/hpa.yaml"

echo

# ---------- Step 4: Wait for rollout ----------
if ! $DRY_RUN; then
  echo ">>> Step 3: Waiting for rollout to complete..."
  kubectl rollout status deployment/techbrief-web -n "$NAMESPACE" --timeout=180s
  kubectl rollout status deployment/techbrief-worker -n "$NAMESPACE" --timeout=120s
  kubectl rollout status deployment/techbrief-beat -n "$NAMESPACE" --timeout=60s
else
  echo "[DRY-RUN] kubectl rollout status deployment/techbrief-web -n $NAMESPACE"
fi

echo

# ---------- Step 5: Smoke test ----------
if ! $DRY_RUN; then
  echo ">>> Step 4: Running smoke test..."
  POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=web -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

  if [[ -n "$POD_NAME" ]]; then
    echo "  Pod: $POD_NAME"
    HEALTH=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- curl -sf http://localhost:8010/health/live/ 2>/dev/null || echo "FAILED")
    echo "  Health: $HEALTH"
  else
    echo "  No web pod found yet. Check manually with: kubectl get pods -n $NAMESPACE"
  fi
else
  echo "[DRY-RUN] Smoke test: curl http://localhost:8010/health/live/"
fi

echo
echo "============================================"
echo " Deployment complete!"
echo "============================================"
echo " Check status:"
echo "   kubectl get pods -n $NAMESPACE"
echo "   kubectl get ingress -n $NAMESPACE"
echo ""
echo " Port-forward for local testing:"
echo "   kubectl port-forward svc/techbrief-web 8010:80 -n $NAMESPACE"
echo "============================================"

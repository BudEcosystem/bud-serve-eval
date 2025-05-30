#!/bin/bash
# Cleanup old eval-datasets volume with hostPath

echo "Cleaning up old eval-datasets volume..."

# Delete PVC
kubectl delete pvc eval-datasets-pvc -n budeval --ignore-not-found=true

# Delete PV
kubectl delete pv eval-datasets --ignore-not-found=true

echo "Cleanup completed. The new volume will be created on app startup."
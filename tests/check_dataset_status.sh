#!/bin/bash

echo "=== Checking Dataset Download Status ==="
echo

# Create a temporary pod to check the volume
kubectl run dataset-check-temp -n budeval --rm -i --restart=Never \
  --image=busybox \
  -- sh -c '
    echo "Checking dataset status..."
    if [ -f /data/dataset_initialized ]; then
      echo "✅ Dataset is DOWNLOADED and INITIALIZED"
      echo "Initialization timestamp:"
      cat /data/dataset_initialized
      echo -e "\nDataset contents:"
      ls -la /data/ | head -20
      echo -e "\nTotal size:"
      du -sh /data/
    else
      echo "❌ Dataset NOT initialized yet"
      echo "Current contents of /data:"
      ls -la /data/
      if [ -f /data/OpenCompassData-complete-20240207.zip ]; then
        echo -e "\n⏳ Download in progress..."
        ls -lh /data/OpenCompassData-complete-20240207.zip
      fi
    fi
  ' \
  --overrides='{"spec":{"containers":[{"name":"dataset-check-temp","volumeMounts":[{"name":"data","mountPath":"/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"eval-datasets-pvc"}}]}}'
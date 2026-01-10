#!/bin/sh
# Script to generate file service discovery targets for Promtail
# This runs as a sidecar container and generates /etc/promtail/pod-logs.json

while true; do
  # Find all log files and generate targets
  find /var/log/pods -name "*.log" -type f | while read logfile; do
    # Skip system namespaces
    if echo "$logfile" | grep -qE "(kube-system|kube-public|kube-node-lease)"; then
      continue
    fi
    
    # Extract namespace, pod name, container from path
    # Format: /var/log/pods/namespace_podname_uid/containername/restartcount.log
    dir=$(dirname "$logfile")
    container=$(basename "$dir")
    pod_dir=$(dirname "$dir")
    pod_info=$(basename "$pod_dir")
    
    echo "{\"targets\":[\"localhost\"],\"labels\":{\"__path__\":\"$logfile\",\"container\":\"$container\"}}"
  done | jq -s '.' > /etc/promtail/pod-logs.json.tmp
  
  # Atomic move
  mv /etc/promtail/pod-logs.json.tmp /etc/promtail/pod-logs.json
  
  sleep 10
done

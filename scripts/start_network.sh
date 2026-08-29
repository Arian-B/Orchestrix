#!/bin/bash

PROJECT_DIR="/mnt/d/SDN-Server-Failover"

cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo " SDN SERVER FAILOVER MININET TOPOLOGY"
echo "=========================================="
echo ""
echo "Starting topology..."
echo ""

sudo python3 topology/failover_topology.py

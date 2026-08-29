#!/bin/bash

PROJECT_DIR="/mnt/d/SDN-Server-Failover"

cd "$PROJECT_DIR" || exit 1

source "$PROJECT_DIR/ryu-venv/bin/activate"

echo "=========================================="
echo " SDN SERVER FAILOVER CONTROLLER"
echo "=========================================="
echo ""
echo "Starting RYU..."
echo ""

ryu-manager controller/failover_controller.py

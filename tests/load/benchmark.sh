#!/bin/bash
set -e

# Create results directory if it doesn't exist
mkdir -p "$(dirname "$0")/results"

echo "Running Locust Load Test..."
locust -f "$(dirname "$0")/locustfile.py" --headless -u 50 -r 5 -t 60s --host=http://localhost:8080 --csv="$(dirname "$0")/results/locust_results"

echo "Load tests completed successfully. Results saved in tests/load/results/"

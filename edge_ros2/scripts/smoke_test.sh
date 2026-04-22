#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# smoke_test.sh — End-to-end smoke test (native ROS2, no Docker)
#
# Run after starting the stack: bash scripts/start.sh all
# Then in another terminal:    bash scripts/smoke_test.sh
#
# Checks:
#   1. All 7 ROS2 nodes are running
#   2. Key topics are publishing messages
#   3. MQTT broker is reachable
#   4. Violations directory is writable
#   5. System health (CPU temp, memory)
# ─────────────────────────────────────────────────────────────────────────────
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} $label"
        PASS=$((PASS+1))
    else
        echo -e "${RED}[FAIL]${NC} $label"
        FAIL=$((FAIL+1))
    fi
}

echo "=============================================="
echo " Footwatch Edge — Smoke Test (Native ROS2)"
echo "=============================================="

# Source ROS2
source /opt/ros/humble/setup.bash 2>/dev/null || true
if [ -f "$PROJECT_ROOT/ros2_ws/install/setup.bash" ]; then
    source "$PROJECT_ROOT/ros2_ws/install/setup.bash"
fi

echo ""
echo "── Node presence checks ──────────────────────"

check "fw_sensor_bridge running" \
    "ros2 node list | grep -q fw_sensor_bridge"

check "fw_inference_node running" \
    "ros2 node list | grep -q fw_inference_node"

check "fw_tracking_speed_node running" \
    "ros2 node list | grep -q fw_tracking_speed_node"

check "fw_plate_ocr_node running" \
    "ros2 node list | grep -q fw_plate_ocr_node"

check "fw_violation_aggregator running" \
    "ros2 node list | grep -q fw_violation_aggregator"

check "fw_ros2_mqtt_bridge running" \
    "ros2 node list | grep -q fw_ros2_mqtt_bridge"

check "fw_health_node running" \
    "ros2 node list | grep -q fw_health_node"

echo ""
echo "── Topic message flow checks ────────────────"

check "/fw/camera/frame publishes" \
    "timeout 8 ros2 topic hz /fw/camera/frame 2>&1 | grep -q 'average rate'"

check "/fw/detect/twowheeler publishes" \
    "timeout 8 ros2 topic hz /fw/detect/twowheeler 2>&1 | grep -q 'average rate'"

check "/fw/track/speed publishes" \
    "timeout 8 ros2 topic hz /fw/track/speed 2>&1 | grep -q 'average rate'"

check "/fw/health/runtime publishes" \
    "timeout 15 ros2 topic hz /fw/health/runtime 2>&1 | grep -q 'average rate'"

echo ""
echo "── Topic content snapshot ───────────────────"

echo -e "${YELLOW}[INFO]${NC} /fw/health/runtime sample (first message):"
timeout 12 ros2 topic echo /fw/health/runtime --once 2>/dev/null || \
    echo -e "${YELLOW}[WARN]${NC} No health message received within 12s"

echo ""
echo "── Storage checks ───────────────────────────"

check "violations directory exists and writable" \
    "[ -d '$PROJECT_ROOT/violations' ] && touch '$PROJECT_ROOT/violations/.fw_smoke_test' && rm '$PROJECT_ROOT/violations/.fw_smoke_test'"

check "config/thresholds.json exists" \
    "[ -f '$PROJECT_ROOT/config/thresholds.json' ]"

check "config/camera_lab.json exists" \
    "[ -f '$PROJECT_ROOT/config/camera_lab.json' ]"

echo ""
echo "── MQTT broker check ────────────────────────"

check "Mosquitto reachable on port 1883" \
    "timeout 3 bash -c 'echo > /dev/tcp/localhost/1883'"

echo ""
echo "── System health ────────────────────────────"

if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp | awk '{print $1/1000}')
    echo -e "CPU temp: ${TEMP}°C"
fi
echo "Memory:"
free -h 2>/dev/null || true

echo ""
echo "=============================================="
echo -e " Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "=============================================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi

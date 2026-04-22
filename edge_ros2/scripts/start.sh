#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh — Start Footwatch edge pipeline (native ROS2, no Docker)
#
# Usage:
#   bash scripts/start.sh              # Start ALL nodes via launch file
#   bash scripts/start.sh sensor_bridge  # Start only sensor_bridge
#   bash scripts/start.sh stop          # Kill all fw_ nodes
#   bash scripts/start.sh status        # Show which nodes are running
#   bash scripts/start.sh mosquitto     # Start local MQTT broker
#
# Works identically on Ubuntu (dev) and Raspberry Pi 400 (production).
# All paths resolve relative to edge_ros2/ project root.
# ─────────────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-all}"

# ── Source ROS2 ──────────────────────────────────────────────────────────────
source /opt/ros/humble/setup.bash
if [ -f "$PROJECT_ROOT/ros2_ws/install/setup.bash" ]; then
    source "$PROJECT_ROOT/ros2_ws/install/setup.bash"
else
    echo -e "${RED}[ERROR] Workspace not built. Run: bash scripts/setup.sh${NC}"
    exit 1
fi

# ── Environment ──────────────────────────────────────────────────────────────
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="rmw_cyclonedds_cpp"
export CYCLONEDDS_URI="file://$PROJECT_ROOT/config/cyclonedds.xml"

echo -e "${CYAN}=== Footwatch Edge — Native ROS2 ===${NC}"
echo "ROS_DOMAIN_ID:  $ROS_DOMAIN_ID"
echo "Project root:   $PROJECT_ROOT"
echo ""

# ── Config validation ────────────────────────────────────────────────────────
validate_configs() {
    local warn=0
    for f in thresholds.json camera_lab.json speed_calibration.json; do
        if [ ! -f "$PROJECT_ROOT/config/$f" ]; then
            echo -e "${YELLOW}[WARN] config/$f missing — defaults will be used${NC}"
            warn=1
        fi
    done
    if [ ! -d "$PROJECT_ROOT/models" ] || [ -z "$(ls -A "$PROJECT_ROOT/models" 2>/dev/null)" ]; then
        echo -e "${YELLOW}[WARN] models/ is empty — inference will fail${NC}"
        warn=1
    fi
    if [ $warn -eq 0 ]; then
        echo -e "${GREEN}[✓]${NC} All config files present"
    fi
}

# ── Common ROS args (used by individual node starts) ─────────────────────────
CONFIG_DIR="$PROJECT_ROOT/config"
MODELS_DIR="$PROJECT_ROOT/models"
VIOLATIONS_DIR="$PROJECT_ROOT/violations"
SPOOL_DB="$PROJECT_ROOT/violations/mqtt_spool.db"
PREVIEW="$PROJECT_ROOT/violations/.preview.jpg"
DEVICE_ID="${DEVICE_ID:-EDGE-001}"
CAMERA_ID="${CAMERA_ID:-FP_CAM_001}"
SITE_ID="${SITE_ID:-SITE-001}"

mkdir -p "$VIOLATIONS_DIR" "$PROJECT_ROOT/logs"

case "$ACTION" in

    # ── Start ALL nodes using the launch file ────────────────────────────
    all)
        validate_configs
        echo ""
        echo -e "${GREEN}Starting all 7 nodes via launch file...${NC}"
        echo "  Press Ctrl+C to stop all nodes."
        echo ""
        ros2 launch fw_launch footwatch_launch.py \
            device_id:="$DEVICE_ID" \
            camera_id:="$CAMERA_ID" \
            site_id:="$SITE_ID" \
            prometheus_port:=9100
        ;;

    # ── Start individual nodes ───────────────────────────────────────────
    sensor_bridge)
        echo -e "${GREEN}Starting sensor_bridge...${NC}"
        ros2 run fw_sensor_bridge sensor_bridge_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p camera_id:="$CAMERA_ID" \
            -p preview_path:="$PREVIEW"
        ;;

    inference)
        echo -e "${GREEN}Starting inference_node...${NC}"
        ros2 run fw_inference_node inference_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p models_dir:="$MODELS_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID"
        ;;

    tracking)
        echo -e "${GREEN}Starting tracking_speed_node...${NC}"
        ros2 run fw_tracking_speed_node tracking_speed_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID"
        ;;

    ocr)
        echo -e "${GREEN}Starting plate_ocr_node...${NC}"
        ros2 run fw_plate_ocr_node plate_ocr_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p models_dir:="$MODELS_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID"
        ;;

    aggregator)
        echo -e "${GREEN}Starting violation_aggregator...${NC}"
        ros2 run fw_violation_aggregator violation_aggregator --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p violations_dir:="$VIOLATIONS_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID"
        ;;

    mqtt)
        echo -e "${GREEN}Starting mqtt_bridge_node...${NC}"
        ros2 run fw_ros2_mqtt_bridge mqtt_bridge_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID" \
            -p site_id:="$SITE_ID" \
            -p spool_db_path:="$SPOOL_DB"
        ;;

    health)
        echo -e "${GREEN}Starting health_node...${NC}"
        ros2 run fw_health_node health_node --ros-args \
            -p config_dir:="$CONFIG_DIR" \
            -p device_id:="$DEVICE_ID" \
            -p camera_id:="$CAMERA_ID" \
            -p spool_db_path:="$SPOOL_DB" \
            -p prometheus_port:=9100
        ;;

    # ── Start local Mosquitto broker ─────────────────────────────────────
    mosquitto)
        echo -e "${GREEN}Starting Mosquitto MQTT broker...${NC}"
        mosquitto -c "$PROJECT_ROOT/config/mosquitto.dev.conf" -v
        ;;

    # ── Stop all fw_ nodes ───────────────────────────────────────────────
    stop)
        echo -e "${YELLOW}Stopping all Footwatch nodes...${NC}"
        # Kill all ROS2 processes containing 'fw_'
        pkill -f "fw_sensor_bridge" 2>/dev/null || true
        pkill -f "fw_inference_node" 2>/dev/null || true
        pkill -f "fw_tracking_speed" 2>/dev/null || true
        pkill -f "fw_plate_ocr" 2>/dev/null || true
        pkill -f "fw_violation_aggregator" 2>/dev/null || true
        pkill -f "fw_ros2_mqtt_bridge" 2>/dev/null || true
        pkill -f "fw_health_node" 2>/dev/null || true
        echo -e "${GREEN}[✓] All nodes stopped${NC}"
        ;;

    # ── Show running status ──────────────────────────────────────────────
    status)
        echo -e "${CYAN}── Running ROS2 nodes ──${NC}"
        ros2 node list 2>/dev/null || echo "(no ROS2 daemon running)"
        echo ""
        echo -e "${CYAN}── Active topics ──${NC}"
        ros2 topic list 2>/dev/null || echo "(no topics)"
        echo ""
        echo -e "${CYAN}── System resources ──${NC}"
        if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
            echo "CPU temp: $(cat /sys/class/thermal/thermal_zone0/temp | awk '{print $1/1000}')°C"
        fi
        free -h 2>/dev/null || true
        ;;

    # ── Rebuild workspace ────────────────────────────────────────────────
    build)
        echo -e "${YELLOW}Rebuilding ROS2 workspace...${NC}"
        cd "$PROJECT_ROOT/ros2_ws"
        colcon build --symlink-install
        echo -e "${GREEN}[✓] Build complete. Re-source with: source ros2_ws/install/setup.bash${NC}"
        ;;

    *)
        echo "Usage: $0 {all|sensor_bridge|inference|tracking|ocr|aggregator|mqtt|health|mosquitto|stop|status|build}"
        exit 1
        ;;
esac

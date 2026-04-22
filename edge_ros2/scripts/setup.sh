#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — One-time setup for Ubuntu / Raspberry Pi 400
# Run ONCE after cloning the repo. Installs Python deps and builds the
# ROS2 workspace.
#
# Usage:
#   cd edge_ros2
#   bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo -e "${GREEN}=== Footwatch Edge — Setup ===${NC}"
echo "Project root: $PROJECT_ROOT"
echo ""

# ── Step 1: Check ROS2 Humble ────────────────────────────────────────────────
if [ ! -f /opt/ros/humble/setup.bash ]; then
    echo -e "${RED}[ERROR] ROS2 Humble not found at /opt/ros/humble/setup.bash${NC}"
    echo "Install ROS2 Humble first:"
    echo "  https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html"
    exit 1
fi
source /opt/ros/humble/setup.bash
echo -e "${GREEN}[✓]${NC} ROS2 Humble found"

# ── Step 2: Install system dependencies ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/5] Installing system packages...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip \
    python3-colcon-common-extensions \
    ros-humble-rmw-cyclonedds-cpp \
    mosquitto \
    mosquitto-clients \
    sqlite3 \
    > /dev/null

echo -e "${GREEN}[✓]${NC} System packages installed"

# ── Step 3: Install Python dependencies ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/5] Installing Python packages...${NC}"
pip3 install -r "$PROJECT_ROOT/requirements.txt" --quiet
echo -e "${GREEN}[✓]${NC} Python packages installed"

# ── Step 4: Create runtime directories ───────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/5] Creating runtime directories...${NC}"
mkdir -p "$PROJECT_ROOT/violations"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/models"
mkdir -p "$PROJECT_ROOT/certs"
mkdir -p "$PROJECT_ROOT/test_data"
echo -e "${GREEN}[✓]${NC} Runtime directories ready"

# ── Step 5: Build ROS2 workspace ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] Building ROS2 workspace with colcon...${NC}"
cd "$PROJECT_ROOT/ros2_ws"
colcon build --symlink-install
echo -e "${GREEN}[✓]${NC} ROS2 workspace built"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo ""
echo "  Next steps:"
echo "    1. Place models in: $PROJECT_ROOT/models/"
echo "       - twowheeler_yolov8n.pt"
echo "       - lp_localiser.pt"
echo ""
echo "    2. Start the full pipeline:"
echo "       bash scripts/start.sh"
echo ""
echo "    3. Or start individual nodes:"
echo "       bash scripts/start.sh sensor_bridge"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"

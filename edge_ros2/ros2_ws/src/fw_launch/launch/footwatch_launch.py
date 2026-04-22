"""
footwatch_launch.py — Single launch file for ALL edge nodes
=============================================================
Replaces docker-compose entirely. Starts all 7 pipeline nodes
in a single ROS2 launch command.

Usage (from edge_ros2/):
    ros2 launch ros2_ws/src/fw_launch/launch/footwatch_launch.py

All config/model/violation paths resolve relative to the project
root (edge_ros2/), making it portable between Ubuntu dev systems
and Raspberry Pi 400 without any path changes.

Pipeline order:
  1. fw_sensor_bridge      — /fw/camera/frame
  2. fw_inference_node     — /fw/detect/twowheeler
  3. fw_tracking_speed_node — /fw/track/speed
  4. fw_plate_ocr_node     — /fw/plate/ocr
  5. fw_violation_aggregator — /fw/violation/confirmed
  6. fw_ros2_mqtt_bridge   — MQTT → AWS IoT / Local Mosquitto
  7. fw_health_node         — /fw/health/runtime + Prometheus
"""

import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # ── Resolve project root (edge_ros2/) ─────────────────────────────────
    # This launch file lives at: edge_ros2/ros2_ws/src/fw_launch/launch/
    # Project root is 4 levels up.
    launch_dir = Path(__file__).resolve().parent
    project_root = launch_dir.parents[3]

    config_dir = str(project_root / "config")
    models_dir = str(project_root / "models")
    violations_dir = str(project_root / "violations")
    spool_db_path = str(project_root / "violations" / "mqtt_spool.db")
    preview_path = str(project_root / "violations" / ".preview.jpg")

    # Ensure runtime directories exist
    for d in [violations_dir, str(project_root / "logs")]:
        os.makedirs(d, exist_ok=True)

    # ── Launch arguments (overridable from CLI) ───────────────────────────
    args = [
        DeclareLaunchArgument("device_id", default_value="EDGE-001"),
        DeclareLaunchArgument("camera_id", default_value="FP_CAM_001"),
        DeclareLaunchArgument("site_id", default_value="SITE-001"),
        DeclareLaunchArgument("prometheus_port", default_value="9100"),
        LogInfo(msg=f"[FW-LAUNCH] Project root: {project_root}"),
        LogInfo(msg=f"[FW-LAUNCH] Config dir:   {config_dir}"),
        LogInfo(msg=f"[FW-LAUNCH] Models dir:   {models_dir}"),
    ]

    device_id = LaunchConfiguration("device_id")
    camera_id = LaunchConfiguration("camera_id")
    site_id = LaunchConfiguration("site_id")
    prometheus_port = LaunchConfiguration("prometheus_port")

    # ── Common parameters shared across nodes ─────────────────────────────
    common_params = {
        "config_dir": config_dir,
        "device_id": device_id,
        "camera_id": camera_id,
    }

    # ── Node 1: Sensor Bridge (sole camera owner) ────────────────────────
    sensor_bridge = Node(
        package="fw_sensor_bridge",
        executable="sensor_bridge_node",
        name="fw_sensor_bridge",
        output="screen",
        parameters=[{
            **common_params,
            "preview_path": preview_path,
            "jpeg_quality": 75,
        }],
    )

    # ── Node 2: Inference (Stage 1 — YOLOv8 detection) ──────────────────
    inference_node = Node(
        package="fw_inference_node",
        executable="inference_node",
        name="fw_inference_node",
        output="screen",
        parameters=[{
            **common_params,
            "models_dir": models_dir,
        }],
    )

    # ── Node 3: Tracking + Speed (Stage 3 — ByteTrack + Kalman) ──────────
    tracking_node = Node(
        package="fw_tracking_speed_node",
        executable="tracking_speed_node",
        name="fw_tracking_speed_node",
        output="screen",
        parameters=[common_params],
    )

    # ── Node 4/5/6: Plate OCR (LP localise + CLAHE + PaddleOCR) ──────────
    ocr_node = Node(
        package="fw_plate_ocr_node",
        executable="plate_ocr_node",
        name="fw_plate_ocr_node",
        output="screen",
        parameters=[{
            **common_params,
            "models_dir": models_dir,
        }],
    )

    # ── Node 7: Violation Aggregator (evidence + challan) ─────────────────
    aggregator_node = Node(
        package="fw_violation_aggregator",
        executable="violation_aggregator",
        name="fw_violation_aggregator",
        output="screen",
        parameters=[{
            **common_params,
            "violations_dir": violations_dir,
        }],
    )

    # ── MQTT Bridge (ROS2 → MQTT at-least-once) ──────────────────────────
    mqtt_bridge = Node(
        package="fw_ros2_mqtt_bridge",
        executable="mqtt_bridge_node",
        name="fw_ros2_mqtt_bridge",
        output="screen",
        parameters=[{
            **common_params,
            "site_id": site_id,
            "spool_db_path": spool_db_path,
        }],
    )

    # ── Health Monitor (device vitals + Prometheus) ──────────────────────
    health_node = Node(
        package="fw_health_node",
        executable="health_node",
        name="fw_health_node",
        output="screen",
        parameters=[{
            **common_params,
            "spool_db_path": spool_db_path,
            "prometheus_port": prometheus_port,
        }],
    )

    return LaunchDescription(
        args + [
            sensor_bridge,
            inference_node,
            tracking_node,
            ocr_node,
            aggregator_node,
            mqtt_bridge,
            health_node,
        ]
    )

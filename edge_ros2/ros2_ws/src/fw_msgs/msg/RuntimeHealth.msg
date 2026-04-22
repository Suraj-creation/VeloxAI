# RuntimeHealth — published by fw_health_node every 10s
builtin_interfaces/Time timestamp
string device_id
string camera_id
string schema_version
# Pipeline state
bool pipeline_running
float32 pipeline_fps
float32 pipeline_latency_ms_p50
int32 active_tracks
int32 violations_in_session
int32 mqtt_offline_queue_depth
# Device vitals
float32 cpu_percent
float32 memory_used_mb
float32 cpu_temp_celsius
float32 disk_free_gb
# Camera state
bool camera_connected
string camera_status        # "online", "signal_flat", "disconnected", "waiting"
float32 signal_mean_luma
float32 signal_std_luma
# Error counters
int32 frame_failures
int32 reconnects
int32 pipeline_errors

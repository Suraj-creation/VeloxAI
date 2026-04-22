# ViolationConfirmed — fully confirmed violation, written to disk, pushed to MQTT
# schema_version v1
builtin_interfaces/Time timestamp
string schema_version       # "v1"
string event_id             # uuid — idempotency key for MQTT dedup
string device_id
string camera_id
string ts_utc               # ISO8601 UTC
string event_type           # "FOOTPATH_ENCROACHMENT"
int32 track_id
string class_name
float32 speed_kmph
float32 confidence
string plate_text
float32 ocr_confidence
bool plate_format_valid
float32 gps_lat
float32 gps_lng
string location_name
string evidence_dir         # local path to evidence bundle
string evidence_uri         # S3/cloud URI (populated after upload)
float32 total_pipeline_latency_ms
bool pushed_to_cloud        # false until MQTT bridge confirms

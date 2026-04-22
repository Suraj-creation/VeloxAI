# ViolationCandidate — pre-confirmed violation (all stages passed, cooldown check pending)
builtin_interfaces/Time timestamp
string camera_id
string frame_id
string event_id             # idempotency key (uuid)
int32 track_id
string class_name
float32 speed_kmph
string plate_text
float32 ocr_confidence
bool plate_format_valid
float32 gps_lat
float32 gps_lng
string location_name

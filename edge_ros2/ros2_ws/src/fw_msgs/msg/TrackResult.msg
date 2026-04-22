# TrackResult — output from Stage 3 ByteTrack + speed estimation
builtin_interfaces/Time timestamp
string camera_id
string frame_id
int32 track_id
string class_name
float32 x1
float32 y1
float32 x2
float32 y2
float32 center_x
float32 center_y
float32 speed_kmph
float32 speed_confidence     # 0.0 if fewer than 3 history frames
bool is_moving               # speed_kmph >= speed_threshold
bool is_parked               # speed < 5 km/h threshold
int32 history_frames         # number of frames in track history
float32 detection_confidence
float32 tracker_latency_ms
float32 speed_latency_ms

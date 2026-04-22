# DetectionArray — batch of detections for one frame
builtin_interfaces/Time frame_timestamp
string camera_id
string frame_id         # uuid per frame for tracing
int32 frame_number
float32 signal_mean_luma
float32 signal_std_luma
bool signal_ok          # false if frame is flat/black/white
fw_msgs/Detection[] detections
float32 stage1_latency_ms

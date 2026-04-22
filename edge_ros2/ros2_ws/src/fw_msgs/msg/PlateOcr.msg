# PlateOcr — output from Stage 4/5/6 plate pipeline
builtin_interfaces/Time timestamp
string camera_id
string frame_id
int32 track_id
# Plate localisation (Stage 4)
float32 plate_x1
float32 plate_y1
float32 plate_x2
float32 plate_y2
float32 plate_localiser_confidence
bool plate_found
# OCR (Stage 6)
string raw_text
string cleaned_text
bool format_valid
float32 ocr_confidence
int32 ocr_voting_rounds
# Latencies
float32 plate_loc_latency_ms
float32 enhancement_latency_ms
float32 ocr_latency_ms
string enhancement_method    # "clahe_cpu" or "esrgan"

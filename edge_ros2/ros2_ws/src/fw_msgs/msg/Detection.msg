# Detection — output from Stage 1 YOLOv8 inference
# Published on /fw/detect/twowheeler
builtin_interfaces/Time timestamp
string camera_id
int32 track_id          # -1 if not yet tracked
float32 x1
float32 y1
float32 x2
float32 y2
float32 center_x
float32 center_y
string class_name       # motorcycle, bicycle, scooter, e-scooter
float32 confidence
float32 bbox_area_px    # area filter guard

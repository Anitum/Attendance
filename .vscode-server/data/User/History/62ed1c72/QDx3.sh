#!/bin/bash

# Directories
VIDEO_DIR="$HOME"  # Directory where camera recordings are stored
PROCESSED_DIR="$HOME/results"  # Directory to keep track of processed files
LOG_DIR="$HOME/logs"
TEMP_DIR="$HOME/processing"
MOTION_DETECTOR_DIR="/home/ubuntu/motionDetector"
INPUT_DIR="$HOME/Results"  # Directory for CSV results
DETECTION_DIR="$HOME/faceDetections"  # Directory where face detections will be saved
DETECTION_HIGH_CONF_DIR="$HOME/faceDetections90"
ATTENDANCE_DIR="$HOME/Attendance"  # Directory for attendance CSV files

# S3 buckets
VIDEO_BUCKET="Erasmith"
RESULTS_BUCKET="people-detection-results"

# Face recognition script
FACE_RECOGNITION_SCRIPT="/home/ubuntu/Face_Recognition_just_json.py"

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/processing.log"
ERROR_LOG="$LOG_DIR/processing_error.log"
DEBUG_LOG="$LOG_DIR/debug.log"

# Create necessary directories
mkdir -p "$PROCESSED_DIR" "$TEMP_DIR" "$INPUT_DIR" "$DETECTION_DIR"
mkdir -p "$DETECTION_HIGH_CONF_DIR" "$ATTENDANCE_DIR"

# Logging function
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
}

# Function to process motion detection results
process_motion_results() {
    local video_file="$1"
    local motion_output="$2"
    local base_name=$(basename "$video_file" .mkv)
    
    # Extract components from motion detection output
    # Expected format: [channel4, False, 2025-03-10 13:32:32]
    local channel=$(echo "$motion_output" | cut -d',' -f1 | tr -d '[ ' )
    local motion_status=$(echo "$motion_output" | cut -d',' -f2 | tr -d ' ')
    
    # Extract date and time from the video filename
    # Input format: channel101_20250310T082239.mkv
    local file_datetime=$(echo "$base_name" | grep -o '[0-9]\{8\}T[0-9]\{6\}')
    
    # Format date and time from filename
    local file_date=$(echo "$file_datetime" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)T.*/\1-\2-\3/')
    local file_time=$(echo "$file_datetime" | sed 's/.*T\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1:\2:\3/')
    
    # Combine to create timestamp
    local detection_time="${file_date} ${file_time}"
    
    # Extract camera number from filename
    local camera_num=$(echo "$base_name" | grep -o 'channel[0-9]\+' | tr -d 'channel')
    
    # Create CSV file path with camera number and date
    local csv_file="$INPUT_DIR/camera${camera_num}_${file_date}.csv"
    
    # Create header if file doesn't exist
    if [ ! -f "$csv_file" ]; then
        echo "file_name,channel,motion_status,timestamp" > "$csv_file"
    fi
    
    # Append result to CSV
    echo "$base_name,$channel,$motion_status,$detection_time" >> "$csv_file"
    
    # Return true if motion was detected
    if [ "$motion_status" = "True" ]; then
        return 0
    else
        return 1
    fi
}

# Function to process face recognition and store attendance
process_face_recognition() {
    local image_path="$1"
    local video_file="$2"  # Video file path
    local base_name=$(basename "$video_file" .mkv)
    local camera_num=$(echo "$base_name" | grep -o 'channel[0-9]\+' | tr -d 'channel')
    local today=$(date '+%Y-%m-%d')
    
    # Extract date and time from the video filename
    # Input format: channel401_20250310T090600.mkv
    local file_datetime=$(echo "$base_name" | grep -o '[0-9]\{8\}T[0-9]\{6\}')
    
    # Format date and time from filename
    local file_date=$(echo "$file_datetime" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)T.*/\1-\2-\3/')
    local file_time=$(echo "$file_datetime" | sed 's/.*T\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1:\2:\3/')
    
    # Combine to create timestamp from video
    local timestamp="${file_date} ${file_time}"
    
    # Create attendance CSV file for today
    # Using the date from the video filename for the attendance file
    local attendance_csv="$ATTENDANCE_DIR/attendance_${file_date}.csv"
    
    # Create header if file doesn't exist
    if [ ! -f "$attendance_csv" ]; then
        echo "timestamp,camera,employee_id,confidence,face_id,image_path" > "$attendance_csv"
    fi
    
    # Run face recognition script and capture JSON output
    local recognition_output=$(python3 "$FACE_RECOGNITION_SCRIPT" "$image_path")
    
    if [ -n "$recognition_output" ]; then
        # Extract data from JSON output using grep and sed
        local employee_id=$(echo "$recognition_output" | grep -o '"employee_id": "[^"]*"' | sed 's/"employee_id": "\(.*\)"/\1/')
        local confidence=$(echo "$recognition_output" | grep -o '"confidence": [0-9.]*' | sed 's/"confidence": \(.*\)/\1/')
        local face_id=$(echo "$recognition_output" | grep -o '"face_id": "[^"]*"' | sed 's/"face_id": "\(.*\)"/\1/')
        
        if [ -n "$employee_id" ]; then
            # Append to attendance CSV with timestamp from video filename
            echo "$timestamp,camera$camera_num,$employee_id,$confidence,$face_id,$image_path" >> "$attendance_csv"
            log_message "Recorded attendance for $employee_id with confidence $confidence at time $timestamp" "$DEBUG_LOG"
            return 0
        fi
    fi
    
    # If we get here, recognition failed or returned empty
    log_message "Face recognition failed or no identity found for: $image_path at time $timestamp" "$DEBUG_LOG"
    return 1
}
# Function to check if file is complete (not being written)
is_file_complete() {
    local file="$1"
    local size1
    local size2
    
    size1=$(stat -c %s "$file")
    sleep 5
    size2=$(stat -c %s "$file")
    
    [ "$size1" = "$size2" ]
}

# Function to process a single video file
process_video() {
    local video_file="$1"
    local base_name=$(basename "$video_file" .mkv)
    local processed_marker="${PROCESSED_DIR}/${base_name}.done"

    # Debug logging
    log_message "Starting process for video: $video_file" "$DEBUG_LOG"

    # Skip if already processed
    if [ -f "$processed_marker" ]; then
        log_message "Skipping already processed file: $video_file"
        return
    fi

    # Check if file is complete
    if ! is_file_complete "$video_file"; then
        log_message "File is still being written: $video_file" "$ERROR_LOG"
        return
    fi

    # Verify video file
    if ! ffprobe "$video_file" &>/dev/null; then
        log_message "Invalid video file: $video_file" "$ERROR_LOG"
        return
    fi

    log_message "Processing video: $video_file"

    # Run motion detection with detailed logging
    log_message "Running motion detection..." "$DEBUG_LOG"

    # Use full path to motion detector and capture output
    motion_output=$("$MOTION_DETECTOR_DIR/motion_detector" "$video_file")
    
    # Process motion detection results and store in CSV
    process_motion_results "$video_file" "$motion_output"
    motion_detected=$?

    if [ $motion_detected -eq 0 ]; then
        log_message "Motion detected, running object detection..." "$DEBUG_LOG"
        
        # Extract date from the video filename
        # Input format: channel101_20250310T082239.mkv
        local file_datetime=$(echo "$base_name" | grep -o '[0-9]\{8\}T[0-9]\{6\}')
        # Format date from filename: 2025-03-10
        local file_date=$(echo "$file_datetime" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)T.*/\1-\2-\3/')
        
        # Create date subfolder in detection directory
        local date_detection_dir="$DETECTION_DIR/$file_date"
        mkdir -p "$date_detection_dir"
        
        # Create high confidence directory for this date if it doesn't exist
        local date_high_conf_dir="$DETECTION_HIGH_CONF_DIR/$file_date"
        mkdir -p "$date_high_conf_dir"
        
        # Run the object detection Python script
        # Note: The original script might not support output_dir parameter
        # If it doesn't, we'll need to move files after detection
        log_message "Running object detection to $date_detection_dir..." "$DEBUG_LOG"
        
        # Store the current DETECTION_DIR value
        local original_detection_dir="$DETECTION_DIR"
        
        # Temporarily set DETECTION_DIR to date-specific directory
        export DETECTION_DIR="$date_detection_dir"
        
        if ! python3 /home/ubuntu/open_model_zoo/demos/object_detection_demo/python/saved_object_detection_demo.py \
            -d CPU \
            -i "$video_file" \
            -at ssd \
            -m /home/ubuntu/models/intel/face-detection-retail-0005/FP32/face-detection-retail-0005.xml \
            --no_show 2>&1 | tee -a "$DEBUG_LOG"; then
            
            # Restore original DETECTION_DIR
            export DETECTION_DIR="$original_detection_dir"
            log_message "Object detection failed" "$ERROR_LOG"
            return
        fi
        
        # Restore original DETECTION_DIR
        export DETECTION_DIR="$original_detection_dir"
        
        # Count the number of detections in the date subfolder
        detection_count=$(ls -1 "$date_detection_dir" 2>/dev/null | wc -l)
        log_message "Found $detection_count detections in $date_detection_dir" "$DEBUG_LOG"
        
        # If detections were found, process each one
        if [ $detection_count -gt 0 ]; then
            log_message "Processing face detections..." "$DEBUG_LOG"
            
            # Find high confidence detections and process them with face recognition
            find "$date_detection_dir" -type f -name "*confidence_9[1-9].jpg" -o -name "*confidence_100.jpg" | while read -r detection; do
                # Pass the video file path as the second parameter
                process_face_recognition "$detection" "$video_file"
                
                # Copy to date-specific high confidence directory
                cp "$detection" "$date_high_conf_dir/"
                log_message "Copied high confidence detection to $date_high_conf_dir/$(basename "$detection")" "$DEBUG_LOG"
            done
            
            # Create a directory for the current video's detections for possible S3 upload
            detection_s3_dir="${file_date}/${base_name}_detections"
            
            # Upload each detection to S3 (commented out as per original script)
            #log_message "Uploading detections to S3..." "$DEBUG_LOG"
            #for detection in "$date_detection_dir"/*; do
            #    if ! aws s3 cp "$detection" "s3://${RESULTS_BUCKET}/${detection_s3_dir}/$(basename "$detection")"; then
            #        log_message "Failed to upload detection to S3: $detection" "$ERROR_LOG"
            #    fi
            #done
        fi
    else
        log_message "No motion detected in file: $base_name.mkv" "$DEBUG_LOG"
        log_message "No motion detected, skipping object detection" "$DEBUG_LOG"
        touch "$processed_marker"  # Mark as processed even though we skip
        rm "$video_file"  # Clean up the video file
        return
    fi

    # Upload video to S3 (commented out as per original script)
    #log_message "Uploading video to S3..." "$DEBUG_LOG"
    #if ! aws s3 cp "$video_file" "s3://${VIDEO_BUCKET}/${base_name}.mkv"; then
    #    log_message "Failed to upload video to S3: $video_file" "$ERROR_LOG"
    #    return
    #fi

    # Create marker file and cleanup
    touch "$processed_marker"
    rm "$video_file"
    
    log_message "Successfully processed and uploaded: $video_file"
}

# Function to clean up old processed markers
cleanup_old_markers() {
    find "$PROCESSED_DIR" -type f -mtime +7 -delete
}

# Main processing loop
main() {
    log_message "Starting video processing service"
    
    while true; do
        # First process channel401 files
        log_message "Looking for channel401 files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*channel401*.mkv" | while read -r video_file; do
            process_video "$video_file"
        done

        # Then process channel101 files
        log_message "Looking for channel101 files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*channel101*.mkv" | while read -r video_file; do
            process_video "$video_file"
        done
        
        # Finally process any other files
        log_message "Looking for other channel files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*.mkv" ! -name "*channel401*.mkv" ! -name "*channel101*.mkv" | while read -r video_file; do
            process_video "$video_file"
        done

        # Clean up old markers periodically
        cleanup_old_markers

        # Wait before next iteration
        sleep 60
    done
}

# Cleanup function
cleanup() {
    log_message "Stopping video processing service"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Start the main process
main
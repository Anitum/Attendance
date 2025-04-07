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
FACE_RECOGNITION_DIR="$HOME/recognizedFaces"  # Directory to store face recognition results

# S3 buckets
VIDEO_BUCKET="Erasmith"
RESULTS_BUCKET="people-detection-results"

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/processing.log"
ERROR_LOG="$LOG_DIR/processing_error.log"
DEBUG_LOG="$LOG_DIR/debug.log"
FACE_LOG="$LOG_DIR/face_recognition.log"

# Create necessary directories
mkdir -p "$PROCESSED_DIR" "$TEMP_DIR" "$INPUT_DIR" "$DETECTION_DIR"
mkdir -p "$DETECTION_HIGH_CONF_DIR" "$FACE_RECOGNITION_DIR"

# Logging function
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
}

# Function to process face detection using Face_Recognition.py
process_face_recognition() {
    local face_image="$1"
    local base_name=$(basename "$face_image")
    local face_processed_marker="${PROCESSED_DIR}/face_${base_name}.done"
    
    # Skip if already processed
    if [ -f "$face_processed_marker" ]; then
        log_message "Skipping already processed face: $base_name" "$FACE_LOG"
        return
    fi
    
    log_message "Processing face recognition on: $face_image" "$FACE_LOG"
    
    # Run face recognition script
    local recognition_result=$(python3 /home/ubuntu/Face_Recognition.py "$face_image")
    
    # Check if recognition was successful
    if [ $? -ne 0 ]; then
        log_message "Face recognition failed for: $face_image" "$ERROR_LOG"
        return
    }
    
    # Save the recognition result
    local result_file="${FACE_RECOGNITION_DIR}/${base_name%.jpg}_result.json"
    echo "$recognition_result" > "$result_file"
    
    # Extract employee_id and confidence from JSON result
    local employee_id=$(echo "$recognition_result" | jq -r '.employee_id')
    local confidence=$(echo "$recognition_result" | jq -r '.confidence')
    
    # Log the recognition result
    log_message "Face recognized as: $employee_id with confidence: $confidence" "$FACE_LOG"
    
    # Create CSV entry for the recognition
    local csv_file="${FACE_RECOGNITION_DIR}/face_recognition_results.csv"
    
    # Create header if file doesn't exist
    if [ ! -f "$csv_file" ]; then
        echo "image_name,employee_id,confidence,timestamp" > "$csv_file"
    }
    
    # Append result to CSV
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$base_name,$employee_id,$confidence,$timestamp" >> "$csv_file"
    
    # Mark as processed
    touch "$face_processed_marker"
    
    # Upload recognition result to S3
    if ! aws s3 cp "$result_file" "s3://${RESULTS_BUCKET}/face_recognition/${base_name%.jpg}_result.json"; then
        log_message "Failed to upload face recognition result to S3: $result_file" "$ERROR_LOG"
    }
}

# Function to process high confidence face detections
process_face_detections() {
    log_message "Checking for new high confidence face detections..." "$DEBUG_LOG"
    
    # Find all face detection images
    find "$DETECTION_HIGH_CONF_DIR" -type f -name "*.jpg" | while read -r face_img; do
        process_face_recognition "$face_img"
    }
}

# Function to process motion detection results
process_motion_results() {
    local video_file="$1"
    local motion_output="$2"
    local base_name=$(basename "$video_file" .mkv)
    
    # Extract components from motion detection output
    # Expected format: [channel2, False, 2025-02-05 17:03:46]
    local channel=$(echo "$motion_output" | cut -d',' -f1 | tr -d '[ ' )
    local motion_status1=$(echo "$motion_output" | cut -d',' -f2 | tr -d ' ')
    # local motion_status2=$(echo "$motion_output" | cut -d',' -f3 | tr -d ' ')
    local detection_time=$(echo "$motion_output" | cut -d',' -f4 | tr -d ']')    
    # Extract date from the video filename
    # Input format: channel601_20250205T123130.mkv
    local file_date=$(echo "$base_name" | grep -o '[0-9]\{8\}' | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3/')
    
    # Extract camera number from filename
    local camera_num=$(echo "$base_name" | grep -o 'channel[0-9]\+' | tr -d 'channel')
    
    # Create CSV file path with camera number and date
    local csv_file="$INPUT_DIR/camera${camera_num}_${file_date}.csv"
    
    # Create header if file doesn't exist
    if [ ! -f "$csv_file" ]; then
        echo "file_name,channel,motion_status1,motion_status2,timestamp" > "$csv_file"
    fi
    
    # Append result to CSV
    echo "$base_name,$channel,$motion_status1,$motion_status2,$detection_time" >> "$csv_file"
    
    # Return true if any motion was detected
    if [ "$motion_status1" = "True" ] || [ "$motion_status2" = "True" ]; then
        return 0
    else
        return 1
    fi
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
        
        # Clear any previous detections
        rm -rf "$DETECTION_DIR"/*
        
        # Run the object detection Python script
        if ! python3 /home/ubuntu/open_model_zoo/demos/object_detection_demo/python/saved_object_detection_demo.py \
            -d CPU \
            -i "$video_file" \
            -at ssd \
            -m /home/ubuntu/models/intel/face-detection-retail-0005/FP32/face-detection-retail-0005.xml \
            --no_show 2>&1 | tee -a "$DEBUG_LOG"; then
            
            log_message "Object detection failed" "$ERROR_LOG"
            return
        fi
        
        # Count the number of detections
        detection_count=$(ls -1 "$DETECTION_DIR" | wc -l)
        # Copy high confidence detections (>90) to separate directory
        find "$DETECTION_DIR" -type f -name "*confidence_9[1-9].jpg" -o -name "*confidence_100.jpg" | xargs -I{} cp {} "$DETECTION_HIGH_CONF_DIR"/
        log_message "Found $detection_count detections" "$DEBUG_LOG"
        
        # If detections were found, upload them to S3
        if [ $detection_count -gt 0 ]; then
            log_message "Uploading detections to S3..." "$DEBUG_LOG"
            
            # Create a directory for the current video's detections
            detection_s3_dir="${base_name}_detections"
            
            # Upload each detection
            for detection in "$DETECTION_DIR"/*; do
                if ! aws s3 cp "$detection" "s3://${RESULTS_BUCKET}/${detection_s3_dir}/$(basename "$detection")"; then
                    log_message "Failed to upload detection to S3: $detection" "$ERROR_LOG"
                fi
            done
            
            # Process any high confidence faces
            process_face_detections
        fi
    else
        log_message "No motion detected in file: $base_name.mkv" "$DEBUG_LOG"
        log_message "No motion detected, skipping object detection" "$DEBUG_LOG"
        touch "$processed_marker"  # Mark as processed even though we skip
        rm "$video_file"  # Clean up the video file
        return
    fi

    # Upload video to S3
    log_message "Uploading video to S3..." "$DEBUG_LOG"
    if ! aws s3 cp "$video_file" "s3://${VIDEO_BUCKET}/${base_name}.mkv"; then
        log_message "Failed to upload video to S3: $video_file" "$ERROR_LOG"
        return
    fi

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
    
    # Install jq if not already installed (needed for JSON parsing)
    if ! command -v jq &> /dev/null; then
        log_message "Installing jq for JSON processing..." "$DEBUG_LOG"
        sudo apt-get update && sudo apt-get install -y jq
    fi
    
    while true; do
        # Find all .mkv files
        find "$VIDEO_DIR" -type f -name "*.mkv" | while read -r video_file; do
            process_video "$video_file"
        done
        
        # Also check for any face detections that might have been missed
        process_face_detections

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
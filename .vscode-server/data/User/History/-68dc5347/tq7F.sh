#!/bin/bash

# face_recognition_tracking.sh - Replacement for face_recognition_no_upload.sh
# This script processes video files using face landmark detection and organizes the results

# Directories
VIDEO_DIR="$HOME"  # Directory where camera recordings are stored
LOG_DIR="$HOME/logs"
TRACK_OUTPUT_DIR="/home/ubuntu/faceDetectionTrack"
FINAL_OUTPUT_DIR="/home/ubuntu/PushToAWSandGrey"

# Face landmark detection script path
LANDMARK_SCRIPT="/home/ubuntu/open_model_zoo/demos/face_recognition_demo/python/land_mark_with_face_detection.py"
PULL_IMAGES_SCRIPT="/home/ubuntu/pull_images.py"

# Face detection model paths
FACE_DETECTION_MODEL="/home/ubuntu/models/intel/face-detection-retail-0005/FP32/face-detection-retail-0005.xml"
LANDMARK_MODEL="/home/ubuntu/models/intel/landmarks-regression-retail-0009/FP32/landmarks-regression-retail-0009.xml"

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/face_tracking.log"
ERROR_LOG="$LOG_DIR/face_tracking_error.log"
DEBUG_LOG="$LOG_DIR/face_tracking_debug.log"

# Create necessary directories
mkdir -p "$TRACK_OUTPUT_DIR"
mkdir -p "$FINAL_OUTPUT_DIR"

# Today's date for folder organization
TODAY=$(date '+%Y%m%d')
TODAYS_TRACK_DIR="$TRACK_OUTPUT_DIR/$TODAY"
mkdir -p "$TODAYS_TRACK_DIR"

# Create a flag file to track when we last ran pull_images
PULL_IMAGES_FLAG="$LOG_DIR/last_pull_images"
touch -t "$(date '+%Y%m%d0000')" "$PULL_IMAGES_FLAG"  # Set to beginning of today

# Logging function
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
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
    local processed_marker="${TODAYS_TRACK_DIR}/${base_name}.done"

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

    # Create a temporary output directory for this specific video
    local temp_output_dir="${TODAYS_TRACK_DIR}/${base_name}"
    mkdir -p "$temp_output_dir"

    # Run the landmark detection script
    log_message "Running landmark detection on $video_file..." "$DEBUG_LOG"
    
    python3 "$LANDMARK_SCRIPT" \
        -i "$video_file" \
        -m_fd "$FACE_DETECTION_MODEL" \
        -m_lm "$LANDMARK_MODEL" \
        -o "$temp_output_dir" \
        --verbose 2>&1 | tee -a "$DEBUG_LOG"
    
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_message "Error: Face landmark detection failed for $video_file" "$ERROR_LOG"
        return
    fi
    
    log_message "Landmark detection completed for $video_file. Results in $temp_output_dir"
    
    # Create marker file to indicate processing is complete
    touch "$processed_marker"
    
    # Mark that we have new content to process
    touch "$TODAYS_TRACK_DIR/.new_content"
}

# Function to run pull_images.py to select top images
process_pull_images() {
    log_message "Running pull_images.py to select top images..."
    
    # Create timestamp prefix for output images
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    
    # Run pull_images.py
    python3 "$PULL_IMAGES_SCRIPT" \
        -i "$TODAYS_TRACK_DIR" \
        -o "$FINAL_OUTPUT_DIR" \
        -n 2 \
        -p "$timestamp" 2>&1 | tee -a "$DEBUG_LOG"
        
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_message "Error: pull_images.py failed" "$ERROR_LOG"
    else
        log_message "Successfully selected top images to $FINAL_OUTPUT_DIR"
        # Update the last pull time
        touch "$PULL_IMAGES_FLAG"
        # Remove the new content flag
        rm -f "$TODAYS_TRACK_DIR/.new_content"
    fi
}

# Cleanup function
cleanup() {
    log_message "Stopping face tracking service"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Main processing loop
main() {
    log_message "Starting face tracking service"
    
    while true; do
        # Process all mkv video files in home directory
        find "$VIDEO_DIR" -type f -name "*.mkv" | while read -r video_file; do
            process_video "$video_file"
        done
        
        # After processing videos, run pull_images to select top images
        # Only run if there are new files processed since the last pull
        if [ -f "$TODAYS_TRACK_DIR/.new_content" ]; then
            process_pull_images
        fi
        
        # Wait before next iteration
        sleep 60
    done
}

# Start the main process
main
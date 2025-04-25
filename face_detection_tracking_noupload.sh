#!/bin/bash

# face_recognition_tracking.sh - Replacement for face_recognition_no_upload.sh
# This script processes video files using motion detection and face landmark detection
TODAY=$(date '+%Y%m%d')

# Directories
VIDEO_DIR="$HOME"  # Directory where camera recordings are stored
LOG_DIR="$HOME/logs"
TRACK_OUTPUT_DIR="/home/ubuntu/faceDetectionTrack"
FINAL_OUTPUT_DIR="/home/ubuntu/PushToAWSandGrey/$TODAY"
TRACK_CONTINUITY_DIR="$HOME/track_continuity"
MOTION_DETECTOR_DIR="/home/ubuntu/motionDetector"
PROCESSED_DIR="$HOME/results"  # Directory to keep track of processed files

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/face_tracking.log"
ERROR_LOG="$LOG_DIR/face_tracking_error.log"
DEBUG_LOG="$LOG_DIR/face_tracking_debug.log"

# Logging function - MOVED UP before first use
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
}

# Create necessary directories
mkdir -p "$TRACK_CONTINUITY_DIR"
mkdir -p "$TRACK_OUTPUT_DIR"
mkdir -p "$FINAL_OUTPUT_DIR"
mkdir -p "$PROCESSED_DIR"

# CSV file to store last frame face information for each channel
TRACK_CSV="$TRACK_CONTINUITY_DIR/$TODAY.csv"

# Face landmark detection script path
LANDMARK_SCRIPT="/home/ubuntu/open_model_zoo/demos/face_recognition_demo/python/land_mark_with_face_detection.py"
PULL_IMAGES_SCRIPT="/home/ubuntu/pull_images.py"

# Face detection model paths
FACE_DETECTION_MODEL="/home/ubuntu/models/intel/face-detection-adas-0001/FP32/face-detection-adas-0001.xml"
LANDMARK_MODEL="/home/ubuntu/models/intel/landmarks-regression-retail-0009/FP32/landmarks-regression-retail-0009.xml"

# Today's date for folder organization
TODAYS_TRACK_DIR="$TRACK_OUTPUT_DIR/$TODAY"
mkdir -p "$TODAYS_TRACK_DIR"

# Always recreate the tracking CSV for the current day to start fresh
echo "channel,timestamp,track_id,x,y,width,height,landmarks" > "$TRACK_CSV"
log_message "Created/reset track continuity CSV file for today: $TRACK_CSV"

# Create a flag file to track when we last ran pull_images
PULL_IMAGES_FLAG="$LOG_DIR/last_pull_images"
touch -t "$(date '+%Y%m%d0000')" "$PULL_IMAGES_FLAG"  # Set to beginning of today

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

# Function to process motion detection results
process_motion_results() {
    local video_file="$1"
    local motion_output="$2"
    local base_name=$(basename "$video_file" .mkv)
    
    # Extract components from motion detection output
    # Expected format: [channel4, False, 2025-03-10 13:32:32]
    local channel=$(echo "$motion_output" | cut -d',' -f1 | tr -d '[ ' )
    local motion_status=$(echo "$motion_output" | cut -d',' -f2 | tr -d ' ')
    
    log_message "Motion detection result: $motion_status for $base_name" "$DEBUG_LOG"
    
    # Return true if motion was detected
    if [ "$motion_status" = "True" ]; then
        return 0
    else
        return 1
    fi
}

# Function to extract channel number from video filename
extract_channel() {
    local video_name="$1"
    echo "$video_name" | grep -o 'channel[0-9]*'
}

# Function to run pull_images.py to select top images
process_pull_images() {
    local video_dir="$1"
    local video_name="$2"
    
    log_message "Running pull_images.py to select top images for $video_name..."
    
    log_message "Processing video directory: $video_name" "$DEBUG_LOG"
    
    # Check if there's a duplicate nested directory
    if [ -d "$video_dir/$video_name" ]; then
        nested_dir="$video_dir/$video_name"
        log_message "Found nested directory structure: $nested_dir" "$DEBUG_LOG"
        
        # Process all track directories (numbered) inside the nested directory
        for track_dir in "$nested_dir"/*; do
            if [ -d "$track_dir" ]; then
                track_id=$(basename "$track_dir")
                log_message "Processing track: $track_id" "$DEBUG_LOG"
                
                # Extract just the channel number from video_name (assuming format like "channel401_YYYYMMDDTHHMMSS")
                channel_part=$(extract_channel "$video_name")
                
                # Run pull_images.py on this specific track directory with simplified prefix
                python3 "$PULL_IMAGES_SCRIPT" \
                    -i "$track_dir" \
                    -o "$FINAL_OUTPUT_DIR" \
                    -n 2 \
                    -p "${channel_part}_track${track_id}" 2>&1 | tee -a "$DEBUG_LOG"
                
                if [ ${PIPESTATUS[0]} -ne 0 ]; then
                    log_message "Error: pull_images.py failed for track $track_id" "$ERROR_LOG"
                else
                    log_message "Successfully selected top image from track $track_id"
                fi
            fi
        done
    else
        # Try running on the video directory itself
        log_message "No nested directory found, processing $video_dir directly" "$DEBUG_LOG"
        
        # Extract just the channel number from video_name
        channel_part=$(extract_channel "$video_name")
        
        python3 "$PULL_IMAGES_SCRIPT" \
            -i "$video_dir" \
            -o "$FINAL_OUTPUT_DIR" \
            -n 2 \
            -p "${channel_part}" 2>&1 | tee -a "$DEBUG_LOG"
    fi
    
    # Update the last pull time
    touch "$PULL_IMAGES_FLAG"
    
    log_message "Completed processing tracks for $video_name"
}

# Function to process a single video file
process_video() {
    local video_file="$1"
    local base_name=$(basename "$video_file" .mkv)
    local processed_marker="${PROCESSED_DIR}/${base_name}.done"
    local channel=$(extract_channel "$base_name")
    local timestamp=$(echo "$base_name" | grep -o '[0-9]\{8\}T[0-9]\{6\}')

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
    
    # Run motion detection
    log_message "Running motion detection..." "$DEBUG_LOG"
    motion_output=$("$MOTION_DETECTOR_DIR/motion_detector" "$video_file")
    
    # Process motion detection results
    process_motion_results "$video_file" "$motion_output"
    motion_detected=$?
    
    if [ $motion_detected -eq 0 ]; then
        log_message "Motion detected, continuing with face tracking for $base_name" "$DEBUG_LOG"
    else
        log_message "No motion detected in file: $base_name.mkv, skipping face tracking" "$DEBUG_LOG"
        touch "$processed_marker"  # Mark as processed even though we skip
        return
    fi

    # Create a temporary output directory for this specific video
    local temp_output_dir="${TODAYS_TRACK_DIR}/${base_name}"
    mkdir -p "$temp_output_dir"

    # Run the landmark detection script with cross-video tracking enabled
    log_message "Running landmark detection on $video_file..." "$DEBUG_LOG"
    
    # In face_detection_tracking.sh, modify the Python call
    python3 "$LANDMARK_SCRIPT" \
        -i "$video_file" \
        -m_fd "$FACE_DETECTION_MODEL" \
        -m_lm "$LANDMARK_MODEL" \
        -o "$temp_output_dir" \
        --track_csv "$TRACK_CSV" \
        --channel "$(basename "$video_file" | grep -o 'channel[0-9]*')" \
        --timestamp "$(basename "$video_file" | grep -o '[0-9]\{8\}T[0-9]\{6\}')" \
        --verbose 2>&1 | tee -a "$DEBUG_LOG"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_message "Error: Face landmark detection failed for $video_file" "$ERROR_LOG"
        return
    fi
    
    log_message "Landmark detection completed for $video_file. Results in $temp_output_dir"
    
    # Create marker file to indicate processing is complete
    touch "$processed_marker"
    #rm "$video_file"
    # Wait for 30 seconds before pulling images
    log_message "Waiting 30 seconds before pulling images for $base_name..."
    sleep 15
    
    # Now pull images for this video
    process_pull_images "$temp_output_dir" "$base_name"
}

# Function to clean up old processed markers
cleanup_old_markers() {
    find "$PROCESSED_DIR" -type f -mtime +7 -delete
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
        # First process channel401 files
        log_message "Looking for channel401 files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*channel401*.mkv" | sort | while read -r video_file; do
            process_video "$video_file"
        done

        # Then process channel101 files
        log_message "Looking for channel101 files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*channel101*.mkv" | sort | while read -r video_file; do
            process_video "$video_file"
        done
        
        # Finally process any other files
        log_message "Looking for other channel files..." "$DEBUG_LOG"
        find "$VIDEO_DIR" -type f -name "*.mkv" ! -name "*channel401*.mkv" ! -name "*channel101*.mkv" | sort | while read -r video_file; do
            process_video "$video_file"
        done
        
        # Clean up old markers periodically
        cleanup_old_markers
        
        # Wait before next iteration
        sleep 60
    done
}

# Start the main process
main
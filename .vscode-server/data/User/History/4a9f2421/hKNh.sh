#!/bin/bash

# Directories
VIDEO_DIR="$HOME"  # Directory where camera recordings are stored
PROCESSED_DIR="$HOME/results"  # Directory to keep track of processed files
LOG_DIR="$HOME/logs"
TEMP_DIR="$HOME/processing"
MOTION_DETECTOR_DIR="/home/ubuntu/motionDetector"
INPUT_DIR="$HOME/Results"  # Directory for CSV results

# S3 buckets
VIDEO_BUCKET="Erasmith"
RESULTS_BUCKET="people-detection-results"

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/processing.log"
ERROR_LOG="$LOG_DIR/processing_error.log"
DEBUG_LOG="$LOG_DIR/debug.log"

# Create necessary directories
mkdir -p "$PROCESSED_DIR" "$TEMP_DIR" "$INPUT_DIR"

# Logging function
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
}

# Function to process motion detection re
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
    local result_file="${TEMP_DIR}/${base_name}_results.csv"
    local processed_marker="${PROCESSED_DIR}/${base_name}.done"

    # Debug logging
    log_message "Starting process for video: $video_file" "$DEBUG_LOG"
    log_message "Result file will be: $result_file" "$DEBUG_LOG"

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
        log_message "Motion detected, running pedestrian detection..." "$DEBUG_LOG"
        
        # Change to demo directory
        cd ~/omz_demos_build/intel64/Release/ || {
            log_message "Failed to change to demo directory" "$ERROR_LOG"
            return
        }
        
        if ! ./pedestrian_tracker_demo \
            -i "$video_file" \
            -m_det intel/person-detection-retail-0013/FP32/person-detection-retail-0013.xml \
            -m_reid intel/person-reidentification-retail-0277/FP32/person-reidentification-retail-0277.xml \
            -at ssd -no_show \
            -out "$result_file" 2>&1 | tee -a "$DEBUG_LOG"; then
            
            log_message "Pedestrian detection failed" "$ERROR_LOG"
            return
        fi
    else
        log_message "No motion detected in file: $base_name.mkv" "$DEBUG_LOG"
        log_message "No motion detected, skipping pedestrian detection" "$DEBUG_LOG"
        touch "$processed_marker"  # Mark as processed even though we skip
        rm "$video_file"  # Clean up the video file
        return
    fi

    # Check if result file exists and has content
    if [ ! -f "$result_file" ]; then
        log_message "Result file not created: $result_file" "$ERROR_LOG"
        return
    fi

    log_message "Result file size: $(stat -c %s "$result_file")" "$DEBUG_LOG"

    # Upload files to S3
    log_message "Uploading video to S3..." "$DEBUG_LOG"
    if ! aws s3 cp "$video_file" "s3://${VIDEO_BUCKET}/${base_name}.mkv"; then
        log_message "Failed to upload video to S3: $video_file" "$ERROR_LOG"
        return
    fi

    log_message "Uploading results to S3..." "$DEBUG_LOG"
    if ! aws s3 cp "$result_file" "s3://${RESULTS_BUCKET}/${base_name}_results.csv"; then
        log_message "Failed to upload results to S3: $result_file" "$ERROR_LOG"
        return
    fi

    # Create marker file and cleanup
    touch "$processed_marker"
    rm "$video_file"
    #rm "$result_file"
    
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
        # Find all .mkv files
        find "$VIDEO_DIR" -type f -name "*.mkv" | while read -r video_file; do
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
    #rm -rf "$TEMP_DIR"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Start the main process
main
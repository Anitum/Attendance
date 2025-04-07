#!/bin/bash

# Directories
VIDEO_DIR="$HOME"  # Directory where camera recordings are stored
PROCESSED_DIR="$HOME/results"  # Directory to keep track of processed files
LOG_DIR="$HOME/logs"
TEMP_DIR="$HOME/processing"
MOTION_DETECTOR_DIR="/home/ubuntu/motionDetector"
INPUT_DIR="$HOME/Results"  # Directory for CSV results
DETECTION_DIR="$HOME/faceDetections"  # Directory where face detections will be saved
DETECTION_DIR_90="$HOME/faceDetections90"  # Directory where high confidence (>=90%) face detections will be saved

# S3 buckets
VIDEO_BUCKET="Erasmith"
RESULTS_BUCKET="people-detection-results"

# Logging setup
mkdir -p "$LOG_DIR"
PROCESS_LOG="$LOG_DIR/processing.log"
ERROR_LOG="$LOG_DIR/processing_error.log"
DEBUG_LOG="$LOG_DIR/debug.log"

# Create necessary directories
mkdir -p "$PROCESSED_DIR" "$TEMP_DIR" "$INPUT_DIR" "$DETECTION_DIR" "$DETECTION_DIR_90"

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
    # Expected format: [channel2, False, 2025-02-05 17:03:46]
    local channel=$(echo "$motion_output" | cut -d',' -f1 | tr -d '[ ' )
    local motion_status=$(echo "$motion_output" | cut -d',' -f2 | tr -d ' ')
    local detection_time=$(echo "$motion_output" | cut -d',' -f3 | tr -d ']')    
    # Extract date from the video filename
    # Input format: channel601_20250205T123130.mkv
    local file_date=$(echo "$base_name" | grep -o '[0-9]\{8\}' | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3/')
    
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
        rm -rf "$DETECTION_DIR_90"/*
        
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
        log_message "Found $detection_count detections" "$DEBUG_LOG"
        
        # Process detections and separate high confidence ones (>=90%)
        for detection in "$DETECTION_DIR"/*; do
            if [ -f "$detection" ]; then
                # Extract confidence from the filename
                confidence=$(basename "$detection" | grep -o '_[0-9]\+\.[0-9]\+' | sed 's/_//')
                
                # If confidence is >=0.9 (90%), copy to the high confidence directory
                if (( $(echo "$confidence >= 0.9" | bc -l) )); then
                    cp "$detection" "$DETECTION_DIR_90/"
                fi
            fi
        done
        
        # Count high confidence detections
        detection_90_count=$(ls -1 "$DETECTION_DIR_90" | wc -l)
        log_message "Found $detection_90_count high confidence (>=90%) detections" "$DEBUG_LOG"
        
        # If detections were found, upload them to S3
        if [ $detection_count -gt 0 ]; then
            log_message "Uploading detections to S3..." "$DEBUG_LOG"
            
            # Create a directory for the current video's detections
            detection_s3_dir="${base_name}_detections"
            detection_s3_dir_90="${base_name}_detections_90plus"
            
            # Upload regular detections
            for detection in "$DETECTION_DIR"/*; do
                if [ -f "$detection" ]; then
                    if ! aws s3 cp "$detection" "s3://${RESULTS_BUCKET}/${detection_s3_dir}/$(basename "$detection")"; then
                        log_message "Failed to upload detection to S3: $detection" "$ERROR_LOG"
                    fi
                fi
            done
            
            # Upload high confidence detections
            for detection in "$DETECTION_DIR_90"/*; do
                if [ -f "$detection" ]; then
                    if ! aws s3 cp "$detection" "s3://${RESULTS_BUCKET}/${detection_s3_dir_90}/$(basename "$detection")"; then
                        log_message "Failed to upload high confidence detection to S3: $detection" "$ERROR_LOG"
                    fi
                fi
            done
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
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Start the main process
main
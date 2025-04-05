#!/bin/bash

# Face Track Selection Processing Script
# This script walks through your directory structure and processes each face track

# Configuration variables
INPUT_BASE_DIR=~/faceDetectionTrack/20250328
OUTPUT_DIR=~/face_recog_top1/20250328
NUM_IMAGES=1
PREFIX="selected"
PYTHON_SCRIPT=~/pull_images.py

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Log file
LOG_FILE="$OUTPUT_DIR/processing_log.txt"
echo "Face Track Processing started at $(date)" > "$LOG_FILE"

# Function to process a single channel directory
process_channel_dir() {
    local channel_dir="$1"
    local channel_name=$(basename "$channel_dir")
    
    echo "Processing channel directory: $channel_name" | tee -a "$LOG_FILE"
    
    # Check if this directory has a subdirectory with the same name (common pattern in your structure)
    if [ -d "$channel_dir/$channel_name" ]; then
        inner_dir="$channel_dir/$channel_name"
        
        # Loop through track directories in the inner directory
        for track_dir in "$inner_dir"/*; do
            if [ -d "$track_dir" ]; then
                process_track_dir "$track_dir" "$channel_name"
            fi
        done
    else
        # Loop through potential track directories directly in the channel directory
        for track_dir in "$channel_dir"/*; do
            if [ -d "$track_dir" ]; then
                process_track_dir "$track_dir" "$channel_name"
            fi
        done
    fi
}

# Function to process a single track directory
process_track_dir() {
    local track_dir="$1"
    local channel_name="$2"
    local track_id=$(basename "$track_dir")
    
    # Check if the directory contains jpg files
    if find "$track_dir" -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" | grep -q .; then
        echo "  Processing track: $channel_name/$track_id" | tee -a "$LOG_FILE"
        
        # Run the Python script for this track directory
        python3 "$PYTHON_SCRIPT" \
            -i "$track_dir" \
            -o "$OUTPUT_DIR" \
            -n "$NUM_IMAGES" \
            -p "${PREFIX}_${channel_name}" | tee -a "$LOG_FILE"
        
        echo "  Completed track: $channel_name/$track_id" | tee -a "$LOG_FILE"
    else
        echo "  Skipping $channel_name/$track_id - no image files found" | tee -a "$LOG_FILE"
    fi
}

# Main processing loop
echo "Starting face track processing..." | tee -a "$LOG_FILE"
echo "Input directory: $INPUT_BASE_DIR" | tee -a "$LOG_FILE"
echo "Output directory: $OUTPUT_DIR" | tee -a "$LOG_FILE"

# Process all channel directories that don't end with .done
for channel_dir in "$INPUT_BASE_DIR"/channel4*; do
    # Skip .done files
    if [[ "$channel_dir" != *.done ]]; then
        if [ -d "$channel_dir" ]; then
            process_channel_dir "$channel_dir"
        fi
    fi
done

echo "Face track processing completed at $(date)" | tee -a "$LOG_FILE"
echo "Total files processed: $(find "$OUTPUT_DIR" -name "*.jpg" | wc -l)" | tee -a "$LOG_FILE"

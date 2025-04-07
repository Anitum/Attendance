#!/bin/bash

# AWSandGreyPush.sh - Monitor PushToAWSandGrey folder and push face recognition results to AWS and GreyTHR
# This script processes face images, runs recognition, and pushes attendance data

# Directories
FACE_IMAGE_DIR="/home/ubuntu/PushToAWSandGrey"
ATTENDANCE_DIR="/home/ubuntu/Attendance2.0"
PROCESSED_DIR="/home/ubuntu/ProcessedFaces"
LOG_DIR="/home/ubuntu/logs"

# Face recognition script
FACE_RECOGNITION_SCRIPT="/home/ubuntu/Face_Recognition_just_json.py"

# Log files
PROCESS_LOG="$LOG_DIR/aws_grey_push.log"
ERROR_LOG="$LOG_DIR/aws_grey_push_error.log"

# Ensure directories exist
mkdir -p "$ATTENDANCE_DIR"
mkdir -p "$PROCESSED_DIR"
mkdir -p "$LOG_DIR"

# Logging function
log_message() {
    local message="$1"
    local log_file="${2:-$PROCESS_LOG}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$log_file"
}

# Function to create today's date folder
create_today_folder() {
    local today=$(date '+%Y%m%d')
    local today_dir="$FACE_IMAGE_DIR/$today"
    
    if [ ! -d "$today_dir" ]; then
        mkdir -p "$today_dir"
        log_message "Created today's processing folder: $today_dir"
    fi
    
    echo "$today_dir"
}

# Function to get today's attendance CSV file path
get_attendance_csv() {
    local today=$(date '+%Y-%m-%d')
    local csv_file="$ATTENDANCE_DIR/attendance_$today.csv"
    
    # Create CSV header if file doesn't exist
    if [ ! -f "$csv_file" ]; then
        echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$csv_file"
        log_message "Created attendance CSV file: $csv_file"
    fi
    
    echo "$csv_file"
}

# Function to process a single face image
process_face_image() {
    local image_path="$1"
    local today_dir="$2"
    local csv_file="$3"
    
    local filename=$(basename "$image_path")
    local camera_part=""
    
    # Extract camera number from filename (assuming format like "channel401_trackXX_...")
    if [[ "$filename" =~ channel([0-9]+)_ ]]; then
        camera_part="camera${BASH_REMATCH[1]}"
    else
        camera_part="unknown"
    fi
    
    log_message "Processing image: $filename from $camera_part"
    
    # Run face recognition using Face_Recognition_just_json.py
    local recognition_result=$(python3 "$FACE_RECOGNITION_SCRIPT" "$image_path")
    
    # Check if we got a valid JSON response
    if [[ "$recognition_result" == *"employee_id"* ]]; then
        # Parse the JSON output
        local employee_id=$(echo "$recognition_result" | grep -o '"employee_id":"[^"]*"' | cut -d'"' -f4)
        local confidence=$(echo "$recognition_result" | grep -o '"confidence":[0-9.]*' | cut -d':' -f2)
        local face_id=$(echo "$recognition_result" | grep -o '"face_id":"[^"]*"' | cut -d'"' -f4)
        
        # Skip if no match found
        if [[ "$employee_id" == "No match found" || "$employee_id" == "Error" ]]; then
            log_message "No match found for $filename" "$ERROR_LOG"
            # Move to processed with "unknown" label
            local target_dir="$PROCESSED_DIR/unknown"
            mkdir -p "$target_dir"
            mv "$image_path" "$target_dir/$filename"
            return
        fi
        
        # Generate timestamp (current time)
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        
        # Append to CSV
        echo "$timestamp,$camera_part,$employee_id,$confidence,$face_id,$image_path" >> "$csv_file"
        log_message "Added attendance record for $employee_id (confidence: $confidence)"
        
        # Move the processed image to employee-specific folder
        local target_dir="$PROCESSED_DIR/$employee_id"
        mkdir -p "$target_dir"
        mv "$image_path" "$target_dir/$filename"
        log_message "Moved $filename to $target_dir"
    else
        log_message "Invalid recognition result for $filename: $recognition_result" "$ERROR_LOG"
        # Move to processed with "error" label
        local target_dir="$PROCESSED_DIR/error"
        mkdir -p "$target_dir"
        mv "$image_path" "$target_dir/$filename"
    fi
}

# Function to move images to today's folder
organize_images() {
    local today_dir="$1"
    
    # Find all image files in the root directory
    find "$FACE_IMAGE_DIR" -maxdepth 1 -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" \) | while read image_file; do
        local basename=$(basename "$image_file")
        log_message "Moving $basename to today's folder"
        mv "$image_file" "$today_dir/"
    done
}

# Main loop
main() {
    log_message "Starting AWS and GreyTHR Push Service"
    
    while true; do
        # Create today's folder
        local today_dir=$(create_today_folder)
        
        # Get today's attendance CSV
        local csv_file=$(get_attendance_csv)
        
        # Move any loose images into today's folder
        organize_images "$today_dir"
        
        # Check for image files in today's folder
        image_count=$(find "$today_dir" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" \) | wc -l)
        
        if [ "$image_count" -gt 0 ]; then
            log_message "Found $image_count images to process in $today_dir"
            
            # Process each image
            find "$today_dir" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" \) | while read image_file; do
                process_face_image "$image_file" "$today_dir" "$csv_file"
            done
            
            # After processing images, notify that the CSV is ready for GreyTHR
            log_message "Completed processing $image_count images. Attendance data ready in $csv_file"
        else
            log_message "No new images to process in $today_dir"
        fi
        
        # Check if greythr_push_attendance.py is running
        if ! pgrep -f "greythr_push_attendance.py" > /dev/null; then
            log_message "Starting greythr_push_attendance.py to process attendance data"
            nohup python3 /home/ubuntu/greythr_push_attendance.py > "$LOG_DIR/greythr_push.log" 2>&1 &
        fi
        
        # Wait before the next check
        sleep 60
    done
}

# Handle cleanup on exit
cleanup() {
    log_message "Stopping AWS and GreyTHR Push Service"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Start the main process
main
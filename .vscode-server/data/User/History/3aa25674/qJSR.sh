#!/bin/bash

# Get today's date in YYYYMMDD format
TODAY=$(date +"%Y%m%d")

# Define source directory with today's date
SOURCE_DIR="/home/ubuntu/PushToAWSandGrey/$TODAY"

# Check if the source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory $SOURCE_DIR does not exist."
    exit 1
fi

# Create a results directory if it doesn't exist
RESULTS_DIR="/home/ubuntu/face_recognition_results/$TODAY"
mkdir -p "$RESULTS_DIR"

# Log file
LOG_FILE="$RESULTS_DIR/recognition_log.txt"

echo "Starting face recognition for images in $SOURCE_DIR at $(date)" | tee -a "$LOG_FILE"

# Process each image file in the source directory
for IMG_FILE in "$SOURCE_DIR"/*.{jpg,jpeg,png,JPG,JPEG,PNG}; do
    # Check if the glob expansion found any files
    if [ ! -f "$IMG_FILE" ]; then
        continue
    fi

    FILENAME=$(basename "$IMG_FILE")
    echo "Processing $FILENAME..." | tee -a "$LOG_FILE"
    
    # Run face recognition on the image
    RESULT=$(python3 /home/ubuntu/Face_Recognition_just_json.py "$IMG_FILE")
    
    # Save the result to a JSON file
    echo "$RESULT" > "$RESULTS_DIR/${FILENAME%.*}_result.json"
    
    # Also log the result
    echo "Result for $FILENAME: $RESULT" >> "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
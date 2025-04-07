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

# CSV file
CSV_FILE="$RESULTS_DIR/recognition_results.csv"

# Create CSV header
echo "Filename,Result" > "$CSV_FILE"

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
    
    # Save the individual result to a JSON file (optional - you can remove this if you only want CSV)
    echo "$RESULT" > "$RESULTS_DIR/${FILENAME%.*}_result.json"
    
    # Append to CSV file - escape quotes in the result to avoid CSV formatting issues
    ESCAPED_RESULT=$(echo "$RESULT" | sed 's/"/""/g')
    echo "\"$FILENAME\",\"$ESCAPED_RESULT\"" >> "$CSV_FILE"
    
    # Also log the result
    echo "Result for $FILENAME: $RESULT" >> "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
echo "CSV file created at $CSV_FILE"
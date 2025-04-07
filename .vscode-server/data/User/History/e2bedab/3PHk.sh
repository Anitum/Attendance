#!/bin/bash
while true; do
# Get today's date in YYYYMMDD format
TODAY=$(date '+%Y%m%d')
TODAY_DASH=$(date +"%Y-%m-%d")

# Define source directory with today's date
SOURCE_DIR="/home/ubuntu/PushToAWSandGrey/$TODAY"

# Check if the source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory $SOURCE_DIR does not exist."
    exit 1
fi

# Create a results directory if it doesn't exist
RESULTS_DIR="/home/ubuntu/face_recognition_results"
mkdir -p "$RESULTS_DIR"

# Log file
LOG_FILE="$RESULTS_DIR/recognition_log.txt"

# File to track processed images
PROCESSED_FILES_LOG="$RESULTS_DIR/processed_files.txt"
touch "$PROCESSED_FILES_LOG"

# CSV file for face recognition results
RECOG_CSV_FILE="$RESULTS_DIR/recognition_results_$TODAY_DASH.csv"

# CSV file for attendance (in the format expected by email_push_attendance.py)
ATTENDANCE_CSV_FILE="$RESULTS_DIR/attendance_results_$TODAY_DASH.csv"

# Create CSV headers if files don't exist or are empty
if [ ! -f "$RECOG_CSV_FILE" ] || [ ! -s "$RECOG_CSV_FILE" ]; then
    echo "Filename,Result" > "$RECOG_CSV_FILE"
fi

if [ ! -f "$ATTENDANCE_CSV_FILE" ] || [ ! -s "$ATTENDANCE_CSV_FILE" ]; then
    echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$ATTENDANCE_CSV_FILE"
fi

echo "Starting face recognition for images in $SOURCE_DIR at $(date)" | tee -a "$LOG_FILE"


# Define the channels to process in order
CHANNELS_TO_PROCESS=("channel401")

# Process each channel in the specified order
for CHANNEL in "${CHANNELS_TO_PROCESS[@]}"; do
    echo "Processing $CHANNEL images..." | tee -a "$LOG_FILE"
    
    # Process each image file in the channel
    for IMG_FILE in "$SOURCE_DIR"/*"$CHANNEL"*.{jpg,jpeg,png,JPG,JPEG,PNG}; do
        # Check if the glob expansion found any files
        if [ ! -f "$IMG_FILE" ]; then
            echo "No $CHANNEL files found" | tee -a "$LOG_FILE"
            continue
        fi

        FILENAME=$(basename "$IMG_FILE")
        FULL_PATH=$(realpath "$IMG_FILE")
        
        # Check if file has already been processed
        if grep -q "$FULL_PATH" "$PROCESSED_FILES_LOG"; then
            echo "Skipping already processed file: $FILENAME" | tee -a "$LOG_FILE"
            continue
        fi
        
        echo "Processing $FILENAME..." | tee -a "$LOG_FILE"
        
        # Run face recognition on the image
        RESULT=$(python3 /home/ubuntu/Face_Recognition_just_json.py "$IMG_FILE")
        
        # Append to recognition CSV file - escape quotes in the result to avoid CSV formatting issues
        ESCAPED_RESULT=$(echo "$RESULT" | sed 's/"/""/g')
        echo "\"$FILENAME\",\"$ESCAPED_RESULT\"" >> "$RECOG_CSV_FILE"
        
        # Parse the result to extract employee information for attendance CSV
        EMPLOYEE_ID=$(echo "$RESULT" | grep -o '"employee_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        CONFIDENCE=$(echo "$RESULT" | grep -o '"confidence"[[:space:]]*:[[:space:]]*[0-9.]*' | awk '{print $2}')
        FACE_ID=$(echo "$RESULT" | grep -o '"face_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 || echo "unknown")

        # Only add to attendance CSV if an employee was recognized
        if [ ! -z "$EMPLOYEE_ID" ] && [ "$EMPLOYEE_ID" != "No match found" ]; then
            # Extract timestamp from filename
            # Pattern looks for YYYYMMDDTHHMMSS in the filename
            if [[ $FILENAME =~ ([0-9]{8}T[0-9]{6}) ]]; then
                # Extract the matched timestamp
                FILE_TIMESTAMP="${BASH_REMATCH[1]}"
                
                # Convert the timestamp format from YYYYMMDDTHHMMSS to YYYY-MM-DD HH:MM:SS
                YEAR="${FILE_TIMESTAMP:0:4}"
                MONTH="${FILE_TIMESTAMP:4:2}"
                DAY="${FILE_TIMESTAMP:6:2}"
                HOUR="${FILE_TIMESTAMP:9:2}"
                MINUTE="${FILE_TIMESTAMP:11:2}"
                SECOND="${FILE_TIMESTAMP:13:2}"
                
                FORMATTED_TIMESTAMP="$YEAR-$MONTH-$DAY $HOUR:$MINUTE:$SECOND"
            else
                # Fallback to current time if filename doesn't match the expected pattern
                FORMATTED_TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
                echo "Warning: Could not extract timestamp from filename $FILENAME, using current time" | tee -a "$LOG_FILE"
            fi
            
            CAMERA="$CHANNEL"

            # Add to attendance CSV
            echo "\"$FORMATTED_TIMESTAMP\",\"$CAMERA\",\"$EMPLOYEE_ID\",\"$CONFIDENCE\",\"$FACE_ID\",\"$IMG_FILE\"" >> "$ATTENDANCE_CSV_FILE"
            
            echo "Added attendance record for $EMPLOYEE_ID with timestamp $FORMATTED_TIMESTAMP" | tee -a "$LOG_FILE"
        fi
        
        # Mark file as processed by adding its path to the processed files log
        echo "$FULL_PATH" >> "$PROCESSED_FILES_LOG"
        
        # Also log the result
        echo "Result for $FILENAME: $RESULT" >> "$LOG_FILE"
    done
    
    echo "Finished processing $CHANNEL images" | tee -a "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
echo "Recognition CSV file created at $RECOG_CSV_FILE"
echo "Attendance CSV file created at $ATTENDANCE_CSV_FILE"

echo "Process completed at $(date)" | tee -a "$LOG_FILE"
    echo "Sleeping for 5 minutes before next check..."
    sleep 300  # Sleep for 5 minutes
done
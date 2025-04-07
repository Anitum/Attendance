#!/bin/bash

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

# CSV file for face recognition results
RECOG_CSV_FILE="$RESULTS_DIR/recognition_results_$TODAY_DASH.csv"

# CSV file for attendance (in the format expected by greythr_push_attendance.py)
ATTENDANCE_CSV_FILE="$RESULTS_DIR/attendance_results_$TODAY_DASH.csv"

# Create CSV headers (separate files)
echo "Filename,Result" > "$RECOG_CSV_FILE"
echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$ATTENDANCE_CSV_FILE"

echo "Starting face recognition for images in $SOURCE_DIR at $(date)" | tee -a "$LOG_FILE"

# First, check if there are any existing attendance records to push from previous runs
PREVIOUS_FILE="$RESULTS_DIR/attendance_results_$(date -d "yesterday" +"%Y-%m-%d").csv"
if [ -f "$PREVIOUS_FILE" ] && [ $(wc -l < "$PREVIOUS_FILE") -gt 1 ]; then
    echo "Found previous attendance file: $PREVIOUS_FILE" | tee -a "$LOG_FILE"
    echo "Pushing previous attendance data to Greythr..." | tee -a "$LOG_FILE"
    
    if python3 /home/ubuntu/greythr_push_attendance.py "$PREVIOUS_FILE"; then
        echo "Previous attendance data successfully pushed to Greythr" | tee -a "$LOG_FILE"
    else
        echo "Failed to push previous attendance data to Greythr (exit code $?)" | tee -a "$LOG_FILE"
    fi
fi

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
        
        CAMERA="main_entrance"  # You can customize this

        # Add to attendance CSV
        echo "\"$FORMATTED_TIMESTAMP\",\"$CAMERA\",\"$EMPLOYEE_ID\",\"$CONFIDENCE\",\"$FACE_ID\",\"$IMG_FILE\"" >> "$ATTENDANCE_CSV_FILE"
        
        echo "Added attendance record for $EMPLOYEE_ID with timestamp $FORMATTED_TIMESTAMP" | tee -a "$LOG_FILE"
        
        # Push to Greythr immediately after each employee recognition
        echo "Pushing attendance data for $EMPLOYEE_ID to Greythr..." | tee -a "$LOG_FILE"
        
        # Create a temporary file with just this one record (including header)
        TEMP_CSV=$(mktemp)
        echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$TEMP_CSV"
        echo "\"$FORMATTED_TIMESTAMP\",\"$CAMERA\",\"$EMPLOYEE_ID\",\"$CONFIDENCE\",\"$FACE_ID\",\"$IMG_FILE\"" >> "$TEMP_CSV"
        
        if python3 /home/ubuntu/greythr_push_attendance.py "$TEMP_CSV"; then
            echo "Attendance for $EMPLOYEE_ID successfully pushed to Greythr" | tee -a "$LOG_FILE"
        else
            echo "Failed to push attendance for $EMPLOYEE_ID to Greythr (exit code $?)" | tee -a "$LOG_FILE"
        fi
        
        # Clean up temp file
        rm "$TEMP_CSV"
    fi
    
    # Also log the result
    echo "Result for $FILENAME: $RESULT" >> "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
echo "Recognition CSV file created at $RECOG_CSV_FILE"
echo "Attendance CSV file created at $ATTENDANCE_CSV_FILE"

echo "Process completed at $(date)" | tee -a "$LOG_FILE"
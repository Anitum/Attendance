#!/bin/bash

# Get today's date in YYYYMMDD format
TODAY=$(date +"%Y%m%d")
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
ATTENDANCE_CSV_FILE="$RESULTS_DIR/recognition_results_$TODAY_DASH.csv"

# Create CSV headers
echo "Filename,Result" > "$RECOG_CSV_FILE"
echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$ATTENDANCE_CSV_FILE"

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
    
    # Append to recognition CSV file - escape quotes in the result to avoid CSV formatting issues
    ESCAPED_RESULT=$(echo "$RESULT" | sed 's/"/""/g')
    echo "\"$FILENAME\",\"$ESCAPED_RESULT\"" >> "$RECOG_CSV_FILE"
    
    # Parse the result to extract employee information for attendance CSV
    # Assuming the result JSON contains something like "name": "employee_name"
    # Extract the employee name/ID from the JSON result
    EMPLOYEE_ID=$(echo "$RESULT" | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    CONFIDENCE=$(echo "$RESULT" | grep -o '"confidence"[[:space:]]*:[[:space:]]*[0-9.]*' | awk '{print $2}')
    FACE_ID=$(echo "$RESULT" | grep -o '"face_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    
    # Only add to attendance CSV if an employee was recognized
    if [ ! -z "$EMPLOYEE_ID" ] && [ "$EMPLOYEE_ID" != "unknown" ]; then
        # Get current timestamp
        TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
        CAMERA="main_entrance"  # You can customize this

        # Add to attendance CSV
        echo "\"$TIMESTAMP\",\"$CAMERA\",\"$EMPLOYEE_ID\",\"$CONFIDENCE\",\"$FACE_ID\",\"$IMG_FILE\"" >> "$ATTENDANCE_CSV_FILE"
        
        echo "Added attendance record for $EMPLOYEE_ID" | tee -a "$LOG_FILE"
    fi
    
    # Also log the result
    echo "Result for $FILENAME: $RESULT" >> "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
echo "Recognition CSV file created at $RECOG_CSV_FILE"
echo "Attendance CSV file created at $ATTENDANCE_CSV_FILE"

# Now push the attendance data to Greythr
echo "Pushing attendance data to Greythr..." | tee -a "$LOG_FILE"
python3 /home/ubuntu/greythr_push_attendance.py
echo "Attendance push process started in background" | tee -a "$LOG_FILE"
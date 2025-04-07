#!/bin/bash

# Get today's date in YYYYMMDD format
TODAY=$(date +"%Y%m%d")
TODAY_HYPHEN=$(date +"%Y-%m-%d")

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

# Attendance CSV file - now in the same directory as results
ATTENDANCE_FILE="$RESULTS_DIR/attendance_$TODAY_HYPHEN.csv"

# Create CSV header
echo "Filename,Result" > "$CSV_FILE"

# Create attendance CSV header if it doesn't exist
if [ ! -f "$ATTENDANCE_FILE" ]; then
    echo "Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath" > "$ATTENDANCE_FILE"
fi

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
    
    # Extract face recognition data and append to attendance CSV
    python3 -c "
import json
import sys
import os
from datetime import datetime

try:
    # Parse the JSON result
    result = json.loads('''$RESULT''')
    
    # If there are faces in the result
    if 'faces' in result and result['faces']:
        for face in result['faces']:
            if 'match' in face and face['match'] and face['match'].get('person_id'):
                # Get current timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Extract camera info from filename if available (this is an example, adjust as needed)
                camera = 'unknown'
                if '_cam' in '$FILENAME':
                    camera = '$FILENAME'.split('_cam')[1].split('_')[0]
                
                # Get employee ID
                employee_id = face['match']['person_id']
                
                # Get confidence score
                confidence = face['match'].get('confidence', 0)
                
                # Get face ID
                face_id = face.get('face_id', 'unknown')
                
                # Get image path
                image_path = os.path.abspath('$IMG_FILE')
                
                # Create CSV line
                csv_line = f'\"{timestamp}\",\"{camera}\",\"{employee_id}\",\"{confidence}\",\"{face_id}\",\"{image_path}\"'
                
                # Print the CSV line (will be captured and written to the file)
                print(csv_line)
except Exception as e:
    sys.stderr.write(f'Error processing JSON: {str(e)}\\n')
    exit(1)
" >> "$ATTENDANCE_FILE" 2>> "$LOG_FILE"
done

echo "Face recognition completed at $(date)" | tee -a "$LOG_FILE"
echo "Results saved to $RESULTS_DIR"
echo "CSV file created at $CSV_FILE"
echo "Attendance data recorded at $ATTENDANCE_FILE"

# Modify the environment variable for the attendance directory before running the script
echo "Starting attendance pusher..." | tee -a "$LOG_FILE"
ATTENDANCE_DIR="$RESULTS_DIR" python3 -c "
import os
import sys

# Override the attendance directory in the greythr_push_attendance.py script
attendance_script = '/home/ubuntu/greythr_push_attendance.py'
with open(attendance_script, 'r') as f:
    script_content = f.read()

# Replace the attendance directory with our environment variable
import re
modified_content = re.sub(
    r'ATTENDANCE_DIR\s*=\s*os\.path\.expanduser\(\"~/testing_greythr_attendance\"\)', 
    f'ATTENDANCE_DIR = \"{os.environ[\"ATTENDANCE_DIR\"]}\"', 
    script_content
)

# Execute the modified script
exec(modified_content)
" &
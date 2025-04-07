#!/bin/bash

# Define directories and files
INPUT_DIR="/home/ubuntu/faceDetections90/2025-03-17"
OUTPUT_FILE="time_name_results.txt"
FACE_RECOGNITION_SCRIPT="/home/ubuntu/Face_Recognition_just_json.py"
DEBUG_FILE="debug_face_recognition.txt"

# Clear previous output and debug files
> "$OUTPUT_FILE"
> "$DEBUG_FILE"

# Process each image in the input directory
for image_file in "$INPUT_DIR"/*.jpg; do
    if [ -f "$image_file" ]; then
        # Extract the time from the filename
        # Format: 20250317_085437_210135_confidence_95.jpg
        filename=$(basename "$image_file")
        
        # Extract the time portion using a more robust pattern matching
        if [[ $filename =~ ([0-9]{8})_([0-9]{6})_ ]]; then
            time_raw="${BASH_REMATCH[2]}"
            
            hour=${time_raw:0:2}
            minute=${time_raw:2:2}
            second=${time_raw:4:2}
            formatted_time="$hour:$minute:$second"
            
            # Run face recognition on the image and capture full response
            echo "Processing: $image_file" >> "$DEBUG_FILE"
            result=$(python3 "$FACE_RECOGNITION_SCRIPT" "$image_file")
            echo "Raw result: $result" >> "$DEBUG_FILE"
            
            # Parse the JSON properly using jq if available
            if command -v jq > /dev/null; then
                employee_id=$(echo "$result" | jq -r '.employee_id')
                confidence=$(echo "$result" | jq -r '.confidence')
                echo "Parsed with jq: employee_id=$employee_id, confidence=$confidence" >> "$DEBUG_FILE"
            else
                # Fallback to grep/cut if jq is not available
                employee_id=$(echo "$result" | grep -o '"employee_id":[^,}]*' | cut -d':' -f2 | tr -d '"' | tr -d ' ')
                confidence=$(echo "$result" | grep -o '"confidence":[^,}]*' | cut -d':' -f2 | tr -d ' ')
                echo "Parsed with grep: employee_id=$employee_id, confidence=$confidence" >> "$DEBUG_FILE"
            fi
            
            # Validate the employee_id
            if [[ -n "$employee_id" && "$employee_id" != "No match found" && "$employee_id" != "Error" ]]; then
                # Write the time and name to the output file
                echo "$formatted_time,$employee_id" >> "$OUTPUT_FILE"
                echo "Successfully processed: $formatted_time,$employee_id" >> "$DEBUG_FILE"
            else
                echo "No valid match for $filename" >> "$DEBUG_FILE"
            fi
        else
            echo "Could not extract time from filename: $filename" >> "$DEBUG_FILE"
        fi
    fi
done

echo "Processing complete. Results saved to $OUTPUT_FILE"
echo "Debug information saved to $DEBUG_FILE"
#!/bin/bash

# Define directories and files
INPUT_DIR="/home/ubuntu/faceDetections90/2025-03-17"
OUTPUT_FILE="time_name_results.txt"
FACE_RECOGNITION_SCRIPT="/home/ubuntu/Face_Recognition_just_json.py"

# Clear previous output file
> "$OUTPUT_FILE"

# Process each image in the input directory
for image_file in "$INPUT_DIR"/*.jpg; do
    if [ -f "$image_file" ]; then
        # Extract the time from the filename
        # Format: 20250317_085437_210135_confidence_95.jpg
        filename=$(basename "$image_file")
        
        # Extract the time portion (085437) and format it with colons (08:54:37)
        time_raw=$(echo "$filename" | grep -o "[0-9]\{6\}" | sed -n '2p')
        if [ -z "$time_raw" ]; then
            # If we can't find a second group of 6 digits, try the first one
            time_raw=$(echo "$filename" | grep -o "[0-9]\{6\}")
        fi
        
        if [ -n "$time_raw" ]; then
            hour=${time_raw:0:2}
            minute=${time_raw:2:2}
            second=${time_raw:4:2}
            formatted_time="$hour:$minute:$second"
            
            # Run face recognition on the image
            result=$(python3 "$FACE_RECOGNITION_SCRIPT" "$image_file")
            
            # Extract employee_id (name) from the JSON output
            employee_id=$(echo "$result" | grep -o '"employee_id": "[^"]*"' | cut -d'"' -f4)
            
            # Skip if no match or error
            if [[ "$employee_id" != "No match found" && "$employee_id" != "Error" ]]; then
                # Write the time and name to the output file
                echo "$formatted_time,$employee_id" >> "$OUTPUT_FILE"
                echo "Processed $filename: $formatted_time,$employee_id"
            else
                echo "No valid match for $filename"
            fi
        else
            echo "Could not extract time from filename: $filename"
        fi
    fi
done

echo "Processing complete. Results saved to $OUTPUT_FILE"
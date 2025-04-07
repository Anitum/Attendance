import csv
import datetime
import sys
from pathlib import Path
import time
from datetime import timedelta

def process_lines_to_csv():
    # Get today's date for the output filename
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    output_dir = Path('/home/ubuntu/testing_greythr_attendance')
    output_file = output_dir / f'attendance_{today}.csv'
    
    # Create directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read all input lines
    lines = [line.strip() for line in sys.stdin if line.strip()]
    
    # Parse timestamps from input to calculate relative time differences
    timestamps = []
    data_rows = []
    
    for line in lines:
        parts = line.split(',', 5)
        if len(parts) >= 5:
            try:
                # Parse the timestamp
                timestamp_str = parts[0]
                timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                timestamps.append(timestamp)
                data_rows.append(parts)
            except ValueError:
                # If timestamp parsing fails, just skip this line
                continue
    
    if not timestamps:
        print("No valid timestamps found in input.")
        return
    
    # Calculate time differences
    start_time = timestamps[0]
    time_diffs = [(t - start_time).total_seconds() for t in timestamps]
    
    # Scale time differences by a factor of 3
    scaled_diffs = [diff * 3 for diff in time_diffs]
    
    # Set the start time to now
    current_time = datetime.datetime.now()
    
    # Open the CSV file for writing
    with open(output_file, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        # Write header
        csv_writer.writerow(['timestamp', 'camera_id', 'person_name', 'confidence', 'person_id', 'image_path'])
        
        # Process each data row with the new timestamps
        for i, parts in enumerate(data_rows):
            # Calculate the new timestamp
            new_timestamp = current_time + timedelta(seconds=scaled_diffs[i])
            timestamp_str = new_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # Update the timestamp in the data
            parts[0] = timestamp_str
            
            # Write to CSV
            csv_writer.writerow(parts)
            
            # If this is the last entry, we're done
            if i == len(data_rows) - 1:
                break
                
            # Calculate delay until next entry should be written
            if i < len(scaled_diffs) - 1:
                delay = scaled_diffs[i+1] - scaled_diffs[i]
                if delay > 0:
                    time.sleep(delay)
    
    print(f"CSV file created at: {output_file}")

if __name__ == "__main__":
    print("Paste your data below. Press Ctrl+D (Unix/Linux) or Ctrl+Z followed by Enter (Windows) when done:")
    process_lines_to_csv()
import csv
import datetime
import sys
from pathlib import Path

def process_lines_to_csv():
    # Get today's date for the output filename
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    output_dir = Path('/home/ubuntu/testing_greythr_attendance')
    output_file = output_dir / f'attendance_{today}.csv'
    
    # Create directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Today's date for replacing in timestamps
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Open the CSV file for writing
    with open(output_file, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        # Write header
        csv_writer.writerow(['timestamp', 'camera_id', 'person_name', 'confidence', 'person_id', 'image_path'])
        
        # Process each line from stdin
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
                
            # Split the line by comma
            parts = line.split(',', 5)
            
            if len(parts) >= 5:
                # Extract timestamp and replace the date with today's date
                timestamp = parts[0]
                if timestamp.count('-') == 2:  # Ensure it's a timestamp
                    # Keep the time part, replace the date part
                    time_part = timestamp.split(' ')[1] if ' ' in timestamp else ''
                    updated_timestamp = f"{today_date} {time_part}"
                    parts[0] = updated_timestamp
                
                # Write the updated line to CSV
                csv_writer.writerow(parts)
            
    print(f"CSV file created at: {output_file}")

if __name__ == "__main__":
    print("Paste your data below. Press Ctrl+D (Unix/Linux) or Ctrl+Z followed by Enter (Windows) when done:")
    process_lines_to_csv()
#!/usr/bin/env python3
import os
import re
import datetime

def convert_utc_to_ist_in_filename(filepath):
    # Extract the directory, base filename, and extension
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    
    # Regular expression to find UTC timestamp in format YYYYMMDDTHHMMSS
    pattern = r'(\d{8})T(\d{2})(\d{2})(\d{2})'
    
    match = re.search(pattern, filename)
    if not match:
        print(f"No timestamp found in format YYYYMMDDTHHMMSS in {filename}")
        return filepath
    
    # Extract timestamp components
    date_str, hour_str, min_str, sec_str = match.groups()
    
    # Convert to datetime object (UTC)
    year = int(date_str[0:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])
    hour = int(hour_str)
    minute = int(min_str)
    second = int(sec_str)
    
    utc_time = datetime.datetime(year, month, day, hour, minute, second)
    
    # Convert to IST (UTC+5:30)
    time_diff = datetime.timedelta(hours=5, minutes=30)
    ist_time = utc_time + time_diff
    
    # Format the new timestamp
    ist_timestamp = ist_time.strftime("%H%M%S")
    
    # Replace the original timestamp with IST (without brackets)
    new_filename = re.sub(
        pattern, 
        f"{date_str}T{ist_timestamp}", 
        filename
    )
    
    # Construct the new full path
    new_filepath = os.path.join(directory, new_filename)
    
    return new_filepath

# Example usage
if __name__ == "__main__":
    original_filepath = "/home/ubuntu/channel401_20250310T054344.mkv"
    new_filepath = convert_utc_to_ist_in_filename(original_filepath)
    print(f"Original: {original_filepath}")
    print(f"Converted: {new_filepath}")
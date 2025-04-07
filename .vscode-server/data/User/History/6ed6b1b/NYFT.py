#!/usr/bin/env python3
import os
import re
import datetime
import glob

def convert_utc_to_ist_in_filename(filepath):
    # Extract the directory, base filename, and extension
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    
    # Regular expression to find timestamp in format YYYYMMDDTHHMMSS
    pattern = r'(\d{8})T(\d{2})(\d{2})(\d{2})'
    
    match = re.search(pattern, filename)
    if not match:
        print(f"No timestamp found in format YYYYMMDDTHHMMSS in {filename}")
        return None
    
    # Extract timestamp components
    date_str, hour_str, min_str, sec_str = match.groups()
    
    # Check if the hour value is 11 or greater, which suggests it might already be in IST
    hour = int(hour_str)
    if hour >= 11:
        print(f"File {filename} might already be in IST (hour >= 11), skipping")
        return filepath
    
    # Convert to datetime object (UTC)
    year = int(date_str[0:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])
    minute = int(min_str)
    second = int(sec_str)
    
    utc_time = datetime.datetime(year, month, day, hour, minute, second)
    
    # Convert to IST (UTC+5:30)
    time_diff = datetime.timedelta(hours=5, minutes=30)
    ist_time = utc_time + time_diff
    
    # Format the new timestamp
    ist_timestamp = ist_time.strftime("%H%M%S")
    
    # Replace the original timestamp with IST
    new_filename = re.sub(
        pattern, 
        f"{date_str}T{ist_timestamp}", 
        filename
    )
    
    # Construct the new full path
    new_filepath = os.path.join(directory, new_filename)
    
    return new_filepath

def process_directory(directory_path, preview_only=True):
    """
    Process all MKV files in the specified directory
    
    Args:
        directory_path: Path to search for MKV files
        preview_only: If True, only show changes without renaming files
    """
    # Find all MKV files in the directory
    mkv_files = glob.glob(os.path.join(directory_path, "*.mkv"))
    
    if not mkv_files:
        print(f"No MKV files found in {directory_path}")
        return
    
    print(f"Found {len(mkv_files)} MKV files")
    
    converted_count = 0
    skipped_count = 0
    no_change_count = 0
    
    for file_path in mkv_files:
        new_file_path = convert_utc_to_ist_in_filename(file_path)
        
        if new_file_path is None:
            # No timestamp pattern found or other error
            skipped_count += 1
        elif new_file_path != file_path:
            # Needs conversion
            if preview_only:
                print(f"Would rename: {os.path.basename(file_path)} -> {os.path.basename(new_file_path)}")
            else:
                try:
                    os.rename(file_path, new_file_path)
                    print(f"Renamed: {os.path.basename(file_path)} -> {os.path.basename(new_file_path)}")
                except Exception as e:
                    print(f"Error renaming {file_path}: {e}")
                    skipped_count += 1
                    continue
            converted_count += 1
        else:
            # No change needed (either already IST or other reason)
            if "might already be in IST" not in file_path:
                print(f"No change needed for {os.path.basename(file_path)}")
                no_change_count += 1
    
    print("\nSummary:")
    print(f"- Files to be converted: {converted_count}")
    print(f"- Files skipped (possible IST or errors): {skipped_count}")
    print(f"- Files with no changes needed: {no_change_count}")

# Example usage
if __name__ == "__main__":
    import sys
    
    # Default directory is the current directory
    directory = "."
    preview_mode = True
    
    # Parse command-line arguments
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2].lower() == "apply":
        preview_mode = False
    
    print(f"Scanning directory: {os.path.abspath(directory)}")
    print(f"Mode: {'Preview (no changes will be made)' if preview_mode else 'Apply (files will be renamed)'}")
    
    process_directory(directory, preview_mode)
    
    if preview_mode:
        print("\nTo apply these changes, run the script with 'apply' as the second argument:")
        print(f"python {sys.argv[0]} {directory} apply")
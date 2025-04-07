#!/usr/bin/env python3
import os
import json
import csv
import subprocess
import logging
from datetime import datetime, timedelta
import time
import re

# Configuration
RECOGNITION_DIR = "/home/ubuntu/face_recognition_results"
EMPLOYEE_MAPPING_FILE = "/home/ubuntu/greythr_employee_mapping.json"
ENTRY_SCRIPT = "/home/ubuntu/entry.sh"  
LOG_FILE = os.path.expanduser("~/logs/attendance_processor.log")

# Configure logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_employee_mapping():
    """Load employee mapping from JSON file"""
    try:
        with open(EMPLOYEE_MAPPING_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load employee mapping: {e}")
        return {}

def get_today_recognition_file():
    """Get the recognition results CSV file for today"""
    today = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(RECOGNITION_DIR, f"recognition_results_{today}.csv")

def parse_timestamp_from_filename(filename):
    """Extract timestamp from filename format like channel401_track0_channel401_20250318T090600"""
    match = re.search(r'(\d{8})T(\d{6})', filename)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        
        # Format: YYYYMMDD and HHMMSS
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        hour = time_str[:2]
        minute = time_str[2:4]
        second = time_str[4:6]
        
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"
    return None

def process_attendance():
    """Process recognition data and send to GreyTHR"""
    # Load employee mapping
    employee_mapping = load_employee_mapping()
    
    # Create attendance state dictionary (0 = out/not seen, 1 = in/seen)
    attendance_state = {name: 0 for _, name in employee_mapping.items()}
    
    if not os.path.exists(RECOGNITION_DIR):
        logging.error(f"Recognition directory not found: {RECOGNITION_DIR}")
        return
    
    # Keep track of last processed line
    last_processed_line = 0
    current_file = ""
    
    while True:
        # Get today's recognition file - needs to be refreshed on each iteration
        recognition_file = get_today_recognition_file()
        
        if not os.path.exists(recognition_file):
            logging.info(f"No recognition file found for today: {recognition_file}")
            time.sleep(60)
            continue
        
        # If we're processing a new file, reset the line counter
        if current_file != recognition_file:
            current_file = recognition_file
            last_processed_line = 0
        
        new_entries = []
        
        # Read the recognition CSV file
        try:
            with open(recognition_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                # Skip header if this is the first time reading
                if last_processed_line == 0 and len(rows) > 0:
                    last_processed_line = 1
                
                # Process only new entries
                if len(rows) > last_processed_line:
                    new_entries = rows[last_processed_line:]
                    last_processed_line = len(rows)
        except Exception as e:
            logging.error(f"Error reading recognition file: {e}")
            time.sleep(60)
            continue
        
        # Process new entries
        for entry in new_entries:
            try:
                if len(entry) < 2:
                    logging.warning(f"Invalid entry format: {entry}")
                    continue
                    
                filename, result_json_str = entry
                
                # Parse the result JSON
                try:
                    result_json = json.loads(result_json_str.replace('""', '"'))
                    employee_id = result_json.get("employee_id")
                    confidence = result_json.get("confidence", 0)
                    face_id = result_json.get("face_id", "")
                    
                    # Skip if no match found or confidence too low
                    if employee_id == "No match found" or confidence < 70:
                        continue
                    
                    # Extract timestamp from filename
                    timestamp = parse_timestamp_from_filename(filename)
                    if not timestamp:
                        logging.warning(f"Could not parse timestamp from filename: {filename}")
                        continue
                        
                    employee_name = employee_id  # In this case, employee_id is already the name like "merwin_mathew"
                    
                    # Get the actual ID for this employee from our mapping
                    employee_id_for_greythr = None
                    for id_key, name in employee_mapping.items():
                        if name == employee_name:
                            employee_id_for_greythr = id_key
                            break
                    
                    if not employee_id_for_greythr:
                        logging.warning(f"No mapping found for employee: {employee_name}")
                        continue
                    
                    # Check if this employee has already been processed
                    if attendance_state.get(employee_name, 0) == 1:
                        logging.info(f"Employee {employee_name} already marked present today")
                        continue
                    
                    # Mark the employee as present
                    attendance_state[employee_name] = 1
                    
                    # Parse the timestamp to datetime object
                    try:
                        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        # Format for entry.sh (using YYYY-MM-DD HH:MM format)
                        formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                        
                        # Send to GreyTHR using entry.sh
                        send_to_greythr(employee_id_for_greythr, formatted_time)
                        
                        logging.info(f"Successfully processed attendance for {employee_name} at {formatted_time}")
                    except ValueError as e:
                        logging.error(f"Invalid timestamp format: {timestamp}, error: {e}")
                        continue
                        
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON: {result_json_str}, error: {e}")
                    continue
                
            except Exception as e:
                logging.error(f"Error processing entry {entry}: {e}")
        
        # Sleep before checking for new entries
        time.sleep(60)

def send_to_greythr(employee_id, formatted_time):
    """Send attendance data to GreyTHR using the entry.sh script"""
    try:
        # Execute the entry script with employee ID and formatted time
        cmd = [ENTRY_SCRIPT, employee_id, formatted_time]
        logging.info(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"Successfully sent attendance for employee {employee_id}: {result.stdout}")
        else:
            logging.error(f"Failed to send attendance: {result.stderr}")
            
    except Exception as e:
        logging.error(f"Failed to send data to GreyTHR: {str(e)}")

if __name__ == "__main__":
    logging.info("Starting attendance processor")
    try:
        process_attendance()
    except KeyboardInterrupt:
        logging.info("Attendance processor stopped")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
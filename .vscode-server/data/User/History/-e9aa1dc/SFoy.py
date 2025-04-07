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
ATTENDANCE_DIR = os.path.expanduser("~/Attendance")
EMPLOYEE_MAPPING_FILE = "/home/ubuntu/employee_mapping.json"
GREYTHR_SCRIPT = "/home/ubuntu/greythr_push_data.sh"
LOG_FILE = os.path.expanduser("~/logs/attendance_processor.log")

# Door configurations for GreyTHR
DOOR_NAME = "Main Door"
DOOR_ID = "1"

# Configure logging
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

def get_today_attendance_file():
    """Get the attendance CSV file for today"""
    today = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(ATTENDANCE_DIR, f"attendance_{today}.csv")

def process_attendance():
    """Process attendance data and send to GreyTHR"""
    # Load employee mapping
    employee_mapping = load_employee_mapping()
    
    # Create attendance state dictionary (0 = out/not seen, 1 = in/seen)
    attendance_state = {name: 0 for _, name in employee_mapping.items()}
    
    # Get today's attendance file
    attendance_file = get_today_attendance_file()
    
    if not os.path.exists(attendance_file):
        logging.info(f"No attendance file found for today: {attendance_file}")
        return
    
    # Keep track of last processed line
    last_processed_line = 0
    
    while True:
        new_entries = []
        
        # Read the attendance CSV file
        try:
            with open(attendance_file, 'r') as f:
                reader = csv.reader(f)
                # Skip header if this is the first time reading
                if last_processed_line == 0:
                    next(reader)
                    last_processed_line = 1
                
                # Process only new entries
                rows = list(reader)
                if len(rows) > last_processed_line - 1:
                    new_entries = rows[last_processed_line - 1:]
                    last_processed_line = len(rows) + 1
        except Exception as e:
            logging.error(f"Error reading attendance file: {e}")
            time.sleep(60)
            continue
        
        # Process new entries
        for entry in new_entries:
            try:
                timestamp, camera, employee_id, confidence, face_id, image_path = entry
                
                # Extract name from employee_id (assuming format like "gbhadra_nair")
                employee_name = employee_id
                
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
                
                # Convert timestamp to GreyTHR format (using the detected time from face recognition)
                # Parse the timestamp to datetime object
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                
                # Format for GreyTHR (adding milliseconds and timezone)
                greythr_timestamp = dt.strftime('%Y-%m-%dT%H:%M:%S.654+05:30')
                
                # Create swipe data for GreyTHR
                # Format: timestamp,door_id,door_name,direction (1=in, 0=out)
                swipe_data = f"{greythr_timestamp},{DOOR_ID},{DOOR_NAME},1"
                
                # Send to GreyTHR
                send_to_greythr(employee_id_for_greythr, swipe_data)
                
                logging.info(f"Successfully processed attendance for {employee_name}")
                
            except Exception as e:
                logging.error(f"Error processing entry {entry}: {e}")
        
        # Sleep before checking for new entries
        time.sleep(60)

def send_to_greythr(employee_id, swipe_data):
    """Send attendance data to GreyTHR using the shell script"""
    try:
        # Create temporary file with swipe data
        with open('/tmp/swipes.txt', 'w') as f:
            f.write(swipe_data)
        
        # Set environment variable for the employee ID
        os.environ['EMPLOYEE_ID'] = employee_id
        
        # Execute the GreyTHR script
        subprocess.run([GREYTHR_SCRIPT, '/tmp/swipes.txt', employee_id], check=True)
        
        logging.info(f"Sent attendance data to GreyTHR for employee {employee_id}")
    except Exception as e:
        logging.error(f"Failed to send data to GreyTHR: {e}")

if __name__ == "__main__":
    logging.info("Starting attendance processor")
    try:
        process_attendance()
    except KeyboardInterrupt:
        logging.info("Attendance processor stopped")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
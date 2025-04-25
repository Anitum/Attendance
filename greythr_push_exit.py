#!/usr/bin/env python3
import os
import json
import csv
import subprocess
import logging
from datetime import datetime, timedelta
import time
import re
import sys

# Configuration
RECOGNITION_DIR = "/home/ubuntu/face_recognition_results"
EMPLOYEE_MAPPING_FILE = "/home/ubuntu/greythr_employee_mapping.json"
EXIT_SCRIPT = "/home/ubuntu/exit.sh"
LOG_FILE = os.path.expanduser("~/logs/exit_attendance_processor.log")

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

def get_today_attendance_file():
    """Get the attendance results CSV file for today"""
    today = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(RECOGNITION_DIR, f"attendance_results_{today}.csv")

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

def get_processed_entry_file(date=None):
    """Get the entry processed record file for a specific date"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(RECOGNITION_DIR, f"processed_greythr_{date}.json")

def create_processed_record_file():
    """Create the daily processed exit record file if it doesn't exist"""
    today = datetime.now().strftime('%Y-%m-%d')
    processed_file = os.path.join(RECOGNITION_DIR, f"processed_exit_greythr_{today}.json")
    if not os.path.exists(processed_file):
        with open(processed_file, 'w') as f:
            json.dump({}, f)
    return processed_file

def is_employee_already_processed(employee_name):
    """Check if employee exit was already processed today"""
    processed_file = create_processed_record_file()
    try:
        with open(processed_file, 'r') as f:
            processed_records = json.load(f)
            return employee_name in processed_records
    except Exception as e:
        logging.error(f"Error checking processed exit record: {e}")
        return False

def mark_employee_as_processed(employee_name, timestamp):
    """Mark that an employee exit has been processed"""
    processed_file = create_processed_record_file()
    try:
        with open(processed_file, 'r') as f:
            processed_records = json.load(f)
        
        processed_records[employee_name] = {
            "timestamp": timestamp,
            "processed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(processed_file, 'w') as f:
            json.dump(processed_records, f, indent=2)
    except Exception as e:
        logging.error(f"Error updating processed exit record: {e}")

def get_last_detection_times():
    """Find the last detection time for each employee from today's attendance file"""
    attendance_file = get_today_attendance_file()
    employee_last_times = {}
    
    if not os.path.exists(attendance_file):
        logging.warning(f"Attendance file not found: {attendance_file}")
        return employee_last_times
    
    try:
        with open(attendance_file, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            
            for row in reader:
                try:
                    if len(row) < 6:
                        continue
                    
                    timestamp_str = row[0].strip('"')
                    employee_id = row[2].strip('"')
                    confidence = float(row[3].strip('"'))
                    
                    # Skip low confidence detections
                    if confidence < 70:
                        continue
                    
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Update last time if it's the first detection or a later one
                    if employee_id not in employee_last_times or timestamp > employee_last_times[employee_id]:
                        employee_last_times[employee_id] = timestamp
                
                except Exception as e:
                    logging.error(f"Error processing attendance row: {e}")
                    
        return employee_last_times
    
    except Exception as e:
        logging.error(f"Error reading attendance file: {e}")
        return {}

def process_employees_without_exit():
    """Check for employees who have an entry but no exit record and process them with 5 PM exit time"""
    today = datetime.now().strftime('%Y-%m-%d')
    entry_file = get_processed_entry_file(today)
    exit_file = create_processed_record_file()
    employee_mapping = load_employee_mapping()
    
    # Check if entry file exists
    if not os.path.exists(entry_file):
        logging.warning(f"Entry file not found: {entry_file}")
        return
    
    try:
        # Load entry records
        with open(entry_file, 'r') as f:
            entry_records = json.load(f)
        
        # Load exit records
        with open(exit_file, 'r') as f:
            exit_records = json.load(f)
        
        # Fixed exit time at 5 PM
        exit_time = f"{today} 17:00"
        
        # Process each employee who has an entry but no exit
        for employee_name in entry_records:
            if employee_name not in exit_records:
                logging.info(f"Found employee {employee_name} with entry but no exit")
                
                # Get the actual ID for this employee from our mapping
                employee_id_for_greythr = None
                for id_key, name in employee_mapping.items():
                    if name == employee_name:
                        employee_id_for_greythr = id_key
                        break
                
                if not employee_id_for_greythr:
                    logging.warning(f"No mapping found for employee: {employee_name}")
                    continue
                
                # Send to GreyTHR using exit.sh
                send_to_greythr(employee_id_for_greythr, exit_time)
                
                # Mark as processed in persistent storage
                mark_employee_as_processed(employee_name, exit_time)
                
                logging.info(f"Successfully processed default EXIT for {employee_name} at {exit_time}")
    
    except Exception as e:
        logging.error(f"Error processing employees without exit: {e}")

def process_attendance():
    """Process recognition data and send exits to GreyTHR"""
    employee_mapping = load_employee_mapping()
    
    # Get the current hour
    current_hour = datetime.now().hour
    
    # Only process exits after 4 PM (16:00)
    if current_hour < 16:
        logging.info("Skipping exit processing - it's before 4 PM")
        time.sleep(60 * 10)  # Sleep for 10 minutes before checking again
        return
    
    # Get last detection times from today's attendance file
    employee_last_times = get_last_detection_times()
    
    if not employee_last_times:
        logging.info("No valid employee detection times found today")
        # Even if no detection times found, check for employees with entry but no exit
        if current_hour >= 17:  # Only after 5 PM
            process_employees_without_exit()
        time.sleep(60)
        return
    
    for employee_name, last_time in employee_last_times.items():
        try:
            # Check if the last detection time is after 4 PM
            if last_time.hour < 16:
                logging.info(f"Skipping {employee_name} - last detection at {last_time} is before 4 PM")
                continue
            
            # Check if exit was already processed today
            if is_employee_already_processed(employee_name):
                logging.info(f"Employee {employee_name} exit already processed today")
                continue
            
            # Get the actual ID for this employee from our mapping
            employee_id_for_greythr = None
            for id_key, name in employee_mapping.items():
                if name == employee_name:
                    employee_id_for_greythr = id_key
                    break
            
            if not employee_id_for_greythr:
                logging.warning(f"No mapping found for employee: {employee_name}")
                continue
            
            # Format for exit.sh (using YYYY-MM-DD HH:MM format)
            formatted_time = last_time.strftime('%Y-%m-%d %H:%M')
            
            # Send to GreyTHR using exit.sh
            send_to_greythr(employee_id_for_greythr, formatted_time)
            
            # Mark as processed in persistent storage
            mark_employee_as_processed(employee_name, formatted_time)
            
            logging.info(f"Successfully processed EXIT for {employee_name} at {formatted_time}")
                
        except Exception as e:
            logging.error(f"Error processing exit for {employee_name}: {e}")
    
    # After processing detections, check for employees with entry but no exit
    if current_hour >= 17:  # Only after 5 PM
        process_employees_without_exit()
    
    # Sleep before checking again
    time.sleep(60 * 15)  # Check every 15 minutes

def process_attendance_file(csv_file):
    """Process a specific attendance CSV file and send exits to GreyTHR"""
    employee_mapping = load_employee_mapping()
    
    if not os.path.exists(csv_file):
        logging.error(f"Attendance CSV file not found: {csv_file}")
        return False
    
    # Dictionary to track last detection time for each employee
    employee_last_times = {}
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            # Skip the header row
            next(reader, None)
            
            for row in reader:
                try:
                    if len(row) < 6:
                        logging.warning(f"Invalid row format: {row}")
                        continue
                    
                    # Format: Timestamp,Camera,EmployeeID,Confidence,FaceID,ImagePath
                    timestamp_str = row[0].strip('"')
                    employee_name = row[2].strip('"')
                    confidence = float(row[3].strip('"'))
                    
                    # Skip if confidence too low
                    if confidence < 70:
                        logging.info(f"Skipping due to low confidence: {employee_name}, confidence: {confidence}")
                        continue
                    
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Update last time if it's the first detection or a later one
                    if employee_name not in employee_last_times or timestamp > employee_last_times[employee_name]:
                        employee_last_times[employee_name] = timestamp
                
                except Exception as e:
                    logging.error(f"Error processing row {row}: {e}")
            
        # Process last detection time for each employee for exit
        for employee_name, last_time in employee_last_times.items():
            try:
                # Only process exits if last detection is after 4 PM
                if last_time.hour < 16:
                    logging.info(f"Skipping {employee_name} - last detection at {last_time} is before 4 PM")
                    continue
                
                # Check if exit was already processed today
                if is_employee_already_processed(employee_name):
                    logging.info(f"Employee {employee_name} exit already processed today")
                    continue
                
                # Get the actual ID for this employee from our mapping
                employee_id_for_greythr = None
                for id_key, name in employee_mapping.items():
                    if name == employee_name:
                        employee_id_for_greythr = id_key
                        break
                
                if not employee_id_for_greythr:
                    logging.warning(f"No mapping found for employee: {employee_name}")
                    continue
                
                # Format for exit.sh (using YYYY-MM-DD HH:MM format)
                formatted_time = last_time.strftime('%Y-%m-%d %H:%M')
                
                # Send to GreyTHR using exit.sh
                send_to_greythr(employee_id_for_greythr, formatted_time)
                
                # Mark as processed in persistent storage
                mark_employee_as_processed(employee_name, formatted_time)
                
                logging.info(f"Successfully processed EXIT for {employee_name} at {formatted_time}")
            
            except Exception as e:
                logging.error(f"Error processing exit for {employee_name}: {e}")
        
        # Check for employees with entry but no exit
        process_employees_without_exit()
        
        return True
    
    except Exception as e:
        logging.error(f"Error processing attendance file {csv_file}: {e}")
        return False

def send_to_greythr(employee_id, formatted_time):
    """Send exit attendance data to GreyTHR using the exit.sh script"""
    try:
        # Execute the exit script with employee ID and formatted time
        cmd = [EXIT_SCRIPT, employee_id, formatted_time]
        logging.info(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"Successfully sent EXIT for employee {employee_id}: {result.stdout}")
        else:
            logging.error(f"Failed to send EXIT: {result.stderr}")
            
    except Exception as e:
        logging.error(f"Failed to send EXIT data to GreyTHR: {str(e)}")

if __name__ == "__main__":
    logging.info("Starting EXIT attendance processor")
    try:
        # Check if a CSV file is provided as an argument
        if len(sys.argv) > 1:
            csv_file = sys.argv[1]
            logging.info(f"Processing specific exit attendance file: {csv_file}")
            if process_attendance_file(csv_file):
                logging.info(f"Successfully processed file: {csv_file}")
                sys.exit(0)
            else:
                logging.error(f"Failed to process file: {csv_file}")
                sys.exit(1)
        else:
            # If no file is provided, run the continuous monitoring process
            logging.info("Running in continuous monitoring mode for EXITS")
            while True:
                process_attendance()
    except KeyboardInterrupt:
        logging.info("EXIT attendance processor stopped")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)
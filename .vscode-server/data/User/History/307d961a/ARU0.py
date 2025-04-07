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
EMPLOYEE_EMAIL_MAPPING_FILE = "/home/ubuntu/employee_email_mapping.json"
LOG_FILE = os.path.expanduser("~/logs/email_attendance.log")
EMAIL_SUBJECT = "Attendance Recorded"

# Configure logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_employee_mapping():
    """Load employee email mapping from JSON file"""
    try:
        with open(EMPLOYEE_EMAIL_MAPPING_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load employee email mapping: {e}")
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
        
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        hour = time_str[:2]
        minute = time_str[2:4]
        second = time_str[4:6]
        
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"
    return None

def format_employee_name(employee_id):
    """Convert employee_id to formatted name (e.g., 'merwin_mathew' -> 'Merwin Mathew')"""
    return ' '.join([part.capitalize() for part in employee_id.split('_')])

def send_email(employee_name, employee_email, timestamp):
    """Send attendance email using mail command with personalized salutation"""
    try:
        formatted_name = format_employee_name(employee_name)
        body = f"""Dear {formatted_name},

Your attendance has been recorded at {timestamp}.

Best regards,
Attendance System"""
        
        cmd = [
            'mail',
            '-s', EMAIL_SUBJECT,
            employee_email
        ]
        
        logging.info(f"Sending email to {employee_email}")
        result = subprocess.run(
            cmd,
            input=body,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            logging.info(f"Email sent successfully to {employee_email}")
        else:
            logging.error(f"Email failed to {employee_email}: {result.stderr}")
            
    except Exception as e:
        logging.error(f"Email error: {str(e)}")

def process_attendance():
    """Process recognition data and send emails"""
    employee_mapping = load_employee_mapping()
    attendance_state = {name: 0 for name in employee_mapping.keys()}
    
    if not os.path.exists(RECOGNITION_DIR):
        logging.error(f"Recognition directory not found: {RECOGNITION_DIR}")
        return
    
    last_processed_line = 0
    current_file = ""
    
    while True:
        recognition_file = get_today_recognition_file()
        
        if not os.path.exists(recognition_file):
            logging.info(f"No recognition file found for today: {recognition_file}")
            time.sleep(60)
            continue
        
        if current_file != recognition_file:
            current_file = recognition_file
            last_processed_line = 0
        
        new_entries = []
        
        try:
            with open(recognition_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                if last_processed_line == 0 and len(rows) > 0:
                    last_processed_line = 1
                
                if len(rows) > last_processed_line:
                    new_entries = rows[last_processed_line:]
                    last_processed_line = len(rows)
        except Exception as e:
            logging.error(f"Error reading recognition file: {e}")
            time.sleep(60)
            continue
        
        for entry in new_entries:
            try:
                if len(entry) < 2:
                    logging.warning(f"Invalid entry format: {entry}")
                    continue
                    
                filename, result_json_str = entry
                
                try:
                    result_json = json.loads(result_json_str.replace('""', '"'))
                    employee_name = result_json.get("employee_id")
                    confidence = result_json.get("confidence", 0)
                    
                    if employee_name == "No match found" or confidence < 70:
                        continue
                    
                    timestamp = parse_timestamp_from_filename(filename)
                    if not timestamp:
                        logging.warning(f"Could not parse timestamp from filename: {filename}")
                        continue
                        
                    employee_email = employee_mapping.get(employee_name)
                    
                    if not employee_email:
                        logging.warning(f"No email mapping for employee: {employee_name}")
                        continue
                    
                    if attendance_state.get(employee_name, 0) == 1:
                        logging.info(f"Already sent email to {employee_name}")
                        continue
                    
                    formatted_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
                    send_email(employee_name, employee_email, formatted_time)
                    attendance_state[employee_name] = 1
                    
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON: {result_json_str}, error: {e}")
                    continue
                
            except Exception as e:
                logging.error(f"Error processing entry {entry}: {e}")
        
        time.sleep(60)

def process_attendance_file(csv_file):
    """Process a specific attendance CSV file and send emails"""
    employee_mapping = load_employee_mapping()
    attendance_state = {name: 0 for name in employee_mapping.keys()}
    
    if not os.path.exists(csv_file):
        logging.error(f"Attendance CSV file not found: {csv_file}")
        return False
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)
            
            for row in reader:
                try:
                    if len(row) < 6:
                        logging.warning(f"Invalid row format: {row}")
                        continue
                    
                    timestamp_str = row[0].strip('"')
                    employee_name = row[2].strip('"')
                    confidence = float(row[3].strip('"'))
                    
                    if confidence < 70:
                        continue
                    
                    employee_email = employee_mapping.get(employee_name)
                    
                    if not employee_email:
                        logging.warning(f"No email mapping for employee: {employee_name}")
                        continue
                    
                    if attendance_state.get(employee_name, 0) == 1:
                        logging.info(f"Already sent email to {employee_name}")
                        continue
                    
                    formatted_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
                    send_email(employee_name, employee_email, formatted_time)
                    attendance_state[employee_name] = 1
                    
                except Exception as e:
                    logging.error(f"Error processing row {row}: {e}")
            
        return True
    except Exception as e:
        logging.error(f"Error processing attendance file {csv_file}: {e}")
        return False

if __name__ == "__main__":
    logging.info("Starting email attendance processor")
    try:
        if len(sys.argv) > 1:
            csv_file = sys.argv[1]
            logging.info(f"Processing specific attendance file: {csv_file}")
            if process_attendance_file(csv_file):
                logging.info(f"Successfully processed file: {csv_file}")
                sys.exit(0)
            else:
                logging.error(f"Failed to process file: {csv_file}")
                sys.exit(1)
        else:
            logging.info("Running in continuous monitoring mode")
            process_attendance()
    except KeyboardInterrupt:
        logging.info("Email attendance processor stopped")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)
#!/usr/bin/env python3
# File name: send_exit_summary.py

import os
import json
import csv
import subprocess
import logging
from datetime import datetime
import sys
import re

# Configuration
RECOGNITION_DIR = "/home/ubuntu/face_recognition_results"
EMPLOYEE_EMAIL_MAPPING_FILE = "/home/ubuntu/employee_email_mapping.json"
LOG_FILE = os.path.expanduser("~/logs/exit_summary.log")
EMAIL_SUBJECT = "Daily Attendance Summary"

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

def format_employee_name(employee_id):
    """Convert employee_id to formatted name (e.g., 'merwin_mathew' -> 'Merwin Mathew')"""
    return ' '.join([part.capitalize() for part in employee_id.split('_')])

def send_email(employee_name, employee_email, entry_time, exit_time):
    """Send attendance summary email using mail command with personalized salutation"""
    try:
        formatted_name = format_employee_name(employee_name)
        body = f"""Dear {formatted_name},

Your attendance summary for today:
Entry Time: {entry_time}
Exit Time: {exit_time}

Thank you.
Best regards,
Attendance System"""
        
        cmd = [
            'mail',
            '-s', EMAIL_SUBJECT,
            employee_email
        ]
        
        logging.info(f"Sending exit summary email to {employee_email}")
        result = subprocess.run(
            cmd,
            input=body,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            logging.info(f"Exit summary email sent successfully to {employee_email}")
        else:
            logging.error(f"Exit summary email failed to {employee_email}: {result.stderr}")
            
    except Exception as e:
        logging.error(f"Email error: {str(e)}")

def process_exit_summary():
    """Process attendance data and send exit summary emails"""
    employee_mapping = load_employee_mapping()
    
    today = datetime.now().strftime('%Y-%m-%d')
    attendance_file = os.path.join(RECOGNITION_DIR, f"attendance_results_{today}.csv")
    
    if not os.path.exists(attendance_file):
        logging.error(f"Attendance file not found for today: {attendance_file}")
        return False
    
    # Dictionary to track first and last detections for each employee
    employee_times = {}
    
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
                    
                    # Skip if no email mapping
                    if employee_id not in employee_mapping:
                        continue
                    
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    if employee_id not in employee_times:
                        employee_times[employee_id] = {
                            'first': timestamp,
                            'last': timestamp
                        }
                    else:
                        # Update first time if earlier
                        if timestamp < employee_times[employee_id]['first']:
                            employee_times[employee_id]['first'] = timestamp
                        
                        # Update last time if later
                        if timestamp > employee_times[employee_id]['last']:
                            employee_times[employee_id]['last'] = timestamp
                
                except Exception as e:
                    logging.error(f"Error processing row {row}: {e}")
        
        # Send summary emails
        for employee_id, times in employee_times.items():
            employee_email = employee_mapping.get(employee_id)
            if not employee_email:
                continue
            
            entry_time = times['first'].strftime('%Y-%m-%d %H:%M:%S')
            exit_time = times['last'].strftime('%Y-%m-%d %H:%M:%S')
            
            send_email(employee_id, employee_email, entry_time, exit_time)
        
        return True
    
    except Exception as e:
        logging.error(f"Error processing exit summary: {e}")
        return False

if __name__ == "__main__":
    logging.info("Starting exit summary processor")
    try:
        if process_exit_summary():
            logging.info("Successfully processed exit summary")
            sys.exit(0)
        else:
            logging.error("Failed to process exit summary")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)
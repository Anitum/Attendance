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
EMPLOYEE_MAPPING_FILE = "/home/ubuntu/employee_email_mapping.json"  # Changed to email mapping
LOG_FILE = os.path.expanduser("~/logs/email_attendance.log")
EMAIL_SUBJECT = "Attendance Recorded"

# ... [keep other functions unchanged until process_attendance] ...

def send_email(employee_email, formatted_time):
    """Send attendance email using mail command"""
    try:
        body = f"Your attendance was recorded at {formatted_time}"
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
    attendance_state = {email: 0 for email in employee_mapping.values()}
    
    # ... [keep previous processing logic unchanged] ...
    
                    # Get email from mapping
                    employee_email = employee_mapping.get(employee_id)
                    
                    if not employee_email:
                        logging.warning(f"No email mapping for {employee_id}")
                        continue
                    
                    if attendance_state.get(employee_email, 0) == 1:
                        logging.info(f"Already sent email to {employee_email}")
                        continue
                    
                    # Send email
                    send_email(employee_email, formatted_time)
                    attendance_state[employee_email] = 1

# ... [keep rest of the code structure unchanged] ...

if __name__ == "__main__":
    logging.info("Starting email attendance processor")
    # ... [rest of main remains same] ...
#!/usr/bin/env python3
# File name: send_exit_notification.py

import os
import json
import csv
import subprocess
import logging
from datetime import datetime
import sys
import smtplib
from email.message import EmailMessage

# Configuration
RECOGNITION_DIR = "/home/ubuntu/face_recognition_results"
EMPLOYEE_EMAIL_MAPPING_FILE = "/home/ubuntu/employee_email_mapping.json"
LOG_FILE = os.path.expanduser("~/logs/exit_notification.log")
EMAIL_SUBJECT = "Exit Time Recorded"

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

def send_exit_email(employee_name, employee_email, exit_time):
    """Send exit time email using SMTP with authentication"""
    try:
        # Configuration (move these to top if needed by multiple functions)
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "anitum.data.logs@gmail.com"
        EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Set this in environment variables
        
        formatted_name = format_employee_name(employee_name)
        
        msg = EmailMessage()
        msg['Subject'] = EMAIL_SUBJECT
        msg['From'] = SENDER_EMAIL
        msg['To'] = employee_email
        
        body = f"""Dear {formatted_name},

Your exit has been recorded at {exit_time}.

Best regards,
Attendance System"""
        
        msg.set_content(body)

        # Send email using SMTP with TLS
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            
        logging.info(f"Exit notification sent successfully to {employee_email}")
            
    except Exception as e:
        logging.error(f"Email error: {str(e)}")
        raise

def process_exit_notifications():
    """Process attendance data and send exit time notifications"""
    employee_mapping = load_employee_mapping()
    
    today = datetime.now().strftime('%Y-%m-%d')
    attendance_file = os.path.join(RECOGNITION_DIR, f"attendance_results_{today}.csv")
    
    if not os.path.exists(attendance_file):
        logging.error(f"Attendance file not found for today: {attendance_file}")
        return False
    
    # Dictionary to track last detection time for each employee
    employee_last_times = {}
    
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
                    
                    # Update last time if it's the first detection or a later one
                    if employee_id not in employee_last_times or timestamp > employee_last_times[employee_id]:
                        employee_last_times[employee_id] = timestamp
                
                except Exception as e:
                    logging.error(f"Error processing row {row}: {e}")
        
        # Send exit notifications
        for employee_id, last_time in employee_last_times.items():
            employee_email = employee_mapping.get(employee_id)
            if not employee_email:
                continue
            
            exit_time = last_time.strftime('%Y-%m-%d %H:%M:%S')
            send_exit_email(employee_id, employee_email, exit_time)
        
        return True
    
    except Exception as e:
        logging.error(f"Error processing exit notifications: {e}")
        return False

if __name__ == "__main__":
    logging.info("Starting exit notification processor")
    try:
        if process_exit_notifications():
            logging.info("Successfully processed exit notifications")
            sys.exit(0)
        else:
            logging.error("Failed to process exit notifications")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)
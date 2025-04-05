#!/usr/bin/env python3
import csv
from datetime import datetime
from collections import defaultdict
import io
import sys
import argparse

def process_attendance(data):
    # Parse CSV data
    reader = csv.reader(io.StringIO(data))
    
    # Track persons and their attendance times
    attendance = defaultdict(list)
    error_count = 0
    
    # Skip header row if it exists
    first_row = True
    
    for row in reader:
        # Skip empty rows
        if not row:
            continue
            
        # Check if this might be a header row
        if first_row and (len(row) > 0 and (row[0].lower() == "timestamp" or 
                         not row[0].strip('"').replace('-', '').replace(':', '').replace(' ', '').isdigit())):
            first_row = False
            continue
        
        first_row = False
        
        # Ensure we have enough columns
        if len(row) < 6:
            print(f"Warning: Skipping row with insufficient columns: {row}")
            continue
            
        timestamp, location, person, confidence, uid, image_path = row
        
        # Clean input values
        timestamp = timestamp.strip('"')
        person = person.strip('"')
        confidence = confidence.strip('"')
        uid = uid.strip('"')
        
        # Skip error entries
        if person == "Error":
            error_count += 1
            continue
        
        try:
            # Convert timestamp to datetime object
            time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            
            # Add to attendance (with confidence as float)
            try:
                confidence_value = float(confidence)
                attendance[person].append((time, confidence_value, uid))
            except ValueError:
                # Skip records with invalid confidence values
                print(f"Warning: Invalid confidence value: {confidence} for {person}")
                continue
                
        except ValueError:
            print(f"Warning: Invalid timestamp format: {timestamp}")
            continue
    
    # Generate final attendance report
    final_attendance = []
    
    for person, records in attendance.items():
        if not records:
            continue
            
        # Sort records by timestamp
        sorted_records = sorted(records, key=lambda x: x[0])
        first_time = sorted_records[0][0]
        last_time = sorted_records[-1][0]
        duration = last_time - first_time
        avg_confidence = sum(r[1] for r in records) / len(records)
        
        final_attendance.append({
            "person": person,
            "first_seen": first_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen": last_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": str(duration),
            "recognition_count": len(records),
            "avg_confidence": f"{avg_confidence:.2f}%",
            "uid": sorted_records[0][2]  # Using the first UID encountered
        })
    
    return final_attendance, error_count

def format_attendance_report(attendance_data, error_count):
    if not attendance_data:
        return "No attendance records found."
    
    # Sort by person name
    sorted_attendance = sorted(attendance_data, key=lambda x: x["person"])
    
    report = ""
    for entry in sorted_attendance:
        report += f"{entry['person']}: {entry['first_seen']}\n"
    
    return report

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process attendance data from a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file containing attendance data')
    args = parser.parse_args()
    
    try:
        # Read from the specified CSV file
        with open(args.csv_file, 'r') as file:
            attendance_data = file.read()
            if not attendance_data.strip():
                print("Error: Empty attendance file")
                return 1
    except FileNotFoundError:
        print(f"Error: File '{args.csv_file}' not found")
        return 1
    
    # Process the attendance data
    attendance_list, error_count = process_attendance(attendance_data)
    
    # Print the formatted report
    print(format_attendance_report(attendance_list, error_count))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
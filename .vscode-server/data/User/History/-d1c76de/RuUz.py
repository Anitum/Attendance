import csv
from datetime import datetime, timedelta
from collections import defaultdict
import io

def process_attendance(data):
    # Parse CSV data
    reader = csv.reader(io.StringIO(data))
    
    # Get today's date
    today = datetime.now().date()
    
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
            
            # Only process records from today
            if time.date() == today:
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
    today = datetime.now().strftime("%Y-%m-%d")
    report = f"ATTENDANCE REPORT FOR {today}\n"
    report += "="*80 + "\n\n"
    
    if not attendance_data:
        report += "No attendance records found for today.\n"
        return report
    
    # Sort by person name
    sorted_attendance = sorted(attendance_data, key=lambda x: x["person"])
    
    for entry in sorted_attendance:
        report += f"Person: {entry['person']}\n"
        report += f"  First seen: {entry['first_seen']}\n"
        report += f"  Last seen: {entry['last_seen']}\n"
        report += f"  Duration: {entry['duration']}\n"
        report += f"  Recognition count: {entry['recognition_count']}\n"
        report += f"  Average confidence: {entry['avg_confidence']}\n"
        report += f"  UID: {entry['uid']}\n"
        report += "-"*50 + "\n"
    
    report += f"\nTotal people detected today: {len(attendance_data)}\n"
    report += f"Error entries today: {error_count}\n"
    
    return report

# Get the input data
def process_attendance_data(data):
    attendance_list, error_count = process_attendance(data)
    return format_attendance_report(attendance_list, error_count)

# Example usage
if __name__ == "__main__":
    # Read from a file instead of hardcoding
    try:
        with open('attendance.csv', 'r') as file:
            attendance_data = file.read()
            if not attendance_data.strip():
                print("Warning: Empty attendance file")
                attendance_data = ""
    except FileNotFoundError:
        # If file doesn't exist, use the data provided in the script
        print("Using example data (attendance.csv not found)")
        attendance_data = """
"channel101_track0_channel101_20250319T091630_0_2_confidence_62.jpg","{""employee_id"": ""ebin_jomon"", ""confidence"": 99.08502197265625, ""face_id"": ""7f7967ab-b948-458d-84a1-649fb55fe68c""}"
"channel101_track0_channel101_20250319T091930_0_1_confidence_80.jpg","{""employee_id"": ""ebin_jomon"", ""confidence"": 78.7154769897461, ""face_id"": ""7f7967ab-b948-458d-84a1-649fb55fe68c""}"
"channel101_track0_channel101_20250319T091930_0_2_confidence_78.jpg","{""employee_id"": ""ebin_jomon"", ""confidence"": 96.76811981201172, ""face_id"": ""7f7967ab-b948-458d-84a1-649fb55fe68c""}"
"channel101_track0_channel101_20250319T092230_0_1_confidence_68.jpg","{""employee_id"": ""gbhadra_nair"", ""confidence"": 91.22850799560547, ""face_id"": ""2e02b2e2-e9c5-49ee-860f-1f76ce1a852e""}"
"channel101_track0_channel101_20250319T092230_0_2_confidence_67.jpg","{""employee_id"": ""gbhadra_nair"", ""confidence"": 91.2748794555664, ""face_id"": ""2e02b2e2-e9c5-49ee-860f-1f76ce1a852e""}"
"channel101_track0_channel101_20250319T094200_0_1_confidence_61.jpg","{""employee_id"": ""Error"", ""confidence"": 0, ""error"": ""An error occurred (InvalidParameterException) when calling the SearchFacesByImage operation: There are no faces in the image. Should be at least 1.""}"
"channel101_track0_channel101_20250319T094200_0_2_confidence_61.jpg","{""employee_id"": ""Error"", ""confidence"": 0, ""error"": ""An error occurred (InvalidParameterException) when calling the SearchFacesByImage operation: There are no faces in the image. Should be at least 1.""}"
        """
    
    print(process_attendance_data(attendance_data))
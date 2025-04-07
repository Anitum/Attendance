import csv
from datetime import datetime
from collections import defaultdict
import io

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
    report = "ATTENDANCE REPORT\n"
    report += "="*80 + "\n\n"
    
    if not attendance_data:
        report += "No attendance records found.\n"
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
    
    report += f"\nTotal people detected: {len(attendance_data)}\n"
    report += f"Error entries: {error_count}\n"
    
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
"2025-03-19 08:52:30","main_entrance","Error","0","","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T085230_0_1_confidence_60.jpg"
"2025-03-19 08:54:00","main_entrance","nayana_m","96.43894958496094","663d4ebc-9845-4d37-be8c-12ffabccfa4e","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T085400_0_1_confidence_81.jpg"
"2025-03-19 08:54:00","main_entrance","nayana_m","94.58027648925781","663d4ebc-9845-4d37-be8c-12ffabccfa4e","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T085400_0_2_confidence_78.jpg"
"2025-03-19 08:55:30","main_entrance","ebin_jomon","99.5948486328125","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T085530_0_1_confidence_93.jpg"
"2025-03-19 08:55:30","main_entrance","ebin_jomon","98.73960876464844","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T085530_0_2_confidence_88.jpg"
"2025-03-19 09:01:30","main_entrance","ebin_jomon","85.8829345703125","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T090130_0_1_confidence_74.jpg"
"2025-03-19 09:01:30","main_entrance","ebin_jomon","86.41988372802734","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T090130_0_2_confidence_73.jpg"
"2025-03-19 09:04:30","main_entrance","ebin_jomon","79.54808807373047","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T090430_0_1_confidence_75.jpg"
"2025-03-19 09:04:30","main_entrance","ebin_jomon","77.64732360839844","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T090430_0_2_confidence_83.jpg"
"2025-03-19 09:16:30","main_entrance","ebin_jomon","99.49040985107422","7f7967ab-b948-458d-84a1-649fb55fe68c","/home/ubuntu/PushToAWSandGrey/20250319/channel101_track0_channel101_20250319T091630_0_1_confidence_61.jpg"
        """
    
    print(process_attendance_data(attendance_data))
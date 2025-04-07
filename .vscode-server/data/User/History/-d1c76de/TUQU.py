import csv
from datetime import datetime
from collections import defaultdict

def process_attendance(data):
    # Parse CSV data
    reader = csv.reader(data.strip().split('\n'))
    
    # Track persons and their attendance times
    attendance = defaultdict(list)
    error_count = 0
    
    for row in reader:
        timestamp, location, person, confidence, uid, image_path = row
        
        # Skip error entries
        if person == "Error":
            error_count += 1
            continue
        
        # Convert timestamp to datetime object
        time = datetime.strptime(timestamp.strip('"'), "%Y-%m-%d %H:%M:%S")
        
        # Add to attendance (with confidence as float)
        confidence_value = float(confidence.strip('"'))
        attendance[person.strip('"')].append((time, confidence_value, uid.strip('"')))
    
    # Generate final attendance report
    final_attendance = []
    
    for person, records in attendance.items():
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
    # Replace this with your input method (e.g., reading from file)
    attendance_data = """your CSV data here"""
    print(process_attendance_data(attendance_data))
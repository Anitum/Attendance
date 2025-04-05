import csv
import datetime
import sys
from collections import defaultdict

def filter_earliest_entries(input_file):
    # Dictionary to store earliest entry for each person
    earliest_entries = defaultdict(lambda: None)
    
    try:
        # Read the input file
        with open(input_file, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) >= 3:  # Make sure row has enough columns
                    try:
                        timestamp_str = row[0]
                        person_name = row[2]
                        
                        # Skip "No match found" entries
                        if person_name == "No match found":
                            continue
                        
                        # Parse the timestamp
                        timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        
                        # Check if this is the earliest entry for this person
                        if earliest_entries[person_name] is None or timestamp < earliest_entries[person_name][0]:
                            earliest_entries[person_name] = (timestamp, person_name)
                    except (ValueError, IndexError) as e:
                        print(f"Error processing row: {row}. Error: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.", file=sys.stderr)
        return
    
    # Output results to stdout (adjusted time and name)
    for person, (timestamp, person_name) in earliest_entries.items():
        # Subtract 10 minutes from the timestamp
        adjusted_timestamp = timestamp - datetime.timedelta(minutes=10)
        # Format the adjusted timestamp
        adjusted_timestamp_str = adjusted_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{adjusted_timestamp_str},{person_name}")

if __name__ == "__main__":
    # Check if filename is provided as command line argument
    if len(sys.argv) != 2:
        print("Usage: python script.py filename.csv", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    filter_earliest_entries(input_file)

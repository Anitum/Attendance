#!/bin/bash

# Usage help function
function show_usage {
    echo "Usage: $0 <employee_id> <datetime>"
    echo "  <employee_id>: The employee ID (can be alphanumeric)"
    echo "  <datetime>: Date and time in format YYYY-MM-DD HH:MM"
    echo ""
    echo "Example: $0 1001 \"2023-11-10 09:30\""
    exit 1
}

# Check if sufficient parameters are provided
if [ $# -lt 2 ]; then
    show_usage
fi

# Set the API credentials and endpoint
API_ID="a88a4421-5c14-4bf9-8624-375aacaf055c"
PRIVATE_KEY_FILE="/home/ubuntu/testing_greythr_attendance/attendance_2025-03-15.csv"
API_ENDPOINT="https://anitum.greythr.com/v2/attendance/asca/swipes"

# Extract command line parameters
EMPLOYEE_ID="$1"
INPUT_DATETIME="$2"

# Convert the input datetime to the required format
# Input format: YYYY-MM-DD HH:MM
# Required format: YYYY-MM-DDThh:mm:ss.SSS+05:30
FORMATTED_DATETIME=$(date -d "$INPUT_DATETIME" "+%Y-%m-%dT%H:%M:%S.000+05:30")

# Check if the date conversion was successful
if [ $? -ne 0 ]; then
    echo "Error: Invalid date format. Please use YYYY-MM-DD HH:MM"
    show_usage
fi

# Create entry (in) swipe
SWIPES="${FORMATTED_DATETIME},${EMPLOYEE_ID},Main Door,1"

echo "Creating ENTRY swipe for Employee ID: $EMPLOYEE_ID"
echo "Time: $FORMATTED_DATETIME"

# Save swipes to a file
echo -n "$SWIPES" > swipes.txt

# Generate signature
SIGNATURE=$(openssl dgst -sha1 -sign "$PRIVATE_KEY_FILE" -binary swipes.txt | base64 -w 0)

# URL encode the swipes and signature using Python
SWIPES_URLENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$SWIPES'''))")
SIGNATURE_URLENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$SIGNATURE'''))")

# Create a complete payload for curl
PAYLOAD="id=${API_ID}&swipes=${SWIPES_URLENCODED}&sign=${SIGNATURE_URLENCODED}"

# Make the request with proper encoding
echo "Sending ENTRY data to greytHR..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_ENDPOINT" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-raw "$PAYLOAD")

# Check the response code
if [ "$RESPONSE" -eq 200 ]; then
    echo "Success! ENTRY data uploaded successfully."
else
    echo "Error! Server returned status code: $RESPONSE"
    # For debugging, you can uncomment the following line
    # curl -v -X POST "$API_ENDPOINT" -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/x-www-form-urlencoded" --data-raw "$PAYLOAD"
fi

# Clean up
rm swipes.txt
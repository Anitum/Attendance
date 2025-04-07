#!/bin/bash

# Set the API credentials and endpoint
API_ID="a88a4421-5c14-4bf9-8624-375aacaf055c"
PRIVATE_KEY_FILE="./Downloads/a88a4421-5c14-4bf9-8624-375aacaf055c.pem"
API_ENDPOINT="https://anitum.greythr.com/v2/attendance/asca/swipes"

# Get swipes from input file and employee ID from arguments
SWIPES_FILE="$1"
EMPLOYEE_ID="$2"  # This is now passed from the Python script

# Read swipes from file
SWIPES=$(cat "$SWIPES_FILE")

# Generate signature
SIGNATURE=$(openssl dgst -sha1 -sign "$PRIVATE_KEY_FILE" -binary "$SWIPES_FILE" | base64 -w 0)

# URL encode the swipes and signature using Perl
SWIPES_URLENCODED=$(perl -MURI::Escape -e 'print uri_escape($ARGV[0]);' "$SWIPES")
SIGNATURE_URLENCODED=$(perl -MURI::Escape -e 'print uri_escape($ARGV[0]);' "$SIGNATURE")

# Create a complete payload for curl
PAYLOAD="id=${API_ID}&swipes=${SWIPES_URLENCODED}&sign=${SIGNATURE_URLENCODED}"

# Make the request with proper encoding
curl -v -X POST "$API_ENDPOINT" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-raw "$PAYLOAD"

# Clean up
rm "$SWIPES_FILE"
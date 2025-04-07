#!/bin/bash

# File to store the expected crontab entries
EXPECTED_ENTRIES_FILE="/tmp/expected_crontab_entries.txt"

# Create the file with expected entries
cat > "$EXPECTED_ENTRIES_FILE" << 'EOF'
05 8 * * * python3 ~/email_push_attendance.py
00 0 * * * find $HOME -name "*.mkv" -type f -delete
00 8 * * * ~/startup2point0.sh
05 8 * * * ~/AWS_Recog.sh
00 12 * * * ~/stop_processes.sh
00 15 * * * find $HOME -name "*.mkv" -type f -delete
00 17 * * * ~/startup2point0.sh
00 17 * * * ~/AWS_Recog.sh
10 21 * * * python3 ~/send_exit_notification.py
00 21 * * * ~/stop_processes.sh
EOF

# Function to check and restore crontab entries
check_and_restore_crontab() {
    echo "$(date): Checking crontab entries..."
    
    # Get current crontab
    crontab -l > /tmp/current_crontab.txt 2>/dev/null || echo "" > /tmp/current_crontab.txt
    
    # Flag to track if we need to update crontab
    NEED_UPDATE=0
    
    # Check each expected entry
    while IFS= read -r entry; do
        if ! grep -F "$entry" /tmp/current_crontab.txt >/dev/null; then
            echo "$(date): Missing entry: $entry"
            NEED_UPDATE=1
        fi
    done < "$EXPECTED_ENTRIES_FILE"
    
    # If we need to update, append missing entries and install the new crontab
    if [ $NEED_UPDATE -eq 1 ]; then
        echo "$(date): Updating crontab with missing entries..."
        
        # Create a new crontab file
        cat /tmp/current_crontab.txt > /tmp/new_crontab.txt
        
        # Add missing entries
        while IFS= read -r entry; do
            if ! grep -F "$entry" /tmp/current_crontab.txt >/dev/null; then
                echo "$entry" >> /tmp/new_crontab.txt
                echo "$(date): Added missing entry: $entry"
            fi
        done < "$EXPECTED_ENTRIES_FILE"
        
        # Install the new crontab
        crontab /tmp/new_crontab.txt
        echo "$(date): Crontab updated successfully."
    else
        echo "$(date): All entries are already present in crontab."
    fi
    
    # Clean up
    rm -f /tmp/current_crontab.txt /tmp/new_crontab.txt
}

# Run the check immediately
check_and_restore_crontab

# Set up the script to run every hour using crontab itself
# Check if this script's cron entry exists already
SCRIPT_PATH="$(readlink -f "$0")"
SCRIPT_CRON_ENTRY="0 * * * * $SCRIPT_PATH"

crontab -l > /tmp/current_crontab.txt 2>/dev/null || echo "" > /tmp/current_crontab.txt

if ! grep -F "$SCRIPT_CRON_ENTRY" /tmp/current_crontab.txt >/dev/null; then
    echo "$(date): Adding this script to crontab to run hourly..."
    echo "$SCRIPT_CRON_ENTRY" >> /tmp/current_crontab.txt
    crontab /tmp/current_crontab.txt
    echo "$(date): Script added to crontab."
fi

# Clean up
rm -f /tmp/current_crontab.txt

echo "$(date): Setup complete. The script will run hourly to ensure all required crontab entries are present."
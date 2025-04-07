#!/bin/bash

# Function to monitor memory usage and handle file movement
monitor_memory() {
    log_file="$HOME/logs/memory_monitor.log"
    mkdir -p "$(dirname "$log_file")"
    
    echo "Starting memory monitoring at $(date)" >> "$log_file"
    
    while true; do
        # Get memory usage percentage
        memory_usage=$(free | grep Mem | awk '{print $3/$2 * 100.0}')
        
        # Log current memory usage
        echo "$(date): Memory usage is $memory_usage%" >> "$log_file"
        
        # Check if memory usage is over 90%
        if (( $(echo "$memory_usage > 90" | bc -l) )); then
            echo "$(date): Memory usage is over 90%. Moving files..." >> "$log_file"
            
            # Create directory for unprocessed recordings
            cd ~
            mkdir -p unprocessed_recording
            
            # Move all channel directories' MKV files
            for channel in {1..4}01; do
                if [ -d "channel$channel" ]; then
                    find "channel$channel" -name "*.mkv" -type f -exec mv {} unprocessed_recording/ \; 2>> "$log_file"
                fi
            done
            
            # Also move any MKV files in the home directory
            find "$HOME" -maxdepth 1 -name "channel*.mkv" -type f -exec mv {} unprocessed_recording/ \; 2>> "$log_file"
            
            # Create log file with timestamp
            timestamp=$(date '+%d%m%y*T*%H%M%S')
            move_log_file="unprocessed_${timestamp}.txt"
            
            # List all files in unprocessed_recording and save to log file
            ls -1 unprocessed_recording/ > "$move_log_file"
            
            # Upload log file to S3
            echo "$(date): Uploading log file to S3..." >> "$log_file"
            if aws s3 cp "$move_log_file" "s3://Erasmith://face-recognition-results/$move_log_file"; then
                echo "$(date): Log file uploaded successfully" >> "$log_file"
            else
                echo "$(date): Failed to upload log file to S3" >> "$log_file"
            fi
            
            # Sync unprocessed_recording directory to S3
            echo "$(date): Syncing unprocessed recordings to S3..." >> "$log_file"
            if aws s3 sync unprocessed_recording/ s3://Erasmith://oil-mill-pilani/recorded/; then
                echo "$(date): Unprocessed recordings synced successfully" >> "$log_file"
                
                # Clean up only if S3 upload was successful
                rm -R unprocessed_recording/
                rm "$move_log_file"
                echo "$(date): Cleanup complete" >> "$log_file"
            else
                echo "$(date): Failed to sync recordings to S3, keeping local files" >> "$log_file"
            fi
        fi
        
        # Wait for 5 minutes before checking again
        sleep 300
    done
}

cd ~

# Create logs directory if it doesn't exist
mkdir -p logs

# Start record.sh in background
nohup ./record.sh > logs/record.log 2>&1 &
echo $! > pids.txt

# Start face_recognition.sh in background
nohup ./face_recognition_no_upload.sh > logs/detection.log 2>&1 &
echo $! >> pids.txt

# Start memory monitoring in background
nohup monitor_memory > logs/memory_monitor.log 2>&1 &
echo $! >> pids.txt

# Start watchdog
# nohup ./watchdog.sh > logs/watchdog.log 2>&1 &
# echo $! >> pids.txt

# Create a stop script to terminate all processes
cat > stop_processes.sh << 'EOF'
#!/bin/bash
# Script to stop all background processes started by startup script

# Check if pids.txt exists
if [ ! -f ~/pids.txt ]; then
    echo "pids.txt not found. Cannot stop processes."
    exit 1
fi

# Read PIDs from file and kill each process
echo "Stopping all background processes..."
while read pid; do
    if ps -p $pid > /dev/null; then
        echo "Killing process $pid"
        kill -15 $pid
        # Force kill if still running after 5 seconds
        sleep 5
        if ps -p $pid > /dev/null; then
            echo "Force killing process $pid"
            kill -9 $pid
        fi
    else
        echo "Process $pid is not running"
    fi
done < ~/pids.txt

# Additionally, try to find and kill any remaining record, detection, or monitor processes
echo "Checking for any remaining processes..."
pkill -f "record.sh"
pkill -f "face_recognition.sh"
pkill -f "monitor_memory"
pkill -f "watchdog.sh"

# Create stop file for record.sh
touch /tmp/stop_recording
sleep 2
rm -f /tmp/stop_recording

# Remove PID file
rm ~/pids.txt
echo "All processes stopped."
EOF

# Make the stop script executable
chmod +x stop_processes.sh

echo "All processes started in background. You can safely close the terminal."
echo "To stop all processes, run: ./stop_processes.sh"
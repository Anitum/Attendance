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
            channel=401
            if [ -d "channel$channel" ]; then
                find "channel$channel" -name "*.mkv" -type f -exec mv {} unprocessed_recording/ \; 2>> "$log_file"
            fi            
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
nohup ./face_detection_tracking_noupload.sh > logs/face_rec.log 2>&1 &
echo $! >> pids.txt

# Start memory monitoring in background
nohup monitor_memory > logs/memory_monitor.log 2>&1 &
echo $! >> pids.txt

# Start AWSandEmailPush.sh in background
nohup ./AWS_Recog.sh > logs/aws_email_push.log 2>&1 &
echo $! >> pids.txt

# Start watchdog
# nohup ./watchdog.sh > logs/watchdog.log 2>&1 &
# echo $! >> pids.txt

# Create a stop script to terminate all processes
cat > stop_processes.sh << 'EOF'
#!/bin/bash
# Script to stop all background processes started by startup script

# Log file for stop process operations
log_file="$HOME/logs/stop_processes.log"
mkdir -p "$(dirname "$log_file")"
echo "===== Stop processes initiated at $(date) =====" >> "$log_file"

# Function to kill a process with its children
kill_process_tree() {
    local pid=$1
    local name=$2
    echo "Attempting to kill $name (PID: $pid)" | tee -a "$log_file"
    
    # Get all child processes
    children=$(pgrep -P $pid)
    
    # Kill the process
    if ps -p $pid > /dev/null; then
        echo "Sending SIGTERM to $pid" | tee -a "$log_file"
        kill -15 $pid 2>> "$log_file"
        
        # Wait for process to terminate
        for i in {1..5}; do
            if ! ps -p $pid > /dev/null; then
                echo "Process $pid terminated" | tee -a "$log_file"
                break
            fi
            echo "Waiting for process $pid to terminate ($i/5)..." | tee -a "$log_file"
            sleep 1
        done
        
        # Force kill if still running
        if ps -p $pid > /dev/null; then
            echo "Force killing process $pid" | tee -a "$log_file"
            kill -9 $pid 2>> "$log_file"
        fi
    else
        echo "Process $pid is not running" | tee -a "$log_file"
    fi
    
    # Kill children
    for child in $children; do
        kill_process_tree $child "child of $name"
    done
}

# Check if pids.txt exists
if [ -f ~/pids.txt ]; then
    echo "Reading PIDs from pids.txt..." | tee -a "$log_file"
    while read pid; do
        if [[ "$pid" =~ ^[0-9]+$ ]]; then
            kill_process_tree $pid "process from pids.txt"
        else
            echo "Invalid PID: $pid" | tee -a "$log_file"
        fi
    done < ~/pids.txt
else
    echo "pids.txt not found. Will try finding processes by name." | tee -a "$log_file"
fi

# Create stop file for record.sh
echo "Creating stop_recording file..." | tee -a "$log_file"
touch /tmp/stop_recording

# Find and kill any remaining processes by name (more aggressive approach)
echo "Searching for remaining processes by name..." | tee -a "$log_file"

# Find processes by exact script name
for script in "record.sh" "face_recognition_no_upload.sh" "monitor_memory" "watchdog.sh" "AWSandEmailPush.sh"; do
    echo "Looking for processes running $script" | tee -a "$log_file"
    pids=$(pgrep -f "$script" || echo "")
    for pid in $pids; do
        kill_process_tree $pid "$script"
    done
done

# Find bash processes that might be running our scripts
bash_pids=$(ps aux | grep bash | grep -E 'record|face_recognition|monitor|watchdog|AWSandEmailPush' | grep -v grep | awk '{print $2}')
for pid in $bash_pids; do
    kill_process_tree $pid "bash script"
done

# Remove the stop file after a short wait
sleep 2
rm -f /tmp/stop_recording

# Remove PID file
if [ -f ~/pids.txt ]; then
    echo "Removing pids.txt file" | tee -a "$log_file"
    rm ~/pids.txt
fi

echo "All processes should now be stopped." | tee -a "$log_file"
echo "Check for any remaining processes with: ps aux | grep -E 'record|face|monitor|watchdog|AWSandEmailPush'" | tee -a "$log_file"

# Final verification
remaining=$(ps aux | grep -E 'record.sh|face_recognition|monitor_memory|watchdog|AWSandEmailPush' | grep -v grep || echo "")
if [ -n "$remaining" ]; then
    echo "WARNING: Some processes may still be running:" | tee -a "$log_file"
    echo "$remaining" | tee -a "$log_file"
    echo "You may need to manually kill these processes." | tee -a "$log_file"
else
    echo "No related processes found running. Stop completed successfully." | tee -a "$log_file"
fi

echo "===== Stop processes completed at $(date) =====" >> "$log_file"
EOF

# Make the stop script executable
chmod +x stop_processes.sh

echo "All processes started in background. You can safely close the terminal."
echo "To stop all processes, run: ./stop_processes.sh"

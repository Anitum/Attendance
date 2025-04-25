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
for script in "record.sh" "face_detection_tracking_noupload.sh" "monitor_memory" "watchdog.sh" "AWS_Recog.sh" "email_push_attendance.py" "greythr_push_attendance.py"; do
    echo "Looking for processes running $script" | tee -a "$log_file"
    pids=$(pgrep -f "$script" || echo "")
    for pid in $pids; do
        kill_process_tree $pid "$script"
    done
done

# Find bash processes that might be running our scripts
bash_pids=$(ps aux | grep bash | grep -E 'record|face_detection|monitor|watchdog|AWS_Recog' | grep -v grep | awk '{print $2}')
for pid in $bash_pids; do
    kill_process_tree $pid "bash script"
done

# Find python processes that might be running email_push_attendance.py
python_pids=$(ps aux | grep python | grep -E 'email_push_attendance.py|greythr_push_attendance.py' | grep -v grep | awk '{print $2}')
for pid in $python_pids; do
    kill_process_tree $pid "email_push_attendance.py python script"
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
echo "Check for any remaining processes with: ps aux | grep -E 'record|face|monitor|watchdog|AWS_Recog|email_push_attendance'" | tee -a "$log_file"

# Final verification
remaining=$(ps aux | grep -E 'record.sh|face_detection_tracking_noupload|monitor_memory|watchdog|AWS_Recog|email_push_attendance.py|greythr_push_attendance.py' | grep -v grep || echo "")
if [ -n "$remaining" ]; then
    echo "WARNING: Some processes may still be running:" | tee -a "$log_file"
    echo "$remaining" | tee -a "$log_file"
    echo "You may need to manually kill these processes." | tee -a "$log_file"
else
    echo "No related processes found running. Stop completed successfully." | tee -a "$log_file"
fi

echo "===== Stop processes completed at $(date) =====" >> "$log_file"

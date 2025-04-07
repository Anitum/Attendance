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
# rm ~/pids.txt
echo "All processes stopped."

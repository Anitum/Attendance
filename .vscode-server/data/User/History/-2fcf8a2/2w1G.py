import cv2
from ultralytics import YOLO
import multiprocessing
import time
import numpy as np
import os
import psutil
import platform

def process_video():
    start_time = time.time()
    
    # Create log file for CPU metrics
    cpu_log_file = open('cpu_metrics.log', 'w')
    cpu_log_file.write("Time(s),CPU_Utilization(%),Memory_Used(MB),Memory_Total(MB),Memory_Utilization(%),CPU_Temperature(C),CPU_Frequency(MHz)\n")
    
    # Create output directory for frames
    os.makedirs('output_frames', exist_ok=True)
    
    # Load the model
    yolo = YOLO('yolo11s.pt')
    videoCap = cv2.VideoCapture(r'/home/ubuntu/stock-footage-people-working-at-business-office-and-sitting-by-tables-with-computers-businesswoman-chats-by.webm')
    
    frame_count = 0
    max_frames = 300
    total_processing_time = 0
    all_confidences = []
    inference_times = []

    def getColours(cls_num):
        base_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        color_index = cls_num % len(base_colors)
        increments = [(1, -2, 1), (-2, 1, -1), (1, -1, 2)]
        color = [base_colors[color_index][i] + increments[color_index][i] * 
        (cls_num // len(base_colors)) % 256 for i in range(3)]
        return tuple(color)

    # Configure headless mode for OpenCV
    os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
    os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

    while frame_count < max_frames:
        frame_start = time.time()
        
        # Get CPU metrics before inference
        try:
            # CPU utilization (average across all cores)
            cpu_util = psutil.cpu_percent(interval=0.1)
            
            # Memory information
            memory = psutil.virtual_memory()
            memory_used = memory.used / (1024 * 1024)  # Convert to MB
            memory_total = memory.total / (1024 * 1024)  # Convert to MB
            memory_util = memory.percent
            
            # CPU frequency (average across all cores)
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                cpu_frequency = cpu_freq.current
            else:
                cpu_frequency = -1
            
            # CPU temperature (if available)
            temperature = -1
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try to get CPU temperature from different possible sources
                    for name, entries in temps.items():
                        if entries:
                            temperature = entries[0].current
                            break
            
            elapsed_time = time.time() - start_time
            cpu_log_file.write(f"{elapsed_time:.2f},{cpu_util},{memory_used:.2f},{memory_total:.2f},{memory_util:.2f},{temperature},{cpu_frequency:.2f}\n")
            cpu_log_file.flush()  # Ensure metrics are written to file in real-time
        except Exception as e:
            print(f"Error getting CPU metrics: {e}")
        
        ret, frame = videoCap.read()
        if not ret:
            break

        # Measure inference time
        inference_start = time.time()
        results = yolo.track(frame, stream=True)
        inference_end = time.time()
        inference_times.append(inference_end - inference_start)

        for result in results:
            classes_names = result.names
            for box in result.boxes:
                if box.conf[0] > 0.4:
                    [x1, y1, x2, y2] = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    cls = int(box.cls[0])
                    colour = getColours(cls)
                    all_confidences.append(float(box.conf[0]))

                    cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
                    cv2.putText(frame, f'{classes_names[cls]} {box.conf[0]:.2f}', 
                                (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 1, colour, 2)
        
        if frame_count % 10 == 0:
            cv2.imwrite(f'output_frames/frame_{frame_count:04d}.jpg', frame)
        
        time.sleep(0.001)
        
        frame_end = time.time()
        frame_processing_time = frame_end - frame_start
        total_processing_time += frame_processing_time
        frame_count += 1
        
        if frame_count % 10 == 0:
            print(f"Processed {frame_count} frames")

    total_time = time.time() - start_time
    
    # Calculate statistics
    avg_confidence = float(np.mean(all_confidences)) if len(all_confidences) > 0 else 0
    min_confidence = float(np.min(all_confidences)) if len(all_confidences) > 0 else 0
    max_confidence = float(np.max(all_confidences)) if len(all_confidences) > 0 else 0
    
    avg_inference = float(np.mean(inference_times)) * 1000 if len(inference_times) > 0 else 0
    min_inference = float(np.min(inference_times)) * 1000 if len(inference_times) > 0 else 0
    max_inference = float(np.max(inference_times)) * 1000 if len(inference_times) > 0 else 0
    
    with open('latency.log', 'w') as log_file:
        log_file.write(f"Total Processing Time: {total_time:.4f} seconds\n")
        log_file.write(f"Average Frame Processing Time: {total_processing_time*1000/frame_count if frame_count > 0 else 0:.4f} ms\n")
        log_file.write(f"Frames Processed: {frame_count}\n")
        log_file.write(f"\nInference Statistics:\n")
        log_file.write(f"Average Inference Time: {avg_inference:.4f} ms\n")
        log_file.write(f"Minimum Inference Time: {min_inference:.4f} ms\n")
        log_file.write(f"Maximum Inference Time: {max_inference:.4f} ms\n")
        log_file.write(f"\nConfidence Statistics:\n")
        log_file.write(f"Average Confidence: {avg_confidence:.4f}\n")
        log_file.write(f"Minimum Confidence: {min_confidence:.4f}\n")
        log_file.write(f"Maximum Confidence: {max_confidence:.4f}\n")
        log_file.write(f"Total Detections: {len(all_confidences)}\n")

    # Generate CPU metrics summary
    try:
        cpu_log_file.close()
        
        # Read the metrics for summary
        import pandas as pd
        try:
            df = pd.read_csv('cpu_metrics.log')
            
            with open('cpu_summary.log', 'w') as summary_file:
                summary_file.write("CPU PERFORMANCE SUMMARY\n")
                summary_file.write("======================\n\n")
                
                summary_file.write(f"CPU Utilization:\n")
                summary_file.write(f"  Average: {df['CPU_Utilization(%)'].mean():.2f}%\n")
                summary_file.write(f"  Maximum: {df['CPU_Utilization(%)'].max():.2f}%\n")
                summary_file.write(f"  Minimum: {df['CPU_Utilization(%)'].min():.2f}%\n\n")
                
                summary_file.write(f"Memory Utilization:\n")
                summary_file.write(f"  Average: {df['Memory_Utilization(%)'].mean():.2f}%\n")
                summary_file.write(f"  Maximum: {df['Memory_Utilization(%)'].max():.2f}%\n")
                summary_file.write(f"  Minimum: {df['Memory_Utilization(%)'].min():.2f}%\n\n")
                
                summary_file.write(f"Memory Used:\n")
                summary_file.write(f"  Average: {df['Memory_Used(MB)'].mean():.2f} MB\n")
                summary_file.write(f"  Maximum: {df['Memory_Used(MB)'].max():.2f} MB\n")
                summary_file.write(f"  Minimum: {df['Memory_Used(MB)'].min():.2f} MB\n\n")
                
                if not all(df['CPU_Temperature(C)'] == -1):
                    temp_data = df[df['CPU_Temperature(C)'] != -1]['CPU_Temperature(C)']
                    if not temp_data.empty:
                        summary_file.write(f"CPU Temperature:\n")
                        summary_file.write(f"  Average: {temp_data.mean():.2f}°C\n")
                        summary_file.write(f"  Maximum: {temp_data.max():.2f}°C\n")
                        summary_file.write(f"  Minimum: {temp_data.min():.2f}°C\n\n")
                
                if not all(df['CPU_Frequency(MHz)'] == -1):
                    freq_data = df[df['CPU_Frequency(MHz)'] != -1]['CPU_Frequency(MHz)']
                    if not freq_data.empty:
                        summary_file.write(f"CPU Frequency:\n")
                        summary_file.write(f"  Average: {freq_data.mean():.2f} MHz\n")
                        summary_file.write(f"  Maximum: {freq_data.max():.2f} MHz\n")
                        summary_file.write(f"  Minimum: {freq_data.min():.2f} MHz\n\n")
                    
        except Exception as e:
            print(f"Error generating CPU metrics summary: {e}")
            
    except Exception as e:
        print(f"Error finalizing CPU monitoring: {e}")

    videoCap.release()

def main():
    process_video()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
import cv2
from ultralytics import YOLO
from memory_profiler import memory_usage
import multiprocessing
import time
import numpy as np
import os

# Add the GPU monitoring library
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    print("Warning: pynvml not found. Installing it for GPU monitoring...")
    os.system('pip install nvidia-ml-py3')
    try:
        import pynvml
        PYNVML_AVAILABLE = True
    except ImportError:
        PYNVML_AVAILABLE = False
        print("Error: Could not install pynvml. GPU metrics will not be available.")

def process_video():
    start_time = time.time()
    
    # Initialize GPU monitoring
    if PYNVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            device = pynvml.nvmlDeviceGetHandleByIndex(0)  # Using the first GPU
            print(f"Monitoring GPU: {pynvml.nvmlDeviceGetName(device).decode('utf-8')}")
        except Exception as e:
            print(f"Error initializing GPU monitoring: {e}")
            device = None
    else:
        device = None
    
    # Create log file for GPU metrics
    gpu_log_file = open('gpu_metrics.log', 'w')
    gpu_log_file.write("Time(s),GPU_Utilization(%),Memory_Used(MB),Memory_Total(MB),Memory_Utilization(%),Temperature(C),Power_Draw(W)\n")
    
    # Load the model
    yolo = YOLO('yolo11n.pt')
    videoCap = cv2.VideoCapture(0)
    
    frame_count = 0
    max_frames = 1000
    total_processing_time = 0
    all_confidences = []  # List to store all confidence values
    inference_times = []  # List to store inference times

    def getColours(cls_num):
        base_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        color_index = cls_num % len(base_colors)
        increments = [(1, -2, 1), (-2, 1, -1), (1, -1, 2)]
        color = [base_colors[color_index][i] + increments[color_index][i] * 
        (cls_num // len(base_colors)) % 256 for i in range(3)]
        return tuple(color)

    while frame_count < max_frames:
        frame_start = time.time()
        
        # Get GPU metrics before inference
        if PYNVML_AVAILABLE and device:
            try:
                # GPU utilization
                utilization = pynvml.nvmlDeviceGetUtilizationRates(device)
                gpu_util = utilization.gpu
                
                # Memory information
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(device)
                memory_used = memory_info.used / (1024 * 1024)  # MiB
                memory_total = memory_info.total / (1024 * 1024)  # MiB
                memory_util = (memory_info.used / memory_info.total) * 100  # Percentage
                
                # Temperature
                temperature = pynvml.nvmlDeviceGetTemperature(device, pynvml.NVML_TEMPERATURE_GPU)
                
                # Power draw
                try:
                    power_draw = pynvml.nvmlDeviceGetPowerUsage(device) / 1000.0  # Convert from mW to W
                except pynvml.NVMLError:
                    power_draw = -1  # Not supported on some GPUs
                
                elapsed_time = time.time() - start_time
                gpu_log_file.write(f"{elapsed_time:.2f},{gpu_util},{memory_used:.2f},{memory_total:.2f},{memory_util:.2f},{temperature},{power_draw:.2f}\n")
                gpu_log_file.flush()  # Ensure metrics are written to file in real-time
            except Exception as e:
                print(f"Error getting GPU metrics: {e}")
        
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
                    all_confidences.append(float(box.conf[0]))  # Store confidence value

                    cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
                    cv2.putText(frame, f'{classes_names[cls]} {box.conf[0]:.2f}', 
                                (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 1, colour, 2)
        
        cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        frame_end = time.time()
        frame_processing_time = frame_end - frame_start
        total_processing_time += frame_processing_time
        frame_count += 1

    total_time = time.time() - start_time
    
    # Calculate statistics with checks for empty arrays
    avg_confidence = float(np.mean(all_confidences)) if len(all_confidences) > 0 else 0
    min_confidence = float(np.min(all_confidences)) if len(all_confidences) > 0 else 0
    max_confidence = float(np.max(all_confidences)) if len(all_confidences) > 0 else 0
    
    # Calculate inference statistics with checks for empty arrays
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

    # Generate GPU metrics summary if available
    if PYNVML_AVAILABLE:
        try:
            # Close the GPU metrics log file
            gpu_log_file.close()
            
            # Read the metrics for summary
            import pandas as pd
            try:
                df = pd.read_csv('gpu_metrics.log')
                
                with open('gpu_summary.log', 'w') as summary_file:
                    summary_file.write("GPU PERFORMANCE SUMMARY\n")
                    summary_file.write("======================\n\n")
                    
                    summary_file.write(f"GPU Utilization:\n")
                    summary_file.write(f"  Average: {df['GPU_Utilization(%)'].mean():.2f}%\n")
                    summary_file.write(f"  Maximum: {df['GPU_Utilization(%)'].max():.2f}%\n")
                    summary_file.write(f"  Minimum: {df['GPU_Utilization(%)'].min():.2f}%\n\n")
                    
                    summary_file.write(f"Memory Utilization:\n")
                    summary_file.write(f"  Average: {df['Memory_Utilization(%)'].mean():.2f}%\n")
                    summary_file.write(f"  Maximum: {df['Memory_Utilization(%)'].max():.2f}%\n")
                    summary_file.write(f"  Minimum: {df['Memory_Utilization(%)'].min():.2f}%\n\n")
                    
                    summary_file.write(f"Memory Used:\n")
                    summary_file.write(f"  Average: {df['Memory_Used(MB)'].mean():.2f} MB\n")
                    summary_file.write(f"  Maximum: {df['Memory_Used(MB)'].max():.2f} MB\n")
                    summary_file.write(f"  Minimum: {df['Memory_Used(MB)'].min():.2f} MB\n\n")
                    
                    summary_file.write(f"GPU Temperature:\n")
                    summary_file.write(f"  Average: {df['Temperature(C)'].mean():.2f}°C\n")
                    summary_file.write(f"  Maximum: {df['Temperature(C)'].max():.2f}°C\n")
                    summary_file.write(f"  Minimum: {df['Temperature(C)'].min():.2f}°C\n\n")
                    
                    if not all(df['Power_Draw(W)'] == -1):
                        power_data = df[df['Power_Draw(W)'] != -1]['Power_Draw(W)']
                        if not power_data.empty:
                            summary_file.write(f"Power Draw:\n")
                            summary_file.write(f"  Average: {power_data.mean():.2f}W\n")
                            summary_file.write(f"  Maximum: {power_data.max():.2f}W\n")
                            summary_file.write(f"  Minimum: {power_data.min():.2f}W\n\n")
                        
            except Exception as e:
                print(f"Error generating GPU metrics summary: {e}")
            
            # Cleanup
            pynvml.nvmlShutdown()
        except Exception as e:
            print(f"Error finalizing GPU monitoring: {e}")

    videoCap.release()
    cv2.destroyAllWindows()

def main():
    # Measure memory usage
    mem_usage = memory_usage(proc=process_video, max_iterations=1)

    # Write memory usage to log file
    with open('memory.log', 'w') as log_file:
        for mem in mem_usage:
            log_file.write(f"{mem} MB\n")

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
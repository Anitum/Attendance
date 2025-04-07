#!/usr/bin/env python3
import os
import shutil
import sys
import re

def copy_high_confidence_faces(source_dir, output_dir):
    """
    Copies face detection files with confidence greater than 90% to output directory.
    
    Args:
        source_dir: Directory containing face detection images
        output_dir: Directory to copy high confidence images to
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Regular expression to extract confidence value
    confidence_pattern = re.compile(r'confidence_(\d{2})\.jpg$')
    
    # Counter for statistics
    total_files = 0
    high_confidence_files = 0
    
    # Process all jpg files in the source directory
    for filename in os.listdir(source_dir):
        if filename.lower().endswith('.jpg'):
            total_files += 1
            file_path = os.path.join(source_dir, filename)
            
            # Extract confidence value using regex
            match = confidence_pattern.search(filename)
            if match:
                confidence = int(match.group(1))
                
                # Copy files with confidence > 90
                if confidence > 90:
                    destination_path = os.path.join(output_dir, filename)
                    shutil.copy2(file_path, destination_path)
                    high_confidence_files += 1
                    print(f"Copied: {filename} (Confidence: {confidence}%)")
    
    print(f"\nSummary:")
    print(f"Total files processed: {total_files}")
    print(f"Files with confidence > 90%: {high_confidence_files}")

if __name__ == "__main__":
    # Check if output directory is provided as command line argument
    if len(sys.argv) != 2:
        print("Usage: python script.py OUTPUT_DIRECTORY")
        sys.exit(1)
    
    source_directory = "/home/ubuntu/faceDetections"
    output_directory = sys.argv[1]
    
    print(f"Source directory: {source_directory}")
    print(f"Output directory: {output_directory}")
    
    copy_high_confidence_faces(source_directory, output_directory)
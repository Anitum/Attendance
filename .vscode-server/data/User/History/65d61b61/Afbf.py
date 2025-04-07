#!/usr/bin/env python3
"""
Face Track Selector

This script processes directories of face tracks and selects the top N images
from each track based on confidence scores. Selected images are copied to a
face recognition directory with a standardized naming format.
"""

import os
import sys
import shutil
import re
import argparse
from datetime import datetime
import cv2
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Select top face images from track directories")
    parser.add_argument("-i", "--input", required=True, help="Input directory containing face tracks")
    parser.add_argument("-o", "--output", default="face_recog", help="Output directory for selected faces")
    parser.add_argument("-n", "--num_images", type=int, default=2, help="Number of top images to select per track")
    parser.add_argument("-p", "--prefix", default=datetime.now().strftime("%Y%m%d_%H%M%S"),
                        help="Prefix for output filenames (default: current timestamp)")
    return parser.parse_args()

def parse_filename(filename):
    """Parse confidence scores from filename"""
    try:
        # Extract frame number and confidence scores
        frame_match = re.search(r'^(\d+)_con_score_([0-9.]+)_land_([0-9.]+)\.jpg$', filename)
        if frame_match:
            frame_num = int(frame_match.group(1))
            face_conf = float(frame_match.group(2))
            landmark_conf = float(frame_match.group(3))
            return frame_num, face_conf, landmark_conf
        return None, 0, 0
    except Exception as e:
        logger.error(f"Error parsing filename {filename}: {str(e)}")
        return None, 0, 0

def calculate_image_quality(image_path):
    """Calculate additional image quality metrics"""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return 0

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Calculate image sharpness (variance of Laplacian)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Calculate brightness (average pixel value)
        brightness = gray.mean()

        # Normalize scores
        sharpness_score = min(1.0, sharpness / 500)  # Normalize sharpness
        brightness_score = 1.0 - abs(brightness - 128) / 128  # Score closer to mid-brightness higher

        # Combined quality score (weighted)
        quality_score = 0.7 * sharpness_score + 0.3 * brightness_score

        return quality_score
    except Exception as e:
        logger.error(f"Error calculating image quality for {image_path}: {str(e)}")
        return 0

def find_image_files(directory):
    """Find all image files in a directory and its subdirectories"""
    image_files = []
    
    # Convert to Path object if it isn't already
    dir_path = Path(directory)
    
    # Walk through all files recursively
    for item in dir_path.glob('**/*'):
        if item.is_file() and item.suffix.lower() in ('.jpg', '.jpeg', '.png'):
            image_files.append(item)
    
    return image_files

def get_top_images(track_dir, n=2):
    """Get top N images from a track directory based on confidence and quality"""
    images = []
    
    # Find all image files recursively
    image_files = find_image_files(track_dir)
    logger.info(f"Found {len(image_files)} images in {track_dir}")
    
    # Process all found images
    for filepath in image_files:
        filename = filepath.name
        frame_num, face_conf, landmark_conf = parse_filename(filename)
        
        # Calculate additional image quality metrics
        quality_score = calculate_image_quality(filepath)
        
        # Combined score: weighted sum of face confidence, landmark confidence, and quality
        combined_score = 0.4 * face_conf + 0.3 * landmark_conf + 0.3 * quality_score
        
        images.append({
            'filepath': filepath,
            'filename': filename,
            'frame_num': frame_num,
            'face_conf': face_conf,
            'landmark_conf': landmark_conf,
            'quality_score': quality_score,
            'combined_score': combined_score
        })
    
    # Sort by combined score
    images.sort(key=lambda x: x['combined_score'], reverse=True)
    
    # Return top N images
    return images[:n]

def process_track_directory(track_dir, output_dir, prefix, num_images):
    """Process a single track directory"""
    # Extract track information from the path
    track_path = Path(track_dir)
    track_id = track_path.name
    
    # Get video name from parent directory
    video_name = track_path.parent.name if track_path.parent.name != "tracks" else track_path.parent.parent.name
    
    logger.info(f"Processing track: {video_name}/{track_id}")
    
    # Get top images for this track
    top_images = get_top_images(track_dir, num_images)
    
    images_selected = 0
    
    # Copy top images to output directory
    for i, img_data in enumerate(top_images):
        if img_data['face_conf'] > 0:  # Only copy if face confidence is positive
            # Create output filename: prefix_videoname_trackID_confidence_XX.jpg
            confidence_pct = int(img_data['face_conf'] * 100)
            output_filename = f"{prefix}_{video_name}_{track_id}_{i+1}_confidence_{confidence_pct}.jpg"
            output_path = output_dir / output_filename
            
            # Copy the file
            shutil.copy2(img_data['filepath'], output_path)
            logger.info(f"Selected: {img_data['filename']} → {output_filename} (Score: {img_data['combined_score']:.2f})")
            images_selected += 1
    
    return images_selected

def process_input_directory(args):
    """Process input directory, handling different directory structures"""
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True, parents=True)
    
    total_images_selected = 0
    
    # Case 1: Input is a track directory containing images directly
    if any(f.suffix.lower() in ('.jpg', '.jpeg', '.png') for f in input_dir.glob('*')):
        total_images_selected += process_track_directory(
            input_dir, output_dir, args.prefix, args.num_images)
    
    # Case 2: Input contains subdirectories that might be track directories
    else:
        # Look for track directories (directories that contain images or have numeric names)
        for item in input_dir.glob('*'):
            if not item.is_dir():
                continue
                
            # Check if this is a track directory (contains images)
            has_images = any(f.suffix.lower() in ('.jpg', '.jpeg', '.png') for f in item.glob('*'))
            
            # If directory contains images or has a numeric name, treat as track directory
            if has_images or item.name.isdigit():
                total_images_selected += process_track_directory(
                    item, output_dir, args.prefix, args.num_images)
            
            # Otherwise, recursively process this directory
            else:
                for subitem in item.glob('*'):
                    if subitem.is_dir():
                        if subitem.name.isdigit() or any(f.suffix.lower() in ('.jpg', '.jpeg', '.png') for f in subitem.glob('*')):
                            total_images_selected += process_track_directory(
                                subitem, output_dir, args.prefix, args.num_images)
    
    return total_images_selected

if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting face track selection from: {args.input}")
    logger.info(f"Selecting top {args.num_images} images per track")
    
    total_selected = process_input_directory(args)
    
    logger.info(f"Finished processing. Selected {total_selected} images.")
    logger.info(f"Selected images saved to: {args.output}")
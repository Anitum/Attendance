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
        img = cv2.imread(image_path)
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

def get_top_images(track_dir, n=2):
    """Get top N images from a track directory based on confidence and quality"""
    images = []

    # Process all images in the track directory
    for filename in os.listdir(track_dir):
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        filepath = os.path.join(track_dir, filename)
        frame_num, face_conf, landmark_conf = parse_filename(filename)
        
        if frame_num is None:
            logger.debug(f"Skipping file with unparseable name: {filename}")
            continue

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

def process_tracks(args):
    """Process all track directories and select top images"""
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True, parents=True)
    
    total_images_processed = 0
    total_images_selected = 0
    
    # Process each channel directory (first level)
    for channel_dir in [d for d in input_dir.glob('*') if d.is_dir()]:
        channel_name = channel_dir.name
        logger.info(f"Processing channel: {channel_name}")
        
        # Process each duplicated channel directory (second level)
        for dup_channel_dir in [d for d in channel_dir.glob('*') if d.is_dir()]:
            # Process each track ID directory (0, 1, 2, etc)
            for track_id_dir in [d for d in dup_channel_dir.glob('*') if d.is_dir()]:
                track_id = track_id_dir.name
                logger.info(f"  Processing track ID: {channel_name}/{track_id}")
                
                # Get top images for this track
                top_images = get_top_images(track_id_dir, args.num_images)
                
                # Copy top images to output directory
                for i, img_data in enumerate(top_images):
                    if img_data['face_conf'] > 0:  # Only copy if face confidence is positive
                        # Create output filename: prefix_channelName_trackID_confidence_XX.jpg
                        confidence_pct = int(img_data['face_conf'] * 100)
                        output_filename = f"{args.prefix}_{channel_name}_{track_id}_{i+1}_confidence_{confidence_pct}.jpg"
                        output_path = output_dir / output_filename
                        
                        # Copy the file
                        shutil.copy2(img_data['filepath'], output_path)
                        logger.info(f"    Selected: {img_data['filename']} → {output_filename} (Score: {img_data['combined_score']:.2f})")
                        total_images_selected += 1
                    
                    total_images_processed += len(top_images)
    
    logger.info(f"Finished processing. Selected {total_images_selected} images from {total_images_processed} total images.")

if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting face track selection from: {args.input}")
    logger.info(f"Selecting top {args.num_images} images per track")
    process_tracks(args)
    logger.info(f"Selected images saved to: {args.output}")
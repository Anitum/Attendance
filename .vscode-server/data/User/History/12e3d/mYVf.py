#!/usr/bin/env python3
"""
 Copyright (c) 2018-2024 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import logging as log
import sys
import os
from argparse import ArgumentParser
from pathlib import Path
from time import perf_counter
from collections import deque
import pandas as pd
import cv2
import numpy as np
from openvino import Core, get_version

sys.path.append(str(Path(__file__).resolve().parents[2] / 'common/python'))
sys.path.append(str(Path(__file__).resolve().parents[2] / 'common/python/model_zoo'))

from utils import crop
from landmarks_detector import LandmarksDetector
from face_detector import FaceDetector

import monitors
from helpers import resolution
from images_capture import open_images_capture

from model_api.models import OutputTransform
from model_api.performance_metrics import PerformanceMetrics

log.basicConfig(format='[ %(levelname)s ] %(message)s', level=log.DEBUG, stream=sys.stdout)

DEVICE_KINDS = ['CPU', 'GPU', 'HETERO']

class TrackableObject:
    def __init__(self, object_id, centroid):
        # Store the object ID
        self.object_id = object_id
        # Initialize a list of centroids using the current centroid
        self.centroids = deque(maxlen=32)
        self.centroids.append(centroid)
        # Store the timestamp of detection
        self.last_seen = 0
        # Initialize the area of the bounding box
        self.area = 0
        # Initialize direction indicators
        self.direction_x = ""  # left or right
        self.direction_y = ""  # up or down
        # Store the ROI dimensions for prediction
        self.size = (0, 0)
        # Store average velocity
        self.velocity_x = 0
        self.velocity_y = 0
        # Keep track of consecutive frames where prediction was used
        self.prediction_count = 0
        # Store face features for re-identification
        self.face_features = None

class EnhancedFaceTracker:
    def __init__(self, max_disappeared=60, max_distance=75, prediction_threshold=20):
        # Initialize the next unique object ID
        self.next_object_id = 0
        # Dictionary to store trackable objects
        self.objects = {}
        # Number of consecutive frames object disappeared
        self.disappeared = {}
        # Maximum consecutive frames an object can be marked as
        # "disappeared" until we deregister the object
        self.max_disappeared = max_disappeared
        # Maximum distance between centroids to associate an object
        self.max_distance = max_distance
        # Maximum consecutive frames where prediction is used
        self.prediction_threshold = prediction_threshold
        # Frame counter
        self.frame_counter = 0

    def register(self, centroid, roi):
        # Create a new trackable object
        trackable = TrackableObject(self.next_object_id, centroid)
        trackable.area = roi.size[0] * roi.size[1]
        trackable.size = roi.size
        trackable.last_seen = self.frame_counter

        # Add to our dictionaries
        self.objects[self.next_object_id] = trackable
        self.disappeared[self.next_object_id] = 0

        # Increment the next unique object ID
        self.next_object_id += 1
        return self.next_object_id - 1

    def deregister(self, object_id):
        # Remove tracking object from our dictionaries
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, rois):
        self.frame_counter += 1

        # Extract centroids from ROIs
        centroids = []
        for roi in rois:
            x_center = roi.position[0] + roi.size[0] / 2
            y_center = roi.position[1] + roi.size[1] / 2
            centroids.append((x_center, y_center))

        # If we have no objects being tracked, register each new detection
        if len(self.objects) == 0:
            object_ids = []
            for i, centroid in enumerate(centroids):
                object_ids.append(self.register(centroid, rois[i]))
            return object_ids

        # If we have no detections, handle disappeared objects
        if len(centroids) == 0:
            # Try to predict locations of disappeared objects
            # and add them as "predictions" to maintain tracking
            predicted_object_ids = []
            predicted_centroids = []
            predicted_rois = []

            for object_id, obj in list(self.objects.items()):
                self.disappeared[object_id] += 1

                # If we've reached max disappeared threshold, deregister
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
                else:
                    # Predict new position based on velocity
                    if len(obj.centroids) >= 2:
                        # Calculate velocity from last two observed positions
                        prev_x, prev_y = obj.centroids[-2]
                        curr_x, curr_y = obj.centroids[-1]

                        # Only predict position if we're not exceeding prediction threshold
                        if obj.prediction_count < self.prediction_threshold:
                            # Predict new position
                            delta_x = curr_x - prev_x
                            delta_y = curr_y - prev_y
                            predicted_x = curr_x + delta_x
                            predicted_y = curr_y + delta_y

                            # Create a "virtual" detection
                            predicted_centroids.append((predicted_x, predicted_y))
                            predicted_object_ids.append(object_id)

                            # Create a corresponding ROI by copying the structure of the existing rois
                            if rois and hasattr(rois[0], "__class__"):
                                # Use the same class type as the existing ROIs
                                roi_class = rois[0].__class__
                                # Create new ROI with the predicted position
                                predicted_roi = roi_class(
                                    predicted_x - obj.size[0]/2,  # x
                                    predicted_y - obj.size[1]/2,  # y
                                    obj.size[0],                  # width
                                    obj.size[1]                   # height
                                )
                            else:
                                # Fallback - create a simple structure
                                class SimpleROI:
                                    def __init__(self, x, y, w, h):
                                        self.position = [x, y]
                                        self.size = [w, h]

                                predicted_roi = SimpleROI(
                                    predicted_x - obj.size[0]/2,
                                    predicted_y - obj.size[1]/2,
                                    obj.size[0],
                                    obj.size[1]
                                )

                            predicted_rois.append(predicted_roi)
                            # Increment prediction count
                            obj.prediction_count += 1

            # If we have predictions, return them
            if predicted_centroids:
                return predicted_object_ids
            return []

        # We have both existing objects and new detections
        # Initialize an array of input and output indices
        object_ids = [-1] * len(centroids)

        # First try to match based on IoU and distance
        used_objects = set()
        used_detections = set()

        object_centroids = {object_id: obj.centroids[-1] for object_id, obj in self.objects.items()}

        # Calculate distances between current objects and new centroids
        distance_matrix = {}
        for object_id, old_centroid in object_centroids.items():
            distance_matrix[object_id] = {}
            for i, new_centroid in enumerate(centroids):
                # Calculate Euclidean distance
                dist = np.sqrt((old_centroid[0] - new_centroid[0])**2 +
                              (old_centroid[1] - new_centroid[1])**2)

                # Calculate IoU between predicted box and detected box
                old_obj = self.objects[object_id]
                old_half_w, old_half_h = old_obj.size[0]/2, old_obj.size[1]/2
                old_box = [
                    old_centroid[0] - old_half_w,
                    old_centroid[1] - old_half_h,
                    old_centroid[0] + old_half_w,
                    old_centroid[1] + old_half_h
                ]

                new_half_w, new_half_h = rois[i].size[0]/2, rois[i].size[1]/2
                new_box = [
                    new_centroid[0] - new_half_w,
                    new_centroid[1] - new_half_h,
                    new_centroid[0] + new_half_w,
                    new_centroid[1] + new_half_h
                ]

                # Calculate IoU
                iou = self._calculate_iou(old_box, new_box)

                # Weighted distance metric (combines distance and IoU)
                weighted_dist = dist * (1.0 - 0.5 * iou)

                distance_matrix[object_id][i] = weighted_dist

        # Sort object IDs by their minimum distance to any centroid
        sorted_objects = sorted(distance_matrix.keys(),
                              key=lambda object_id: min(distance_matrix[object_id].values()))

        # Associate objects with new detections
        for object_id in sorted_objects:
            if object_id in used_objects:
                continue

            # Sort centroids by distance to this object
            sorted_indices = sorted(distance_matrix[object_id].keys(),
                                   key=lambda idx: distance_matrix[object_id][idx])

            matched = False
            for idx in sorted_indices:
                # Skip if this detection was already matched
                if idx in used_detections:
                    continue

                # If the distance is too large, skip
                if distance_matrix[object_id][idx] > self.max_distance:
                    continue

                # Match this object with this detection
                object_ids[idx] = object_id
                used_objects.add(object_id)
                used_detections.add(idx)

                # Update object properties
                obj = self.objects[object_id]
                obj.centroids.append(centroids[idx])
                obj.last_seen = self.frame_counter
                obj.size = rois[idx].size
                obj.area = rois[idx].size[0] * rois[idx].size[1]
                obj.prediction_count = 0

                # Update direction status
                if len(obj.centroids) >= 2:
                    prev_x, prev_y = obj.centroids[-2]
                    curr_x, curr_y = obj.centroids[-1]

                    # Update velocity (smoothed)
                    delta_x = curr_x - prev_x
                    delta_y = curr_y - prev_y
                    obj.velocity_x = 0.7 * obj.velocity_x + 0.3 * delta_x
                    obj.velocity_y = 0.7 * obj.velocity_y + 0.3 * delta_y

                    # Update direction
                    if obj.velocity_x > 1:
                        obj.direction_x = "right"
                    elif obj.velocity_x < -1:
                        obj.direction_x = "left"

                    if obj.velocity_y > 1:
                        obj.direction_y = "down"
                    elif obj.velocity_y < -1:
                        obj.direction_y = "up"

                # Reset disappeared counter
                self.disappeared[object_id] = 0
                matched = True
                break

            # If the object wasn't matched, increment disappeared counter
            if not matched:
                self.disappeared[object_id] += 1

                # If we have sufficient history, try to predict
                obj = self.objects[object_id]
                if len(obj.centroids) >= 2 and obj.prediction_count < self.prediction_threshold:
                    # Calculate velocity from last known positions
                    prev_x, prev_y = obj.centroids[-2]
                    curr_x, curr_y = obj.centroids[-1]

                    # Predict new position
                    delta_x = curr_x - prev_x
                    delta_y = curr_y - prev_y
                    predicted_x = curr_x + delta_x
                    predicted_y = curr_y + delta_y

                    # Update with prediction
                    obj.centroids.append((predicted_x, predicted_y))
                    obj.prediction_count += 1

        # Clean up any objects that have disappeared for too long
        for object_id in list(self.disappeared.keys()):
            if self.disappeared[object_id] > self.max_disappeared:
                self.deregister(object_id)

        # Register any new detections that weren't matched
        for i, object_id in enumerate(object_ids):
            if object_id == -1:
                object_ids[i] = self.register(centroids[i], rois[i])

        return object_ids

    def _calculate_iou(self, boxA, boxB):
        """Calculate the Intersection over Union between two bounding boxes"""
        # Determine the coordinates of the intersection rectangle
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        # Compute the area of intersection rectangle
        interArea = max(0, xB - xA) * max(0, yB - yA)

        # Compute the area of both bounding boxes
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        # Compute the IoU
        iou = interArea / float(boxAArea + boxBArea - interArea)

        return iou


def save_last_frame_tracks(track_csv, rois, face_ids, landmarks, channel, timestamp):
    """Save the last frame's track information to CSV"""
    # Create a list to hold all track data for the current frame
    current_frame_tracks = []
    
    for i, (roi, face_id) in enumerate(zip(rois, face_ids)):
        # Extract face coordinates
        x = roi.position[0]
        y = roi.position[1]
        w = roi.size[0]
        h = roi.size[1]
        
        # Extract landmark data if available
        landmark_data = ""
        if i < len(landmarks) and landmarks[i] is not None:
            # Convert landmark array to string representation
            landmark_data = ";".join([f"{pt[0]},{pt[1]}" for pt in landmarks[i]])
        
        # Create track data dict
        track_data = {
            'channel': channel,
            'timestamp': timestamp,
            'track_id': face_id,
            'x': x,
            'y': y,
            'width': w,
            'height': h,
            'landmarks': landmark_data
        }
        current_frame_tracks.append(track_data)
    
    try:
        # Load existing CSV data if file exists
        if os.path.exists(track_csv):
            df = pd.read_csv(track_csv)
            
            # Remove existing entries for this channel+timestamp combination
            df = df[~((df['channel'] == channel) & (df['timestamp'] == timestamp))]
            
            # Append new track data
            if current_frame_tracks:
                new_df = pd.DataFrame(current_frame_tracks)
                df = pd.concat([df, new_df], ignore_index=True)
        else:
            # Create new DataFrame if file doesn't exist
            df = pd.DataFrame(current_frame_tracks)
        
        # Save to CSV
        df.to_csv(track_csv, index=False)
        log.info(f"Saved {len(current_frame_tracks)} tracks to {track_csv}")
    except Exception as e:
        log.error(f"Error saving track data: {e}")

def build_argparser():
    parser = ArgumentParser()

    general = parser.add_argument_group('General')
    general.add_argument('-i', '--input', required=True,
                         help='Required. An input to process. The input must be a single image, '
                              'a folder of images, video file or camera id.')
    general.add_argument('--loop', default=False, action='store_true',
                         help='Optional. Enable reading the input in a loop.')
    general.add_argument('-o', '--output', default='output',
                         help='Optional. Path to the output directory where face images will be saved.')
    general.add_argument('-limit', '--output_limit', default=1000, type=int,
                         help='Optional. Number of frames to process. '
                              'If 0 is set, all frames are processed.')
    general.add_argument('--crop_size', default=(0, 0), type=int, nargs=2,
                         help='Optional. Crop the input stream to this resolution.')
    general.add_argument('-u', '--utilization_monitors', default='', type=str,
                         help='Optional. List of monitors to show initially.')

    models = parser.add_argument_group('Models')
    models.add_argument('-m_fd', type=Path, required=True,
                        help='Required. Path to an .xml file with Face Detection model.')
    models.add_argument('-m_lm', type=Path, required=True,
                        help='Required. Path to an .xml file with Facial Landmarks Detection model.')
    models.add_argument('--fd_input_size', default=(0, 0), type=int, nargs=2,
                        help='Optional. Specify the input size of detection model for '
                             'reshaping. Example: 500 700.')

    infer = parser.add_argument_group('Inference options')
    infer.add_argument('-d_fd', default='CPU', choices=DEVICE_KINDS,
                       help='Optional. Target device for Face Detection model. '
                            'Default value is CPU.')
    infer.add_argument('-d_lm', default='CPU', choices=DEVICE_KINDS,
                       help='Optional. Target device for Facial Landmarks Detection '
                            'model. Default value is CPU.')
    infer.add_argument('-v', '--verbose', action='store_true',
                       help='Optional. Be more verbose.')
    infer.add_argument('-t_fd', metavar='[0..1]', type=float, default=0.6,
                       help='Optional. Probability threshold for face detections.')
    infer.add_argument('-exp_r_fd', metavar='NUMBER', type=float, default=1.15,
                       help='Optional. Scaling ratio for bboxes passed to face recognition.')
    parser.add_argument('--track_csv', type=str, default=None,
                    help='Optional. Path to the CSV file to store track continuity information.')
    parser.add_argument('--channel', type=str, default=None,
                    help='Optional. Channel identifier for the video being processed.')
    parser.add_argument('--timestamp', type=str, default=None,
                    help='Optional. Timestamp identifier for the video being processed.')
    return parser


class FrameProcessor:
    QUEUE_SIZE = 16

    def __init__(self, args):
        log.info('OpenVINO Runtime')
        log.info('\tbuild: {}'.format(get_version()))
        core = Core()

        self.face_detector = FaceDetector(core, args.m_fd,
                                          args.fd_input_size,
                                          confidence_threshold=args.t_fd,
                                          roi_scale_factor=args.exp_r_fd)
        self.landmarks_detector = LandmarksDetector(core, args.m_lm)
        self.face_tracker = EnhancedFaceTracker()

        self.face_detector.deploy(args.d_fd)
        self.landmarks_detector.deploy(args.d_lm, self.QUEUE_SIZE)

    def process(self, frame):
        rois = self.face_detector.infer((frame,))
        if self.QUEUE_SIZE < len(rois):
            log.warning('Too many faces for processing. Will be processed only {} of {}'
                        .format(self.QUEUE_SIZE, len(rois)))
            rois = rois[:self.QUEUE_SIZE]

        landmarks = self.landmarks_detector.infer((frame, rois))

        # Track the detected faces
        face_ids = self.face_tracker.update(rois)

        return [rois, landmarks, face_ids]
        
    def load_previous_tracks(self, track_csv, channel):
        """Load previous track information from CSV to enable cross-video tracking"""
        if not os.path.exists(track_csv):
            return None
        
        try:
            df = pd.read_csv(track_csv)
            # Filter for the specific channel
            channel_data = df[df['channel'] == channel]
            
            if len(channel_data) == 0:
                return None
            
            # Get the latest timestamp for this channel
            latest_timestamp = channel_data['timestamp'].max()
            latest_tracks = channel_data[channel_data['timestamp'] == latest_timestamp]
            
            if len(latest_tracks) == 0:
                return None
                
            # Convert DataFrame to list of dicts for easier processing
            track_list = latest_tracks.to_dict('records')
            return track_list
        except Exception as e:
            log.error(f"Error loading previous tracks: {e}")
            return None
            
    def initialize_tracker_with_history(self, previous_tracks):
        """Initialize the face tracker with previous track data"""
        if not previous_tracks:
            return
            
        # Clear existing tracker state
        self.face_tracker = EnhancedFaceTracker()
        
        # Initialize with previous tracks
        for track in previous_tracks:
            obj_id = track['track_id']
            x, y = float(track['x']), float(track['y'])
            w, h = float(track['width']), float(track['height'])
            
            # Create a trackable object with the previous ID
            self.face_tracker.objects[obj_id] = TrackableObject(obj_id, (x + w/2, y + h/2))
            self.face_tracker.objects[obj_id].size = (w, h)
            self.face_tracker.disappeared[obj_id] = 0
            
            # Update next_object_id to be greater than any existing ID
            self.face_tracker.next_object_id = max(self.face_tracker.next_object_id, obj_id + 1)

def center_crop(frame, crop_size):
    fh, fw, _ = frame.shape
    crop_size[0], crop_size[1] = min(fw, crop_size[0]), min(fh, crop_size[1])
    return frame[(fh - crop_size[1]) // 2 : (fh + crop_size[1]) // 2,
                 (fw - crop_size[0]) // 2 : (fw + crop_size[0]) // 2,
                 :]


def save_face_image(frame, roi, landmarks, video_name, track_id, frame_num, output_dir):
    """Extract face from frame and save it to disk"""
    # Create directory structure
    video_dir = os.path.join(output_dir, video_name)
    track_dir = os.path.join(video_dir, str(track_id))
    os.makedirs(track_dir, exist_ok=True)

    # Extract face coordinates
    xmin = max(int(roi.position[0]), 0)
    ymin = max(int(roi.position[1]), 0)
    xmax = min(int(roi.position[0] + roi.size[0]), frame.shape[1])
    ymax = min(int(roi.position[1] + roi.size[1]), frame.shape[0])

    # Crop face from frame
    face_img = frame[ymin:ymax, xmin:xmax]

    # Skip if face region is empty
    if face_img.size == 0:
        return

    # Get face detection confidence
    face_conf = roi.confidence if hasattr(roi, 'confidence') else 1.0

    # Calculate a quality score based on landmark positions
    # Check if landmarks is an array with the expected structure
    landmark_quality = 1.0  # Default value

    # Calculate average of landmark points
    if landmarks is not None and isinstance(landmarks, np.ndarray) and landmarks.size > 0:
        # Calculate eye distance (between points 0 and 1) - normalized
        if landmarks.shape[0] >= 2:
            eye_distance = np.sqrt(
                (landmarks[0][0] - landmarks[1][0])**2 +
                (landmarks[0][1] - landmarks[1][1])**2
            )
            # Normalize quality based on eye distance (1.0 is best)
            landmark_quality = min(1.0, eye_distance * 3.0)  # Scale up for visibility

    # Filename format: <frame_number>_con_score_<confidence score of face detection>_land_<confidence score of landmarks>.jpg
    filename = f"{frame_num}_con_score_{face_conf:.4f}_land_{landmark_quality:.4f}.jpg"

    # Save the face image
    output_path = os.path.join(track_dir, filename)
    cv2.imwrite(output_path, face_img)


def main():
    args = build_argparser().parse_args()

    # Create output directory
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # Extract video name from input path
    video_name = os.path.splitext(os.path.basename(args.input))[0]

    cap = open_images_capture(args.input, args.loop)
    frame_processor = FrameProcessor(args)
    
    # If cross-video tracking is enabled, load previous track data
    if args.track_csv and args.channel:
        previous_tracks = frame_processor.load_previous_tracks(args.track_csv, args.channel)
        if previous_tracks:
            log.info(f"Loaded {len(previous_tracks)} previous tracks for channel {args.channel}")
            frame_processor.initialize_tracker_with_history(previous_tracks)
            log.info("Initialized face tracker with previous track data")
    
    frame_num = 0
    first_frame_processed = False
    last_frame_rois = None
    last_frame_landmarks = None
    last_frame_face_ids = None
    
    metrics = PerformanceMetrics()
    presenter = None
    input_crop = None
    if args.crop_size[0] > 0 and args.crop_size[1] > 0:
        input_crop = np.array(args.crop_size)
    elif not (args.crop_size[0] == 0 and args.crop_size[1] == 0):
        raise ValueError('Both crop height and width should be positive')

    while True:
        start_time = perf_counter()
        frame = cap.read()
        if frame is None:
            if frame_num == 0:
                raise ValueError("Can't read an image from the input")
            break
        if input_crop is not None:
            frame = center_crop(frame, input_crop)

        # Process the frame
        rois, landmarks, face_ids = frame_processor.process(frame)
        
        # Store first and every frame's data
        if not first_frame_processed and rois:
            first_frame_processed = True
            log.info(f"First frame processed with {len(rois)} faces detected")
        
        # Always keep the latest frame's data
        if rois:
            last_frame_rois = rois.copy()
            last_frame_landmarks = landmarks.copy() if landmarks else None
            last_frame_face_ids = face_ids.copy() if face_ids else None

        # Extract and save face images for each detection
        for i, (roi, landmark_set, face_id) in enumerate(zip(rois, landmarks, face_ids)):
            # Save the face image with landmark information
            save_face_image(frame, roi, landmark_set, video_name, face_id, frame_num, output_dir)

        frame_num += 1

        # Check if we've reached the output limit
        if args.output_limit > 0 and frame_num >= args.output_limit:
            break

        metrics.update(start_time, frame)

        # Update utilization monitors if present
        if presenter is not None:
            presenter.handleKey(27)  # Just to update metrics

    # Save the last frame's track information for cross-video tracking
    if args.track_csv and args.channel and args.timestamp and last_frame_rois:
        save_last_frame_tracks(args.track_csv, last_frame_rois, last_frame_face_ids, 
                               last_frame_landmarks, args.channel, args.timestamp)
    
    metrics.log_total()
    if presenter is not None:
        for rep in presenter.reportMeans():
            log.info(rep)

    log.info(f"Processing complete. Face images saved to {output_dir}")

if __name__ == '__main__':
    sys.exit(main() or 0)

# Cross-Video Tracking
# When the next video channel101_20250328T170130.mkv is processed:

# The system loads previous track information from track_continuity.csv
# If the same person appears in the new video, they'll maintain the same track ID
# New faces will get new track IDs (e.g., 4, 5)

# After processing the second video, the directory structure looks like:

# /home/ubuntu/faceDetectionTrack/20250328/
# ├── channel101_20250328T170004/  # First video
# │   ├── 1/
# │   ├── 2/
# │   └── 3/
# └── channel101_20250328T170130/  # Second video
#     ├── 1/  # Same person as track 1 in first video
#     ├── 3/  # Same person as track 3 in first video 
#     ├── 4/  # New person
#     └── 5/  # New person
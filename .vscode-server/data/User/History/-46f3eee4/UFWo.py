#!/usr/bin/env python3

import os
import sys
import json
import boto3
from botocore.exceptions import ClientError

class FaceRecognition:
    def __init__(self, collection_id='Employees', employee_dir='./employees'):
        """Initialize the face recognition system with a collection ID and employee directory."""
        self.rekognition = boto3.client('rekognition')
        self.collection_id = collection_id
        self.employee_dir = employee_dir
        self.mapping_file = 'employee_face_mapping.json'
        
        # Ensure the collection exists
        self._ensure_collection()
        
        # Index faces if mapping doesn't exist
        if not os.path.exists(self.mapping_file):
            self.index_employee_faces()
    
    def _ensure_collection(self):
        """Create the collection if it doesn't exist."""
        try:
            self.rekognition.describe_collection(CollectionId=self.collection_id)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self.rekognition.create_collection(CollectionId=self.collection_id)
            else:
                raise
    
    def index_employee_faces(self):
        """Index all employee faces from the employee directory."""
        if not os.path.exists(self.employee_dir):
            print(f"Error: Employee directory {self.employee_dir} not found")
            sys.exit(1)
        
        employee_mapping = {}
        
        # Index each employee photo
        for filename in os.listdir(self.employee_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                # Extract employee ID from filename (customize as needed)
                employee_id = os.path.splitext(filename)[0]
                image_path = os.path.join(self.employee_dir, filename)
                
                # Read the image file
                with open(image_path, 'rb') as image_file:
                    image_bytes = image_file.read()
                
                # Index the face
                try:
                    response = self.rekognition.index_faces(
                        CollectionId=self.collection_id,
                        Image={'Bytes': image_bytes},
                        ExternalImageId=employee_id,
                        DetectionAttributes=[]
                    )
                    
                    # Store the mapping between Face ID and employee ID
                    for face in response['FaceRecords']:
                        face_id = face['Face']['FaceId']
                        employee_mapping[face_id] = employee_id
                    
                except Exception as e:
                    print(f"Error indexing {filename}: {str(e)}")
        
        # Save the mapping to a JSON file
        with open(self.mapping_file, 'w') as f:
            json.dump(employee_mapping, f)
    
    def recognize_face(self, image_path):
        """Recognize an employee from a face image."""
        if not os.path.exists(image_path):
            return {"error": f"Image file not found: {image_path}"}
        
        # Load the employee mapping
        try:
            with open(self.mapping_file, 'r') as f:
                employee_mapping = json.load(f)
        except FileNotFoundError:
            return {"error": "Employee mapping file not found. Please index employee faces first."}
        
        # Read the image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
        
        try:
            # Search for the face in the collection
            response = self.rekognition.search_faces_by_image(
                CollectionId=self.collection_id,
                Image={'Bytes': image_bytes},
                MaxFaces=5,
                FaceMatchThreshold=70
            )
            
            # Process the results
            if response['FaceMatches']:
                matches = []
                
                for match in response['FaceMatches']:
                    face_id = match['Face']['FaceId']
                    confidence = match['Similarity']
                    employee_id = employee_mapping.get(face_id, "Unknown")
                    
                    matches.append({
                        'employee_id': employee_id,
                        'confidence': confidence,
                        'face_id': face_id
                    })
                
                # Return the highest confidence match
                return matches[0]
            else:
                return {
                    'employee_id': "No match found",
                    'confidence': 0
                }
        
        except Exception as e:
            return {
                'employee_id': "Error",
                'confidence': 0,
                'error': str(e)
            }
    
    def recognize_faces_in_directory(self, input_dir):
        """Recognize faces in all images within a directory."""
        if not os.path.exists(input_dir):
            print(f"Error: Input directory {input_dir} not found")
            return {"error": f"Directory not found: {input_dir}"}
        
        results = {}
        
        # Process each image in the directory
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(input_dir, filename)
                try:
                    result = self.recognize_face(image_path)
                    results[filename] = result
                except Exception as e:
                    results[filename] = {
                        'employee_id': "Error",
                        'confidence': 0,
                        'error': str(e)
                    }
                
                # Print progress
                print(f"Processed {filename}: {results[filename]['employee_id']} ({results[filename].get('confidence', 0):.2f}%)")
        
        return results

if __name__ == "__main__":
    # Check if directory path is provided
    if len(sys.argv) != 2:
        print("Usage: ./face_recognition.py <input_directory>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    
    # Create face recognition system
    face_recognition = FaceRecognition()
    
    # Check if the input is a directory or a single file
    if os.path.isdir(input_dir):
        # Process all images in the directory
        results = face_recognition.recognize_faces_in_directory(input_dir)
        
        # Save results to a JSON file in the input directory
        output_file = os.path.join(input_dir, "recognition_results.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {output_file}")
    else:
        # Process single image
        result = face_recognition.recognize_face(input_dir)
        print(json.dumps(result, indent=2))
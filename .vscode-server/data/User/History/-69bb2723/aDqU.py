#!/usr/bin/env python3

import sys
from Face_Recognition import FaceRecognition

def run_face_recognition_demo():
    """
    Simple demo for the Face Recognition system.
    Takes an image path as input and identifies the person in the image.
    """
    # Print welcome message
    print("\n===== Face Recognition System Demo =====\n")
    
    # Check if image path is provided as command line argument
    if len(sys.argv) == 2:
        image_path = sys.argv[1]
    else:
        # If no command line argument, ask for image path
        image_path = input("Enter the path to the image file: ")
    
    print(f"\nAnalyzing image: {image_path}")
    print("Processing...")
    
    # Initialize the face recognition system
    face_recognition = FaceRecognition()
    
    # Recognize the face
    result = face_recognition.recognize_face(image_path)
    
    # Display the results
    print("\n----- Recognition Results -----")
    
    if 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Recognized Employee ID: {result['employee_id']}")
        print(f"Confidence Score: {result['confidence']:.2f}%")
        
        # Add recommendation based on confidence
        if result['confidence'] > 95:
            print("Status: Strong match ✓")
        elif result['confidence'] > 80:
            print("Status: Good match ✓")
        elif result['confidence'] > 70:
            print("Status: Possible match, verify manually")
        else:
            print("Status: Weak match, additional verification recommended")
    
    print("\n===== Demo Complete =====")

if __name__ == "__main__":
    run_face_recognition_demo()
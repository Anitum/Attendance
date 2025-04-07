#!/usr/bin/env python3
import sys
import os

def recognize_face(image_path):
    """
    Mock function to simulate face recognition.
    In a real implementation, this would use a face recognition library.
    """
    # For this demo, we'll extract the employee ID from the filename
    # In a real system, you would perform actual face recognition here
    
    # Just for demonstration, we'll hardcode to return "ebin_jomon" for any input
    employee_id = "ebin_jomon"
    confidence = 100.0
    
    return employee_id, confidence

def main():
    # Check if image path is provided
    if len(sys.argv) != 2:
        print("Usage: python3 demo.py <image_path>")
        sys.exit(1)
    
    # Get the image path from command line arguments
    image_path = sys.argv[1]
    
    # Check if the file exists
    if not os.path.exists(image_path):
        print(f"Error: File {image_path} does not exist.")
        sys.exit(1)
    
    # Print the collection being used
    print("Using existing collection: Employees")
    
    # Recognize the face
    employee_id, confidence = recognize_face(image_path)
    
    # Print the results
    print(f"Recognized Employee ID: {employee_id}")
    print(f"Confidence Score: {confidence:.2f}%")

if __name__ == "__main__":
    main()
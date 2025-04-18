import numpy as np
import cv2
from tensorflow.keras.models import load_model

# Load the trained model
model = load_model("face_recognition_model_extended.keras")

# Load the label encoder
label_encoder = np.load("label_encoder_extended.npy", allow_pickle=True)

def preprocess_image(image_path, target_size=(128, 128)):
    """Preprocesses the input image for model prediction."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Image not found or cannot be loaded!")
    
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert to RGB
    img = cv2.resize(img, target_size)  # Resize
    img = img.astype("float32") / 255.0  # Normalize
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    return img

def predict(image_path):
    """Predicts the Employee ID for the given image."""
    img = preprocess_image(image_path)
    prediction = model.predict(img)  # Get probabilities
    predicted_class_index = np.argmax(prediction)  # Get class index
    predicted_class_name = label_encoder[predicted_class_index]  # Convert to class name
    confidence = np.max(prediction)  # Get confidence score
    
    print(f"Predicted Employee ID: {predicted_class_name} with {confidence:.2f} confidence")
    return predicted_class_name, confidence

# Example Usage
image_path =r"/home/ubuntu/PushToAWSandGrey/20250408/channel401_track127_channel401_20250408T092830_127_1_confidence_93.jpg"
predict(image_path)

# Import necessary libraries
import cv2
import numpy as np
import openvino as ov
import os

# Load the model
model_xml = "/home/ubuntu/models/intel/facial-landmarks-35-adas-0002/FP32/facial-landmarks-35-adas-0002.xml"
model_bin = "/home/ubuntu/models/intel/facial-landmarks-35-adas-0002/FP32/facial-landmarks-35-adas-0002.bin"
core = ov.Core()
model = core.read_model(model_xml)
compiled_model = core.compile_model(model)

# Load the input image (use os.path.expanduser to handle the ~ in the path)
input_path = os.path.expanduser("/home/ubuntu/trash/face_recog_top1/selected_channel401_20250327T094930_channel401_20250327T094930_6_1_confidence_100.jpg")
img = cv2.imread(input_path)

if img is None:
    raise ValueError(f"Could not load image from {input_path}")

# Preprocess the image
h, w = img.shape[:2]
input_shape = compiled_model.input(0).shape
target_h, target_w = input_shape[2], input_shape[3]

# Resize and create a preprocessed copy
resized_img = cv2.resize(img, (target_w, target_h))
input_image = resized_img.transpose((2, 0, 1))  # HWC to CHW
input_image = np.expand_dims(input_image, axis=0)

# Perform inference
output = compiled_model([input_image])[0]
landmarks = output.reshape(-1, 2)  # Reshape to pairs of x,y coordinates

# Post-process landmarks (scale back to original image dimensions)
landmarks[:, 0] *= w
landmarks[:, 1] *= h

# Draw landmarks on the original image
for x, y in landmarks:
    x_coord, y_coord = int(x), int(y)
    cv2.circle(img, (x_coord, y_coord), 3, (0, 255, 0), -1)

output_dir = os.path.expanduser("~/trash/landmark_testing_output/")
os.makedirs(output_dir, exist_ok=True)

# Save the image with landmarks
output_path = os.path.expanduser("~/trash/landmark_testing_output/output_landmarks.jpg")
cv2.imwrite(output_path, img)

print(f"Image with landmarks saved to {output_path}")
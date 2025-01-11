import cv2
import mediapipe as mp
import numpy as np

# Initialize Mediapipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,  # Enables iris landmarks
    min_detection_confidence=0.5
)

mp_drawing = mp.solutions.drawing_utils

def extract_eye_parameters_comprehensive(image_path, pixels_per_mm=None):
    """
    Extracts multiple eye-related parameters from the full face image.
    
    Args:
        image_path (str): Path to the full face image.
        pixels_per_mm (float, optional): Calibration factor (pixels per millimeter). Defaults to None.
    
    Returns:
        dict: Dictionary containing 'iris_radius', 'pupil_diameter', 'pupil_displacement',
              'iris_area', 'iris_pupil_ratio', 'iris_radius_mm', 'pupil_diameter_mm'.
    """
    params = {
        'iris_radius': None,
        'pupil_diameter': None,
        'pupil_displacement': (None, None),
        'iris_area': None,
        'iris_pupil_ratio': None,
        'iris_radius_mm': None,
        'pupil_diameter_mm': None
    }
    
    try:
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Unable to read image at {image_path}")
            return params
        
        # Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Process with Face Mesh
        results = face_mesh.process(rgb_image)
        
        if not results.multi_face_landmarks:
            print("No face landmarks detected.")
            return params
        
        # Assuming single face
        face_landmarks = results.multi_face_landmarks[0]
        
        # Define iris landmark indices
        LEFT_IRIS = [468, 469, 470, 471, 472]
        RIGHT_IRIS = [473, 474, 475, 476, 477]
        
        # Function to get pixel coordinates from landmarks
        def get_pixel_coords(landmarks, indices, image_width, image_height):
            coords = []
            for idx in indices:
                if idx >= len(landmarks.landmark):
                    print(f"Warning: Landmark index {idx} is out of range.")
                    continue
                lm = landmarks.landmark[idx]
                x = int(lm.x * image_width)
                y = int(lm.y * image_height)
                coords.append((x, y))
            return coords
        
        height, width, _ = image.shape
        
        # Extract left and right iris coordinates
        left_iris_coords = get_pixel_coords(face_landmarks, LEFT_IRIS, width, height)
        right_iris_coords = get_pixel_coords(face_landmarks, RIGHT_IRIS, width, height)
        
        # Choose which eye to process (left or right)
        # For demonstration, we'll process the left eye
        iris_coords = left_iris_coords
        
        # Ensure that enough landmarks are detected
        if len(iris_coords) < 5:
            print("Insufficient iris landmarks detected.")
            return params
        
        # Calculate iris center
        iris_center_x = int(np.mean([pt[0] for pt in iris_coords]))
        iris_center_y = int(np.mean([pt[1] for pt in iris_coords]))
        
        # Calculate iris radius
        distances = [np.hypot(pt[0] - iris_center_x, pt[1] - iris_center_y) for pt in iris_coords]
        iris_radius = np.mean(distances)
        params['iris_radius'] = round(iris_radius, 2)
        
        # Calculate iris area
        iris_area = np.pi * (iris_radius ** 2)
        params['iris_area'] = round(iris_area, 2)
        
        # Define ROI around iris for pupil detection
        roi_size = int(iris_radius * 1.2)
        x1 = max(iris_center_x - roi_size, 0)
        y1 = max(iris_center_y - roi_size, 0)
        x2 = min(iris_center_x + roi_size, width)
        y2 = min(iris_center_y + roi_size, height)
        
        roi = image[y1:y2, x1:x2]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray_roi, (7, 7), 0)
        
        # Detect pupil using HoughCircles
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=20,
            param1=50,
            param2=30,
            minRadius=int(iris_radius * 0.3),
            maxRadius=int(iris_radius * 0.8)
        )
        
        if circles is not None:
            circles = np.uint16(np.around(circles))
            pupil = circles[0][0]
            pupil_center_x = x1 + pupil[0]
            pupil_center_y = y1 + pupil[1]
            pupil_diameter = pupil[2] * 2
            params['pupil_diameter'] = round(pupil_diameter, 2)
            
            # Calculate displacement
            dx = pupil_center_x - iris_center_x
            dy = pupil_center_y - iris_center_y
            params['pupil_displacement'] = (round(dx, 2), round(dy, 2))
            
            # Calculate iris to pupil ratio
            iris_pupil_ratio = iris_radius / (pupil_diameter / 2)
            params['iris_pupil_ratio'] = round(iris_pupil_ratio, 2)
            
            # Convert to millimeters if calibration factor is provided
            if pixels_per_mm:
                params['iris_radius_mm'] = round(iris_radius / pixels_per_mm, 2)
                params['pupil_diameter_mm'] = round(pupil_diameter / pixels_per_mm, 2)
            
            # Draw for visualization (optional)
            cv2.circle(image, (pupil_center_x, pupil_center_y), pupil[2], (0, 255, 0), 2)
            cv2.line(image, (iris_center_x, iris_center_y), (pupil_center_x, pupil_center_y), (255, 0, 0), 2)
            cv2.circle(image, (iris_center_x, iris_center_y), 2, (255, 0, 0), -1)
            cv2.circle(image, (pupil_center_x, pupil_center_y), 2, (0, 255, 0), -1)
        else:
            print("No pupil detected.")
        
        # Save comprehensive debug image
        debug_image_path = image_path.replace('.png', '_comprehensive_debug.png').replace('.jpg', '_comprehensive_debug.jpg')
        cv2.imwrite(debug_image_path, image)
        
        return params

    except Exception as e:
        print(e)

# Example usage
if __name__ == "__main__":
    image_path = r"c:/Users/dell/Pictures/Camera Roll/test.jpg"
    pixels_per_mm = 10 
    eye_params = extract_eye_parameters_comprehensive(image_path, pixels_per_mm)
    print(eye_params)

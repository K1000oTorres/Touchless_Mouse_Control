import os
import cv2
import mediapipe as mp
import pyautogui
from controller import Controller
from datetime import datetime


# Enables PyAutoGUI emergency stop.
# Move the mouse to the top-left corner of the screen to trigger fail-safe.
pyautogui.FAILSAFE = True


# Create records folder if it does not exist
RECORDS_FOLDER = "records"
os.makedirs(RECORDS_FOLDER, exist_ok=True)


# Open the default camera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Could not open the camera.")


# Get camera properties for video recording
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# Some cameras return 0 FPS, so we use a safe default value
if fps == 0:
    fps = 30


# Create a unique filename for every session
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
record_path = os.path.join(RECORDS_FOLDER, f"record_{timestamp}.avi")

# Video writer used to save the camera session
fourcc = cv2.VideoWriter_fourcc(*"XVID")
video_writer = cv2.VideoWriter(
    record_path,
    fourcc,
    fps,
    (frame_width, frame_height)
)

print(f"Recording started: {record_path}")


# Initialize MediaPipe Hands
mpHands = mp.solutions.hands

hands = mpHands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75
)

mpDraw = mp.solutions.drawing_utils


# Application state
paused = False

# Counter used to avoid closing the app due to a temporary false detection
multiple_hands_counter = 0
MULTIPLE_HANDS_FRAME_LIMIT = 15


# BGR colors for each action
ACTION_COLORS = {
    "Ready": (255, 255, 255),
    "No Hand Detected": (160, 160, 160),
    "Moving Cursor": (0, 255, 0),
    "Cursor Frozen": (255, 255, 0),
    "Scrolling Up": (255, 0, 0),
    "Scrolling Down": (255, 120, 0),
    "Zooming In": (255, 0, 255),
    "Zooming Out": (180, 0, 255),
    "Left Click": (0, 255, 255),
    "Right Click": (0, 165, 255),
    "Double Click": (0, 0, 255),
    "Dragging": (128, 0, 255),
    "Dragging Released": (200, 200, 0),
}


def get_action_color(action):
    """
    Returns the color assigned to the current action.
    OpenCV uses BGR format, not RGB.
    """
    return ACTION_COLORS.get(action, (255, 255, 255))


try:
    while True:
        # Read frame from camera
        success, img = cap.read()

        if not success or img is None:
            print("Could not read frame from the camera.")
            break

        # Flip image horizontally to create mirror effect
        img = cv2.flip(img, 1)

        # Convert BGR image to RGB because MediaPipe uses RGB
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Process the frame and detect hands
        results = hands.process(imgRGB)

        # Keyboard controls
        key = cv2.waitKey(5) & 0xFF

        # ESC key closes the application
        if key == 27:
            print("ESC pressed. Closing application.")
            break

        # P key pauses or resumes mouse control
        if key == ord("p"):
            paused = not paused
            print("Paused." if paused else "Resumed.")

        # If one or more hands are detected
        if results.multi_hand_landmarks:
            hand_count = len(results.multi_hand_landmarks)

            # If multiple hands are detected, block control and close after several frames
            if hand_count > 1:
                multiple_hands_counter += 1
                Controller.last_action = "Multiple Hands Detected"

                cv2.putText(
                    img,
                    "Warning: multiple hands detected",
                    (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 255),
                    2
                )

                # Release mouse button if dragging was active
                if Controller.dragging:
                    pyautogui.mouseUp(button="left")
                    Controller.dragging = False

                if multiple_hands_counter >= MULTIPLE_HANDS_FRAME_LIMIT:
                    print(
                        "Security warning: multiple hands detected consistently. "
                        "Closing application."
                    )
                    break

                action_color = (0, 0, 255)

                cv2.putText(
                    img,
                    f"Action: {Controller.last_action}",
                    (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    action_color,
                    2
                )

                video_writer.write(img)
                cv2.imshow("Hand Tracker", img)
                continue

            # Reset counter when only one hand is detected
            multiple_hands_counter = 0

            # Use the first detected hand
            Controller.hand_Landmarks = results.multi_hand_landmarks[0]

            # Draw hand landmarks on the camera window
            mpDraw.draw_landmarks(
                img,
                Controller.hand_Landmarks,
                mpHands.HAND_CONNECTIONS
            )

            # Update finger states
            Controller.update_fingers_status()

            # Execute mouse actions only if the app is not paused
            if not paused:
                Controller.cursor_moving()
                Controller.detect_scrolling()
                Controller.detect_zoomming()
                Controller.detect_clicking()
                Controller.detect_dragging()

        else:
            # Reset hand state when no hand is detected
            multiple_hands_counter = 0
            Controller.hand_Landmarks = None
            Controller.prev_hand = None
            Controller.last_action = "No Hand Detected"

            # Release mouse button if dragging was active
            if Controller.dragging:
                pyautogui.mouseUp(button="left")
                Controller.dragging = False
                print("Dragging stopped because no hand was detected.")

        # Get color for current action
        action_color = get_action_color(Controller.last_action)

        # Show last detected action on screen
        cv2.putText(
            img,
            f"Action: {Controller.last_action}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            action_color,
            2
        )

        # Show pause status on screen
        if paused:
            cv2.putText(
                img,
                "PAUSED",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

        # Save current frame to the video file
        video_writer.write(img)

        # Show camera window
        cv2.imshow("Hand Tracker", img)

finally:
    # Always release mouse button before closing
    if Controller.dragging:
        pyautogui.mouseUp(button="left")
        Controller.dragging = False

    # Release camera, video writer and OpenCV windows
    video_writer.release()
    cap.release()
    cv2.destroyAllWindows()

    print(f"Recording saved: {record_path}")
    print("Application closed safely.")
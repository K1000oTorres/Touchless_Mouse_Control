import time
import math
import pyautogui


class Controller:
    """
    Handles mouse control based on MediaPipe hand landmarks.
    """

    # Previous hand position used to calculate relative cursor movement
    prev_hand = None

    # Mouse state flags
    dragging = False
    left_clicked = False
    right_clicked = False
    double_clicked = False

    # Current hand landmarks provided by MediaPipe
    hand_Landmarks = None

    # Finger status flags
    little_finger_down = False
    little_finger_up = False
    index_finger_down = False
    index_finger_up = False
    middle_finger_down = False
    middle_finger_up = False
    ring_finger_down = False
    ring_finger_up = False
    thumb_finger_down = False
    thumb_finger_up = False

    # Combined finger states
    all_fingers_down = False
    all_fingers_up = False

    # Pinch gesture flags
    index_finger_within_thumb_finger = False
    middle_finger_within_thumb_finger = False
    ring_finger_within_thumb_finger = False
    little_finger_within_thumb_finger = False

    # Screen size
    screen_width, screen_height = pyautogui.size()

    # Cursor movement settings
    movement_ratio = 2.8
    smooth_factor = 0.65
    edge_threshold = 2

    # Cooldowns to avoid repeated unwanted actions
    click_cooldown = 0.5
    scroll_cooldown = 0.3
    zoom_cooldown = 0.4

    last_click_time = 0
    last_scroll_time = 0
    last_zoom_time = 0

    # Distance threshold used to detect pinch gestures
    pinch_threshold = 0.05

    # Last action shown on the camera window
    last_action = "Ready"
    last_action_time = 0

    # Time in seconds that important actions remain visible
    action_display_duration = 1.5

    # Priority system
    current_action_priority = 0

    @staticmethod
    def set_action(action, priority=0):
        """
        Updates the action displayed on screen.

        Priority levels:
            0 = Status actions
                (Moving Cursor, Cursor Frozen)

            1 = Gesture actions
                (Scroll, Zoom)

            2 = Mouse actions
                (Clicks, Dragging)
        """

        current_time = time.time()

        # Important actions remain visible for a short period
        if (
            Controller.current_action_priority > priority and
            current_time - Controller.last_action_time < Controller.action_display_duration
        ):
            return

        Controller.last_action = action
        Controller.last_action_time = current_time
        Controller.current_action_priority = priority

        print(action)

    @staticmethod
    def distance(point1, point2):
        """
        Calculates the 2D distance between two MediaPipe landmarks.
        """
        return math.sqrt(
            (point1.x - point2.x) ** 2 +
            (point1.y - point2.y) ** 2
        )

    @staticmethod
    def can_execute(last_time, cooldown):
        """
        Checks whether enough time has passed to execute another action.
        """
        return time.time() - last_time >= cooldown

    @staticmethod
    def update_fingers_status():
        """
        Updates the status of each finger: up, down, or pinching the thumb.
        """
        if Controller.hand_Landmarks is None:
            return

        landmarks = Controller.hand_Landmarks.landmark

        # Detect whether fingers are up or down using vertical position
        Controller.little_finger_down = landmarks[20].y > landmarks[17].y
        Controller.little_finger_up = landmarks[20].y < landmarks[17].y

        Controller.index_finger_down = landmarks[8].y > landmarks[5].y
        Controller.index_finger_up = landmarks[8].y < landmarks[5].y

        Controller.middle_finger_down = landmarks[12].y > landmarks[9].y
        Controller.middle_finger_up = landmarks[12].y < landmarks[9].y

        Controller.ring_finger_down = landmarks[16].y > landmarks[13].y
        Controller.ring_finger_up = landmarks[16].y < landmarks[13].y

        Controller.thumb_finger_down = landmarks[4].y > landmarks[13].y
        Controller.thumb_finger_up = landmarks[4].y < landmarks[13].y

        # Detect combined states
        Controller.all_fingers_down = (
            Controller.index_finger_down and
            Controller.middle_finger_down and
            Controller.ring_finger_down and
            Controller.little_finger_down
        )

        Controller.all_fingers_up = (
            Controller.index_finger_up and
            Controller.middle_finger_up and
            Controller.ring_finger_up and
            Controller.little_finger_up
        )

        # Detect pinch gestures using real distance to the thumb tip
        thumb_tip = landmarks[4]

        Controller.index_finger_within_thumb_finger = (
            Controller.distance(thumb_tip, landmarks[8]) <= Controller.pinch_threshold
        )

        Controller.middle_finger_within_thumb_finger = (
            Controller.distance(thumb_tip, landmarks[12]) <= Controller.pinch_threshold
        )

        Controller.ring_finger_within_thumb_finger = (
            Controller.distance(thumb_tip, landmarks[16]) <= Controller.pinch_threshold
        )

        Controller.little_finger_within_thumb_finger = (
            Controller.distance(thumb_tip, landmarks[20]) <= Controller.pinch_threshold
        )

    @staticmethod
    def get_position(hand_x_position, hand_y_position):
        """
        Converts hand coordinates into screen cursor coordinates.
        Uses relative movement and smoothing.
        """
        old_x, old_y = pyautogui.position()

        current_x = int(hand_x_position * Controller.screen_width)
        current_y = int(hand_y_position * Controller.screen_height)

        if Controller.prev_hand is None:
            Controller.prev_hand = [current_x, current_y]
            return old_x, old_y

        delta_x = current_x - Controller.prev_hand[0]
        delta_y = current_y - Controller.prev_hand[1]

        Controller.prev_hand = [current_x, current_y]

        target_x = old_x + delta_x * Controller.movement_ratio
        target_y = old_y + delta_y * Controller.movement_ratio

        smooth_x = old_x + (target_x - old_x) * Controller.smooth_factor
        smooth_y = old_y + (target_y - old_y) * Controller.smooth_factor

        smooth_x = max(
            Controller.edge_threshold,
            min(smooth_x, Controller.screen_width - Controller.edge_threshold)
        )

        smooth_y = max(
            Controller.edge_threshold,
            min(smooth_y, Controller.screen_height - Controller.edge_threshold)
        )

        return smooth_x, smooth_y

    @staticmethod
    def cursor_moving():
        """
        Moves the cursor using the base of the middle finger as reference.
        """
        if Controller.hand_Landmarks is None:
            return

        point = 9
        landmark = Controller.hand_Landmarks.landmark[point]

        x, y = Controller.get_position(landmark.x, landmark.y)

        # Freeze cursor when all fingers are up and thumb is down
        cursor_frozen = (
            Controller.all_fingers_up and
            Controller.thumb_finger_down
        )

        if not cursor_frozen:
            pyautogui.moveTo(x, y, duration=0)
            Controller.set_action("Moving Cursor", priority=0)
        else:
            Controller.set_action("Cursor Frozen", priority=0)

    @staticmethod
    def detect_scrolling():
        """
        Detects hand gestures for scrolling up and down.
        """
        if Controller.hand_Landmarks is None:
            return

        if not Controller.can_execute(
            Controller.last_scroll_time,
            Controller.scroll_cooldown
        ):
            return

        scrolling_up = (
            Controller.little_finger_up and
            Controller.index_finger_down and
            Controller.middle_finger_down and
            Controller.ring_finger_down
        )

        scrolling_down = (
            Controller.index_finger_up and
            Controller.middle_finger_down and
            Controller.ring_finger_down and
            Controller.little_finger_down
        )

        if scrolling_up:
            pyautogui.scroll(120)
            Controller.last_scroll_time = time.time()
            Controller.set_action("Scrolling Up", priority=1)

        elif scrolling_down:
            pyautogui.scroll(-120)
            Controller.last_scroll_time = time.time()
            Controller.set_action("Scrolling Down")

    @staticmethod
    def detect_zoomming():
        """
        Detects hand gestures for zooming in and out.
        """
        if Controller.hand_Landmarks is None:
            return

        if not Controller.can_execute(
            Controller.last_zoom_time,
            Controller.zoom_cooldown
        ):
            return

        landmarks = Controller.hand_Landmarks.landmark

        zooming = (
            Controller.index_finger_up and
            Controller.middle_finger_up and
            Controller.ring_finger_down and
            Controller.little_finger_down
        )

        index_middle_distance = Controller.distance(
            landmarks[8],
            landmarks[12]
        )

        zooming_out = zooming and index_middle_distance <= 0.06
        zooming_in = zooming and index_middle_distance > 0.06

        if zooming_out:
            pyautogui.keyDown("ctrl")
            pyautogui.scroll(-50)
            pyautogui.keyUp("ctrl")
            Controller.last_zoom_time = time.time()
            Controller.set_action("Zooming Out", priority=1)

        elif zooming_in:
            pyautogui.keyDown("ctrl")
            pyautogui.scroll(50)
            pyautogui.keyUp("ctrl")
            Controller.last_zoom_time = time.time()
            Controller.set_action("Zooming In", priority=1)

    @staticmethod
    def detect_clicking():
        """
        Detects left click, right click, and double click gestures.
        """
        if Controller.hand_Landmarks is None:
            return

        if not Controller.can_execute(
            Controller.last_click_time,
            Controller.click_cooldown
        ):
            return

        left_click_condition = (
            Controller.index_finger_within_thumb_finger and
            Controller.middle_finger_up and
            Controller.ring_finger_up and
            Controller.little_finger_up and
            not Controller.middle_finger_within_thumb_finger and
            not Controller.ring_finger_within_thumb_finger and
            not Controller.little_finger_within_thumb_finger
        )

        right_click_condition = (
            Controller.middle_finger_within_thumb_finger and
            Controller.index_finger_up and
            Controller.ring_finger_up and
            Controller.little_finger_up and
            not Controller.index_finger_within_thumb_finger and
            not Controller.ring_finger_within_thumb_finger and
            not Controller.little_finger_within_thumb_finger
        )

        double_click_condition = (
            Controller.ring_finger_within_thumb_finger and
            Controller.index_finger_up and
            Controller.middle_finger_up and
            Controller.little_finger_up and
            not Controller.index_finger_within_thumb_finger and
            not Controller.middle_finger_within_thumb_finger and
            not Controller.little_finger_within_thumb_finger
        )

        if not Controller.left_clicked and left_click_condition:
            pyautogui.click()
            Controller.left_clicked = True
            Controller.last_click_time = time.time()
            Controller.set_action("Left Click", priority=2)

        elif not Controller.index_finger_within_thumb_finger:
            Controller.left_clicked = False

        if not Controller.right_clicked and right_click_condition:
            pyautogui.rightClick()
            Controller.right_clicked = True
            Controller.last_click_time = time.time()
            Controller.set_action("Right Click", priority=2)

        elif not Controller.middle_finger_within_thumb_finger:
            Controller.right_clicked = False

        if not Controller.double_clicked and double_click_condition:
            pyautogui.doubleClick()
            Controller.double_clicked = True
            Controller.last_click_time = time.time()
            Controller.set_action("Double Click")

        elif not Controller.ring_finger_within_thumb_finger:
            Controller.double_clicked = False

    @staticmethod
    def detect_dragging():
        """
        Detects drag and drop gesture.
        """
        if Controller.hand_Landmarks is None:
            if Controller.dragging:
                pyautogui.mouseUp(button="left")
                Controller.dragging = False
                Controller.set_action("Dragging Released")
            return

        if not Controller.dragging and Controller.all_fingers_down:
            pyautogui.mouseDown(button="left")
            Controller.dragging = True
            Controller.set_action("Dragging", priority=2)

        elif Controller.dragging and not Controller.all_fingers_down:
            pyautogui.mouseUp(button="left")
            Controller.dragging = False
            Controller.set_action("Dragging Released", priority=2)
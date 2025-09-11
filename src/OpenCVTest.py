import cv2
import time

prototxt_path = '../models/MobileNetSSD_deploy.prototxt'
model_path = '../models/MobileNetSSD_deploy.caffemodel'

CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

camera_id = 0
frame_width = 640
frame_height = 480
fps_limit = 10

cap = cv2.VideoCapture(camera_id)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)

frame_time = 1 / fps_limit
prev_time = 0

# Пределы скорости моторов
MAX_SPEED = 127
TURN_SPEED = 80  # скорость при повороте

while True:
    current_time = time.time()
    if current_time - prev_time < frame_time:
        continue
    prev_time = current_time

    ret, frame = cap.read()
    if not ret:
        print("Не удалось получить кадр с камеры")
        break

    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    dog_center_x = None
    highest_confidence = 0

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            idx = int(detections[0, 0, i, 1])
            if CLASSES[idx] == "dog" and confidence > highest_confidence:
                highest_confidence = confidence
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (startX, startY, endX, endY) = box.astype("int")
                dog_center_x = (startX + endX) // 2

    if dog_center_x is not None:
        center_frame = w // 2
        offset = dog_center_x - center_frame

        # Зона "центра" +- 30 пикселей
        if abs(offset) <= 30:
            # Едем вперед
            left_speed = MAX_SPEED
            right_speed = MAX_SPEED
            action = "Внимание, СОБАКА! Едем вперед"
        elif offset < -30:
            # Поворачиваем налево
            left_speed = -TURN_SPEED
            right_speed = TURN_SPEED
            action = "Собака слева, поворачиваем"
        else:
            # Поворачиваем направо
            left_speed = TURN_SPEED
            right_speed = -TURN_SPEED
            action = "Собака справа, поворачиваем"

        print(f"{action}: левый мотор = {left_speed}, правый мотор = {right_speed}")

    else:
        # Собака не найдена - стоим на месте
        print("Собака не найдена: левый мотор = 0, правый мотор = 0")

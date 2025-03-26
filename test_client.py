import random
import socket
import pickle
import threading
import time

import cv2
SERVER_IP = ('192.168.0.30', 12345)

import rospy
from clover import srv
from std_srvs.srv import Trigger
from clover.srv import SetLEDEffect
import math
import cv2
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
from clover import long_callback
import numpy as np
from threading import Lock
from geometry_msgs.msg import PointStamped, Point
import tf2_ros
import tf2_geometry_msgs
import threading

rospy.init_node('flight')

get_telemetry = rospy.ServiceProxy('get_telemetry', srv.GetTelemetry)
navigate = rospy.ServiceProxy('navigate', srv.Navigate)
navigate_global = rospy.ServiceProxy('navigate_global', srv.NavigateGlobal)
set_altitude = rospy.ServiceProxy('set_altitude', srv.SetAltitude)
set_yaw = rospy.ServiceProxy('set_yaw', srv.SetYaw)
set_yaw_rate = rospy.ServiceProxy('set_yaw_rate', srv.SetYawRate)
set_position = rospy.ServiceProxy('set_position', srv.SetPosition)
set_velocity = rospy.ServiceProxy('set_velocity', srv.SetVelocity)
set_attitude = rospy.ServiceProxy('set_attitude', srv.SetAttitude)
set_rates = rospy.ServiceProxy('set_rates', srv.SetRates)
land = rospy.ServiceProxy('land', Trigger)
set_effect = rospy.ServiceProxy('led/set_effect', SetLEDEffect)

bridge = CvBridge()
telem_lock = Lock()

tf_buffer = tf2_ros.Buffer()
tf_listener = tf2_ros.TransformListener(tf_buffer)

camera_info = rospy.wait_for_message('main_camera/camera_info', CameraInfo)
camera_matrix = np.float64(camera_info.K).reshape(3, 3)
distortion = np.float64(camera_info.D).flatten()
point_pub = rospy.Publisher('~red_circle', PointStamped, queue_size=1)

flag = False
pause_now = False
land_now = False
mission_active = False
current_mission_thread = None
fire = []
final = []
f = []


def get_telemetry_locked(frame_id):
    with telem_lock:
        return get_telemetry(frame_id=frame_id)


current_target = {
    'x': 0,
    'y': 0,
    'z': 0,
    'yaw': float('nan'),
    'speed': 0.5,
    'frame_id': '',
    'auto_arm': False
}


def navigate_wait(x=0, y=0, z=0, yaw=float('nan'), speed=0.5, frame_id='', auto_arm=False, tolerance=0.2):
    global pause_now, land_now, current_target

    current_target = {
        'x': x,
        'y': y,
        'z': z,
        'yaw': yaw,
        'speed': speed,
        'frame_id': frame_id,
        'auto_arm': auto_arm
    }

    navigate(x=x, y=y, z=z, yaw=yaw, speed=speed, frame_id=frame_id, auto_arm=auto_arm)

    while not rospy.is_shutdown() and not land_now:
        if pause_now:
            # При паузе останавливаем коптер на текущей позиции
            telem = get_telemetry_locked(frame_id=frame_id)
            navigate(x=telem.x, y=telem.y, z=telem.z, yaw=telem.yaw, frame_id=frame_id)
            rospy.sleep(0.2)
            continue

        telem = get_telemetry_locked(frame_id='navigate_target')
        if math.sqrt(telem.x ** 2 + telem.y ** 2 + telem.z ** 2) < tolerance:
            break
        rospy.sleep(0.2)

        if land_now:
            land()
            return False

    return not land_now


def img_xy_to_point(xy, dist, camera_matrix):
    xy = cv2.undistortPoints(xy, camera_matrix, distortion, P=camera_matrix)[0][0]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    # Shift points to center
    xy -= cx, cy

    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]

    return Point(x=xy[0] * dist / fx, y=xy[1] * dist / fy, z=dist)


def get_center_of_mass(mask):
    M = cv2.moments(mask)
    if M['m00'] == 0:
        return None
    return M['m10'] // M['m00'], M['m01'] // M['m00']


red_lower1 = np.array([0, 90, 181])
red_upper1 = np.array([9, 255, 255])

red_lower2 = np.array([168, 71, 157])
red_upper2 = np.array([180, 255, 255])


@long_callback
def image_callback(data):
    global flag
    global camera_height
    global camera_width
    if flag:
        image_sub.unregister()
    else:
        img = bridge.imgmsg_to_cv2(data, 'bgr8')
        x1, y1 = 50, 60  # Левый верхний угол
        x2, y2 = 190, 190  # Правый нижний угол

        # Обрезанное изображение
        img = img[y1:y2, x1:x2]
        img_to_publish = img.copy()

        cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
        cx_cropped = cx - x1
        cy_cropped = cy - y1

        cropped_camera_matrix = camera_matrix.copy()
        cropped_camera_matrix[0, 2] = cx_cropped
        cropped_camera_matrix[1, 2] = cy_cropped

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask_red1 = cv2.inRange(hsv, red_lower1, red_upper1)
        mask_red2 = cv2.inRange(hsv, red_lower2, red_upper2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        mask_yellow = cv2.inRange(hsv, (9, 90, 175), (34, 255, 255))

        mask_red = cv2.bitwise_or(mask_red, mask_yellow)

        object_found = False
        contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) > 10:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(img_to_publish, (x, y), (x + w, y + h), (0, 255, 0), 2)
                object_found = True

        if object_found:
            cv2.putText(img_to_publish, "OBJECT DETECTED", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            cv2.putText(img_to_publish, "NO OBJECTS", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        marked_image_msg = bridge.cv2_to_imgmsg(img_to_publish, 'bgr8')
        marked_image_pub.publish(marked_image_msg)

        M = cv2.moments(mask_red)
        xy = get_center_of_mass(mask_red)

        if xy is None:
            return

        # calculate and publish the position of the circle in 3D space
        telem = get_telemetry_locked(frame_id='terrain')
        altitude = telem.z if telem is not None else 1.0
        xy3d = img_xy_to_point(xy, altitude, cropped_camera_matrix)

        try:
            target = PointStamped(header=data.header, point=xy3d)
            setpoint = tf_buffer.transform(target, 'map', timeout=rospy.Duration(0.2))

            # Вывод абсолютных координат на экран
            # print(f"Абсолютные координаты объекта: x={setpoint.point.x:.2f}, y={setpoint.point.y:.2f}")
            fire.append([round(setpoint.point.x, 4), round(setpoint.point.y, 4)])

            # Публикация координат
            point_pub.publish(target)

        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
            rospy.logerr(f"Ошибка преобразования координат: {e}")
        image_pub.publish(bridge.cv2_to_imgmsg(mask_red, 'mono8'))


image_pub = rospy.Publisher('pepepepepe', Image)
image_sub = rospy.Subscriber('main_camera/image_raw', Image, image_callback)
marked_image_pub = rospy.Publisher('marked_object_image', Image, queue_size=1)

def get_battery():
    return ['bat', round(get_telemetry().voltage, 2), round((get_telemetry().voltage / 16.8) * 100, 2)]


def pause():
    global pause_now
    pause_now = not pause_now  # Переключаем состояние паузы
    if pause_now:
        print("Mission paused")
        set_effect(r=255, g=165, b=0)  # Оранжевый свет при паузе
    else:
        print("Mission resumed - continuing to target")
        # При возобновлении продолжаем движение к последней запомненной точке
        if mission_active:
            navigate(**current_target)
        set_effect(r=0, g=255, b=0)  # Зеленый свет при продолжении
    return pause_now


def landdd():
    global land_now, mission_active, pause_now
    print("Emergency landing initiated")
    land_now = True
    pause_now = False  # Отключаем паузу, если была
    mission_active = False
    land()
    set_effect(r=255, g=0, b=0)  # Красный свет при аварийной посадке
    return True


def coords():
    global final, fire, f
    s_x, s_y = 0, 0
    cou = 0

    for i in range(len(fire) - 1):
        if abs(fire[i][0] - fire[i + 1][0]) > 0.3 or abs(fire[i][1] - fire[i + 1][1]) > 0.3 or i == len(fire) - 2:
            final.append([round(s_x / cou, 2), round(s_y / cou, 2)])
            s_x, s_y, cou = 0, 0, 0
        s_x += fire[i][0]
        s_y += fire[i][1]
        cou += 1
    final = sorted(final, key=lambda x: (x[0], x[1]))
    for i in range(len(final) - 1):
        if abs(final[i][0] - final[i + 1][0]) > 0.4 or abs(final[i][1] - final[i + 1][1]) > 0.4 or i == len(final) - 2:
            f.append([round(s_x / cou, 2), round(s_y / cou, 2)])
            s_x, s_y, cou = 0, 0, 0
        s_x += final[i][0]
        s_y += final[i][1]
        cou += 1
    if len(final) > 1 and (abs(f[-1][0] - final[-1][0]) > 0.4 or abs(f[-1][1] - final[-1][1]) > 0.4):
        f.append(final[-1])
    elif len(final) == 1:
        f.append(final[-1])
    return ['coords'] + f


def mission_routine(client_socket):
    global pause_now, land_now, mission_active, current_target, final, fire

    print("Starting mission")
    mission_active = True
    land_now = False
    set_effect(r=255, g=165, b=0)
    # Взлет

    if not navigate_wait(z=1, frame_id='body', auto_arm=True):
        return

    rospy.sleep(2)

    # Точка 1
    if not navigate_wait(x=0, y=0, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=0, y=3, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=0, y=6, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=2, y=6, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=2, y=3, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=2, y=0, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=2, y=1, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=4, y=2, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=4, y=6, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    if not navigate_wait(x=0, y=0, z=1, frame_id='aruco_map'):
        return

    rospy.sleep(2)

    flag = False
    rospy.sleep(2)
    send_variable(['1_mission_end', coords()], client_socket)
    mission_active = False
    print("Mission completed")
    set_effect(r=255, g=165, b=0)  # Синий свет при завершении


def start_mission(client_socket):
    global current_mission_thread, mission_active

    if mission_active:
        print("Mission is already running")
        return False

    # Останавливаем предыдущий поток миссии, если он есть
    if current_mission_thread is not None and current_mission_thread.is_alive():
        current_mission_thread.join()

    # Сбрасываем флаги
    global pause_now, land_now
    pause_now = False
    land_now = False

    # Запускаем миссию в отдельном потоке
    current_mission_thread = threading.Thread(target=mission_routine, args=(client_socket,))
    current_mission_thread.start()

    return True



def send_variable(data, client_socket):
    serialized = pickle.dumps(data)
    client_socket.send(len(serialized).to_bytes(4, 'big'))
    client_socket.send(serialized)





def information_cycle(client_socket):

    try:
        while True:
            send_variable(get_battery(), client_socket)
            time.sleep(0.1)
            send_variable(coords(), client_socket)
            time.sleep(0.1)
    finally:
        pass

def send_message():


    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = SERVER_IP
    client_socket.connect(server_address)

    thread = threading.Thread(target=information_cycle, args=(client_socket,))
    thread.daemon = True
    thread.start()
    try:
        while True:
            #send_variable(get_battery(), client_socket)
            #send_variable(get_img(), client_socket)


            # Cтарое
            data_length = client_socket.recv(4)
            if not data_length:
                break
            length = int.from_bytes(data_length, 'big')

            received_data = b""
            while len(received_data) < length:
                received_data += client_socket.recv(4096)

            data = pickle.loads(received_data)
            print(f"Ответ сервера: {data}")
            if data == "start":
                print('Выполняю команду start')
                send_variable("start", client_socket)
                start_mission()
            elif data == "pause":
                print('Выполняю команду pause')
                send_variable("pause", client_socket)
                pause()
            elif data == "land":
                print('Выполняю команду land')
                send_variable("land", client_socket)
                landdd()
                #serialized = pickle.dumps("land")
                #client_socket.send(len(serialized).to_bytes(4, 'big'))
                #client_socket.send(serialized)
    finally:
        client_socket.close()


#send_message_thread = threading.Thread(target=send_message)
#send_message_thread.daemon = True
#send_message_thread.start()
send_message()
import socket
import pickle
import threading
import queue

import cv2
#import numpy

import interface
import interface
import file_to_drone

message_queue = queue.Queue()
connected_clients = {}  # Хранилище: IP-адрес -> сокет

def send_data_to_client(client_socket, data):
    """Отправляет сериализованные данные клиенту."""
    try:
        serialized_data = pickle.dumps(data)
        data_length = len(serialized_data).to_bytes(4, 'big')
        client_socket.sendall(data_length + serialized_data)
    except Exception as e:
        print(f"Ошибка отправки данных клиенту: {e}")

def handle_client(client_socket, client_address):
    try:
        ip_address = client_address[0]
        connected_clients[ip_address] = client_socket  # Сохраняем клиента по IP
        print(f"Клиент {client_address} подключен. Всего клиентов: {len(connected_clients)}")
        while True:
            # Получаем длину данных
            data_length = client_socket.recv(4)
            if not data_length:
                return
            length = int.from_bytes(data_length, 'big')

            # Получаем сериализованные данные
            received_data = b""
            while len(received_data) < length:
                received_data += client_socket.recv(4096)

            # Десериализуем объект
            obj = pickle.loads(received_data)
            #if type(obj) == numpy.ndarray:
            #    print('Изображение получено')
            #    app.update_drone_image(1, obj)
            if type(obj) == list:
                if obj[0] == 'bat':
                    if ip_address == '192.168.0.10':
                        app.update_battery_status(1, obj[1], obj[2])
                    if ip_address == '192.168.0.20':
                        app.update_battery_status(2, obj[1], obj[2])
                    if ip_address == '192.168.2.110':
                        app.update_battery_status(1, obj[1], obj[2])
                if obj[0] == 'coords':
                    app.clear_fire()
                    for i in obj[1]:
                        app.update_fire(i, 0)
                if obj[0] == '1_mission_end':
                    send_data_to_client(connected_clients['192.168.0.20'], ['coords', obj[1]])
            if obj == '2_mission_end':
                app.message_queue.put('land')

            print(f"Получен ответ от клиента {ip_address}: {obj}")


    except Exception as e:
        print(f"Ошибка клиента {client_address}: {e}")
    finally:
        ip_address = client_address[0]
        if ip_address in connected_clients:
            del connected_clients[ip_address]
            client_socket.close()
            print(f"Клиент {client_address} отключен. Всего клиентов: {len(connected_clients)}")

def send_command_to_client(client_ip, command):
    """Отправляет команду конкретному клиенту по его IP-адресу."""
    if client_ip in connected_clients:
        client_socket = connected_clients[client_ip]
        send_data_to_client(client_socket, command)
        print(f"Отправлена команда '{command}' клиенту {client_ip}")
        return True
    else:
        print(f"Клиент с IP-адресом {client_ip} не найден.")
        return False

def process_messages():
    """Функция для постоянной обработки сообщений из очереди."""
    while True:
        try:
            message = message_queue.get()  # Блокирующее получение
            print(f"Сервер получил из очереди: {message}")

            # Предположим, сообщение из очереди имеет формат: "IP_адрес:команда"
            parts = message.split(":", 1)
            if len(parts) == 2:
                target_ip = parts[0]
                command_to_send = parts[1]
                send_command_to_client(target_ip, command_to_send)
            else:
                # Если формат не соответствует, отправляем всем (или обрабатываем как-то иначе)
                print(f"Некорректный формат сообщения из очереди: {message}. Отправка всем.")
                for client_ip, client_socket in connected_clients.items():
                    send_data_to_client(client_socket, message)

        except Exception as e:
            print(f"Ошибка в process_messages: {e}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 12345))
    server.listen(5)
    print("Сервер запущен...")

    while True:
        client, addr = server.accept()
        print(f"Подключено: {addr}")
        if addr[0] == '192.168.0.10':
            app.update_connection_status(1, True)
            app.update_ready_status(1, True)
        if addr[0] == '192.168.0.20':
            app.update_connection_status(2, True)
            app.update_ready_status(2, True)


        threading.Thread(target=handle_client, args=(client, addr)).start()

def run_upload(host, username, password, local_file, remote_path):
    """Функция-обертка для вызова upload_file в отдельном потоке."""
    try:
        file_to_drone.upload_file(
            host=host,
            username=username,
            password=password,
            local_file=local_file,
            remote_path=remote_path
        )
        print(f"Загрузка файла {local_file} на {host} завершена.")
    except Exception as e:
        print(f"Ошибка при загрузке файла {local_file} на {host}: {e}")


def video(url, number):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("Не удалось открыть видеопоток")
        exit()
    while True:
        ret, frame = cap.read()
        if ret:
            app.update_drone_image(number, frame)
        else:
            break

if __name__ == "__main__":
    app = interface.AppInterface(message_queue) # Закомментируйте, если интерфейс не нужен для теста
    #app.update_drone_image(1, "kokos.png")
    app.update_drone_image(1, "load.png")
    app.update_drone_image(2, "load.png")
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    ## Параметры для загрузки файла (пример)
    #host_ip_upload = "192.168.2.110"
    #username_upload = "pi"
    #password_upload = "Dh1_RHjL"
    #local_file_path_upload = "test_client.py"
    #remote_path_dir_upload = "~/catkin_ws/src/clover"



    host_ip_upload = "192.168.0.10"
    username_upload = "pi"
    password_upload = "raspberry"
    local_file_path_upload = "test_client.py"
    remote_path_dir_upload = "~/catkin_ws/src/clover"
    upload_thread = threading.Thread(
        target=run_upload,
        args=(host_ip_upload, username_upload, password_upload, local_file_path_upload, remote_path_dir_upload)
    )
    upload_thread.daemon = True
    upload_thread.start()

    # Параметры для загрузки файла (пример)
    host_ip_upload = "192.168.0.20"
    username_upload = "pi"
    password_upload = "raspberry"
    local_file_path_upload = "test_client1.py"
    remote_path_dir_upload = "~/catkin_ws/src/clover"

    # Создаем и запускаем поток для загрузки файла
    upload_thread = threading.Thread(
        target=run_upload,
        args=(host_ip_upload, username_upload, password_upload, local_file_path_upload, remote_path_dir_upload)
    )
    upload_thread.daemon = True
    upload_thread.start()


    message_processing_thread = threading.Thread(target=process_messages)
    message_processing_thread.daemon = True
    message_processing_thread.start()

    url1 = 'http://192.168.0.10:8080/stream?topic=/marked_object_image'
    url2 = 'http://192.168.0.20:8080/stream?topic=/marked_object_image'
    thread1 = threading.Thread(target=video, args=(url1, 1))
    thread1.daemon = True
    thread1.start()
    thread2 = threading.Thread(target=video, args=(url1, 2))
    thread2.daemon = True
    thread2.start()

    import time
    if app:
        app.run()
    else:
        while True:
            time.sleep(1)
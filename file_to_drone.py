import paramiko
from scp import SCPClient


def upload_file(host, username, password, local_file, remote_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Подключаюсь к {host} как {username}...")
        ssh.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=10
        )
        print("SSH подключение установлено!")

        with SCPClient(ssh.get_transport()) as scp:
            print(f"Передаю файл {local_file} в {remote_path}...")
            scp.put(local_file, remote_path)
            print("Файл успешно загружен!")


        print("Запуск файла на дроне")
        #command = f"bash -c 'source /opt/ros/noetic/setup.bash && python3 {remote_path}/{local_file}'"
        command = f"""
                bash -c '
                source /opt/ros/noetic/setup.bash
                source ~/catkin_ws/devel/setup.bash
                python3 {remote_path}/{local_file} & echo $! > /tmp/clover_script.pid
                '
                """
        stdin, stdout, stderr = ssh.exec_command(command)
        pid = stdout.read().decode().strip()
        if pid:
            print(f"Скрипт успешно запущен (PID: {pid})")
        else:
            print("Не удалось запустить скрипт")
            print("Лог ошибок:", stderr.read().decode())

    except paramiko.AuthenticationException:
        print("Ошибка аутентификации: Неверное имя пользователя или пароль")
    except paramiko.SSHException as e:
        print(f"Ошибка SSH: {str(e)}")
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")
    finally:
        ssh.close()
        print("Соединение закрыто")

'''upload_file(
    host="192.168.1.70",    # IP дрона
    username="pi",           # Логин дрона
    password="raspberry",    # Пароль
    local_file="client_1.py",  # Ваш файл
    remote_path="~/catkin_ws/src/clover"  # Куда сохранить
)
'''
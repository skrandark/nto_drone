'''Это код программного интерфейса, с помощью которого осуществляется управление миссие'''
import time
import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import queue

import tkinter as tk
from tkinter import ttk
import queue
from PIL import Image, ImageTk
import cv2
import numpy as np

class AppInterface:
    def __init__(self, message_queue):
        self.message_queue = message_queue
        self.root = tk.Tk()
        self.root.title("Интерфейс управления дронами")
        self.root.geometry("700x750+0+0")  # Увеличиваем высоту окна
        self.root.configure(bg='#808080')

        # Главный контейнер для статусов
        self.status_frame = tk.Frame(self.root, bg='#808080')
        self.status_frame.pack(pady=20)

        # Создаем блоки для каждого дрона
        self.create_drone_block("Дрон 1", 0)
        self.create_drone_block("Дрон 2", 1)

        # Создаем контейнер для кнопок
        self.button_frame = tk.Frame(self.root, bg='#808080')
        self.button_frame.pack(pady=10)

        # Создаем кнопки
        self.create_buttons()

        # Создаем индикатор статуса полета
        self.create_flight_status()

        # Контейнер для изображений
        self.image_frame = tk.Frame(self.root, bg='#808080')
        self.image_frame.pack(pady=10)

        # Заготовки для изображений (инициализируем с темным цветом)
        self.drone1_image_label = tk.Label(self.image_frame, bg='#555555', width=320, height=240)
        self.drone1_image_label.pack(side=tk.LEFT, padx=10)

        self.drone2_image_label = tk.Label(self.image_frame, bg='#555555', width=320, height=240)
        self.drone2_image_label.pack(side=tk.LEFT, padx=10)
        self.update_connection_status(1, False)
        self.update_ready_status(1, False)
        self.update_battery_status(1, 0, 0)
        self.update_connection_status(2, False)
        self.update_ready_status(2, False)
        self.update_battery_status(2, 0, 0)

        # Создаем таблицу для отображения данных об очагах
        self.create_fire_table()

    def create_fire_table(self):
        """Создает таблицу для отображения информации об очагах."""
        table_frame = tk.Frame(self.root, bg='#808080')
        table_frame.pack(pady=10)

        # Заголовки столбцов
        columns = ("Координаты очага", "Площадь (см^2)")
        self.fire_tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        for col in columns:
            self.fire_tree.heading(col, text=col)
            self.fire_tree.column(col, width=150)  # Можно настроить ширину столбцов

        self.fire_tree.pack(fill=tk.BOTH, expand=True)
        self.fire_data = []  # Список для хранения данных об очагах

    def update_fire(self, coords, area):
        """Обновляет таблицу с информацией об очаге.

        Args:
            coords: Кортеж с координатами (x, y).
            area: Площадь очага.
        """
        self.fire_data.append((f"{coords[0]}, {coords[1]}", area))
        self._update_fire_table_display()

    def clear_fire(self):
        """Очищает таблицу с информацией об очагах."""
        self.fire_data = []
        self._update_fire_table_display()

    def _update_fire_table_display(self):
        """Внутренний метод для обновления отображения таблицы."""
        # Очищаем таблицу
        for item in self.fire_tree.get_children():
            self.fire_tree.delete(item)

        # Заполняем таблицу новыми данными
        for row in self.fire_data:
            self.fire_tree.insert("", tk.END, values=row)

    def create_buttons(self):
        """Создает функциональные кнопки."""
        buttons = [
            ("Запуск", self.start_drone),
            ("Пауза", self.pause_drone),
            ("Посадка", self.land_drone),
            ("Очистить очаги", self.clear_fire)  # Добавлена кнопка очистки
        ]

        for text, command in buttons:
            button = tk.Button(
                self.button_frame,
                text=text,
                command=command,
                width=14
            )
            button.pack(side=tk.LEFT, padx=5)

    def create_drone_block(self, name, column):
        """Создает группу элементов интерфейса для одного дрона"""
        frame = tk.Frame(self.status_frame, bg='#808080')
        frame.grid(row=0, column=column, padx=40)

        # Заголовок блока
        label = tk.Label(
            frame,
            text=name,
            font=('Arial', 12, 'bold'),
            bg='#808080',
            fg='white'
        )
        label.pack(pady=(0, 10))

        # Индикатор подключения
        conn_label = tk.Label(
            frame,
            text="Статус подключения:",
            font=('Arial', 10),
            bg='#808080',
            fg='white'
        )
        conn_label.pack(anchor='w')

        conn_status = tk.Label(
            frame,
            text="Не подключен",
            font=('Arial', 10, 'bold'),
            bg='red',
            fg='white',
            width=15
        )
        conn_status.pack(pady=5, anchor='w')

        # Индикатор готовности
        ready_label = tk.Label(
            frame,
            text="Готовность к старту:",
            font=('Arial', 10),
            bg='#808080',
            fg='white'
        )
        ready_label.pack(anchor='w')

        ready_status = tk.Label(
            frame,
            text="Не готов",
            font=('Arial', 10, 'bold'),
            bg='red',
            fg='white',
            width=15
        )
        ready_status.pack(pady=5, anchor='w')

        # Индикатор заряда
        battery_label = tk.Label(
            frame,
            text="Заряд (V/%):",
            font=('Arial', 10),
            bg='#808080',
            fg='white'
        )
        battery_label.pack(anchor='w')

        battery_status = tk.Label(
            frame,
            text="0/0%",
            font=('Arial', 10, 'bold'),
            bg='red',
            fg='white',
            width=15
        )
        battery_status.pack(pady=5, anchor='w')

        # Сохраняем ссылки на индикаторы
        if name == "Дрон 1":
            self.drone1_connection = conn_status
            self.drone1_ready = ready_status
            self.drone1_battery = battery_status
        else:
            self.drone2_connection = conn_status
            self.drone2_ready = ready_status
            self.drone2_battery = battery_status

    def update_connection_status(self, drone_number, connected):
        """Обновляет статус подключения для выбранного дрона"""
        color = 'green' if connected else 'red'
        text = "Подключен" if connected else "Не подключен"

        if drone_number == 1:
            self.drone1_connection.config(bg=color, text=text)
        elif drone_number == 2:
            self.drone2_connection.config(bg=color, text=text)

        self.root.update_idletasks()  # Добавляем принудительное обновление

    def update_ready_status(self, drone_number, ready):
        """Обновляет статус готовности для выбранного дрона"""
        color = 'green' if ready else 'red'
        text = "Готов" if ready else "Не готов"

        if drone_number == 1:
            self.drone1_ready.config(bg=color, text=text)
        elif drone_number == 2:
            self.drone2_ready.config(bg=color, text=text)

        self.root.update_idletasks()  # Добавляем принудительное обновление

    def update_battery_status(self, drone_number, voltage, percentage):
        """Обновляет статус заряда для выбранного дрона"""
        text = f"{voltage}/{percentage}%"
        color = 'green' if percentage > 20 else 'red'  # Пример логики цвета

        if drone_number == 1:
            self.drone1_battery.config(text=text, bg=color)
        elif drone_number == 2:
            self.drone2_battery.config(text=text, bg=color)

        self.root.update_idletasks()  # Добавляем принудительное обновление

    def _display_image(self, drone_number, img_tk):
        """Внутренняя функция для отображения ImageTk.PhotoImage."""
        if drone_number == 1:
            self.drone1_image_label.config(image=img_tk)
            self.drone1_image_label.image = img_tk
        elif drone_number == 2:
            self.drone2_image_label.config(image=img_tk)
            self.drone2_image_label.image = img_tk
        self.root.update_idletasks()

    def update_drone_image(self, drone_number, image_source):
        """Обновляет изображение дрона, принимая путь к файлу или объект cv2."""
        img_pil = None
        try:
            if isinstance(image_source, str):
                # Загрузка из файла
                img_pil = Image.open(image_source)
            elif isinstance(image_source, np.ndarray):
                # Преобразование объекта cv2
                img_rgb = cv2.cvtColor(image_source, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)

            if img_pil:
                img_resized = img_pil.resize((320, 240), Image.LANCZOS)
                img_tk = ImageTk.PhotoImage(img_resized)
                self._display_image(drone_number, img_tk)
            else:
                print(f"Ошибка: Неверный тип источника изображения для дрона {drone_number}")
                self._display_image(drone_number, None) # Очищаем изображение
        except FileNotFoundError:
            print(f"Ошибка: Изображение '{image_source}' не найдено.")
            self._display_image(drone_number, None) # Очищаем изображение
        except Exception as e:
            print(f"Ошибка при обработке изображения: {e}")
            self._display_image(drone_number, None) # Очищаем изображение

    def create_flight_status(self):
        """Создает индикатор статуса полета."""
        self.flight_status_label = tk.Label(
            self.root,
            text="Статус полета: Ожидание",
            font=('Arial', 12),
            bg='#808080',
            fg='white'
        )
        self.flight_status_label.pack(pady=10)

    def start_drone(self):
        """Обработчик кнопки "Запуск"."""
        print("Запуск дронов...")
        self.message_queue.put("start")  # Отправляем сообщение серверу.
        self.update_flight_status("В полете")

        # Добавьте здесь логику запуска дронов

    def pause_drone(self):
        """Обработчик кнопки "Пауза"."""
        print("Пауза дронов...")
        self.message_queue.put("pause")  # Отправляем сообщение серверу.
        self.update_flight_status("Пауза")
        # Добавьте здесь логику паузы дронов

    def land_drone(self):
        """Обработчик кнопки "Посадка"."""
        print("Посадка дронов...")
        self.message_queue.put("land")  # Отправляем сообщение серверу.
        self.update_flight_status("Посадка")
        # Добавьте здесь логику посадки дронов

    #def emergency_stop(self):
    #    """Обработчик кнопки "Экстренное выключение"."""
    #    print("Экстренное выключение дронов...")
    #    self.message_queue.put("OFF")  # Отправляем сообщение серверу.
    #    self.update_flight_status("Экстренное выключение")
    #    # Добавьте здесь логику экстренного выключения дронов

    def update_flight_status(self, status):
        """Обновляет статус полета."""
        self.flight_status_label.config(text=f"Статус полета: {status}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AppInterface(queue.Queue())
    # Пример обновления статусов (для тестирования)
    app.update_connection_status(1, True)
    app.update_ready_status(1, True)
    app.update_battery_status(1, 15.5, 85)
    app.update_connection_status(2, False)
    app.update_ready_status(2, False)
    app.update_battery_status(2, 12.1, 15)

    # Пример обновления изображений (замените на реальные пути к изображениям)
    app.update_drone_image(1, "load.png")
    app.update_drone_image(2, "load.png")
    app.update_fire((10, 20), 15)
    app.update_fire([12, 23], 15)

    #time.sleep(3)
    app.run()

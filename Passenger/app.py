from flask import Flask, render_template, request, jsonify
import sqlite3
import random
import threading
import time
import logging
import requests
from datetime import datetime, timedelta
app = Flask(__name__)

# Логирование действий пассажиров.
passenger_logger = logging.getLogger('passenger_actions')
passenger_logger.setLevel(logging.INFO)
handler = logging.FileHandler('passenger_actions.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s')) # noqa
passenger_logger.addHandler(handler)

# Логирование действий пользователя.
user_logger = logging.getLogger('user_actions')
user_logger.setLevel(logging.INFO)
handler = logging.FileHandler('user_actions.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s')) # noqa
user_logger.addHandler(handler)

# Управление потоком авто-генерации.
auto_generation_thread = None
auto_generation_running = False

table = '26.228.200.110:5555' # IP табло.
ticket_office = '26.109.26.0:5555' # IP кассы.
check_in = '26.109.26.0:5555' # IP регистрации.
transport = '26.132.135.106:5555' # IP службы транспорта.

# Временные параметры.
ticket_office_close = 180
check_in_end = 30
late = 20
waiting = 10
check_time = 10
action_await = 7

# Модельного время.
current_time = ''
def get_model_time():
    global current_time

    response = requests.get(f"http://{table}/departure-board/time?days=true") # noqa

    current_time = table_convert(response.text.strip())
    print(current_time)

# Перевод времени в формат sqlite.
def convert_to_sqlite_format(time_str):
    dt_obj = datetime.strptime(time_str, "%m/%d/%Y %I:%M:%S %p")

    return dt_obj.strftime("%Y-%m-%d %H:%M:%S")

def table_convert(time_str):
    time_str = time_str.strip('"')
    time_str = time_str.split('.')[0]

    dt_obj = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")

    return dt_obj.strftime("%Y-%m-%d %H:%M:%S")

# Рандомизация поведения.
def random_behavior():
    behaviors = ['Обычный', 'Продажа', 'Мошенник касса', 'Мошенник регистрация', 'Опоздавший касса',
                 'Опоздавший регистрация']
    weights = [55, 20, 5, 5, 10, 5]
    return random.choices(behaviors, weights=weights, k=1)[0]

# Рандомизация веса багажа.
def random_baggage_weight():
    return random.randint(0, 30)

# Обработка времени действия.
def action_time_thread():
    time.sleep(action_await)
    while True:
        get_model_time()
        global current_time
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        c.execute(
            "SELECT id, behavior, status, action_time, flight_id, baggage_weight FROM passengers WHERE "
            "strftime('%s', action_time) < strftime('%s', ?)",
            (current_time, ))
        passengers = c.fetchall()
        passengers_by_status = {}
        for passenger in passengers:
            passenger_id, behavior, status, action_time, flight_id, baggage_weight = passenger
            if status not in passengers_by_status:
                passengers_by_status[status] = []
            passengers_by_status[status].append((passenger_id, behavior, flight_id, baggage_weight))

        for status, passenger_group in passengers_by_status.items():
            update_passenger_status(status, passenger_group, current_time)

        conn.commit()
        conn.close()
        time.sleep(check_time)

# Функция для обновления статуса группы пассажиров
def update_passenger_status(status, passenger_group, model_time):
    if status == "Поиск билета":
        _ = requests.get(f"http://{ticket_office}/ticket-office/available-flights") # noqa

    elif status == "Покупка билета":
        ticket_data = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2],
                "baggage_weight": passenger[3]
            }
            for passenger in passenger_group
        ]
        _ = requests.post(f"http://{ticket_office}/ticket-office/buy-ticket", json=ticket_data) # noqa

    elif status == "Продажа билета":
        return_data = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2]
            }
            for passenger in passenger_group
            ]
        _ = requests.post(f"http://{ticket_office}/ticket-office/return-ticket", json=return_data) # noqa

    elif status == "Регистрация":
        passenger_ids = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2]
            }
            for passenger in passenger_group
            ]
        _ = requests.post(f"http://{ticket_office}/checkin/passenger", json=passenger_ids) # noqa

    elif status == "На посадку":
        boarding_data = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2]
            }
            for passenger in passenger_group
        ]
        print(boarding_data)
        _ = requests.post(f"http://{transport}/transportation-pass", json=boarding_data)  # noqa

    elif status == "На борту":
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        for passenger in passenger_group:
            passenger_id, behavior, flight_id, baggage_weight = passenger
            c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",
                      ("Удаление", model_time, passenger_id))
        conn.commit()
        conn.close()
    elif status == "Удаление":
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        c.execute("DELETE from passengers WHERE status like 'Удаление'")
        deleted_rows = c.rowcount
        passenger_logger.info(f"Аэропорт покинуло {deleted_rows} человек.")
        conn.commit()
        conn.close()

# Авто-генерация пассажиров.
def auto_generate_passengers(num_passengers, interval, behavior, baggage_weight):
    global auto_generation_running
    while auto_generation_running:
        conn = sqlite3.connect('passengers.db') # noqa
        c = conn.cursor()
        for _ in range(num_passengers):
            current_behavior = behavior if behavior != 'Случайно' else random_behavior()
            current_baggage_weight = baggage_weight if baggage_weight is None else random_baggage_weight()
            c.execute("INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                      (current_behavior, 'Поиск билета', current_baggage_weight, current_time))
        conn.commit()
        conn.close()
        time.sleep(interval)

# Вычисление времени действия пассажиров.
def random_time(start, end):
    start_time = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")

    if end_time < start_time:
        day_difference = (end_time - start_time).days
        end_time += timedelta(days=abs(day_difference))

    time_difference = (end_time - start_time).total_seconds() / 60

    random_minutes = random.randint(0, int(time_difference) - 1)

    result = start_time + timedelta(minutes=random_minutes)

    return result.strftime("%Y-%m-%d %H:%M:%S")

# Вычисление границ временного действия.
def manipulate_time(time_str, operator, minutes):
    time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

    new_time = ''
    if operator == '+':
        new_time = time_obj + timedelta(minutes=minutes)
    elif operator == '-':
        new_time = time_obj - timedelta(minutes=minutes)

    return new_time.strftime("%Y-%m-%d %H:%M:%S")

# Обработка времени действия.
threading.Thread(target=action_time_thread, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_passengers', methods=['POST'])
def create_passengers():
    data = request.json
    num_passengers = int(data.get('num_passengers'))
    behavior = data.get('behavior')
    baggage_weight = data.get('baggage_weight')
    if not num_passengers:
        return jsonify({"error": "Один из параметров не был заполнен."}), 400

    conn = sqlite3.connect('passengers.db') # noqa
    c = conn.cursor()
    for _ in range(num_passengers):
        current_behavior = behavior if behavior != 'Случайно' else random_behavior()
        current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
        c.execute("INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                  (current_behavior, 'Поиск билета', current_baggage_weight, current_time))
    conn.commit()
    conn.close()

    user_logger.info(
        f"Пользователь сгенерировал {num_passengers} пассажиров с характеристиками: поведение - {behavior},"
        f" вес багажа - {baggage_weight if baggage_weight is not None else 'Случайно'}")

    return jsonify({"message": f"Успешно было создано {num_passengers} пассажиров."}), 200

@app.route('/start_auto_generation', methods=['POST'])
def start_auto_generation():
    global auto_generation_thread, auto_generation_running

    data = request.json
    num_passengers = int(data.get('num_passengers'))
    interval = int(data.get('interval'))
    behavior = data.get('behavior')
    baggage_weight = data.get('baggage_weight')

    if not num_passengers or not interval:
        return jsonify({"error": "Один из параметров не был заполнен."}), 400

    if auto_generation_thread:
        auto_generation_running = False
        auto_generation_thread.join() # noqa

    auto_generation_running = True
    auto_generation_thread = threading.Thread(target=auto_generate_passengers,
                                              args=(num_passengers, interval, behavior, baggage_weight), daemon=True)
    auto_generation_thread.start()

    user_logger.info(
        f"Пользователь включил авто-генерацию пассажиров со следующими параметрами: число генерируемых пассажиров - {num_passengers},"
        f" интервал генераций - {interval}, поведение - {behavior}, вес багажа - {baggage_weight if baggage_weight is not None else 'Случайно'}")

    return jsonify({
        "message": "Была запущена авто-генерация.",
        "num_passengers": num_passengers,
        "interval": interval,
    }), 200

@app.route('/stop_auto_generation', methods=['POST'])
def stop_auto_generation():
    global auto_generation_thread, auto_generation_running

    if auto_generation_thread:
        auto_generation_running = False
        auto_generation_thread.join() # noqa
        auto_generation_thread = None

    user_logger.info(f"Пользователь отключил авто-генерацию пассажиров.")
    return jsonify({"message": "Авто-генерация остановлена."}), 200


@app.route('/passenger/available-flights', methods=['POST'])
def available_flights():
    data = request.json
    global current_time
    conn = sqlite3.connect('passengers.db')
    c = conn.cursor()

    try:
        c.execute(
            "SELECT id, behavior FROM passengers WHERE strftime('%s', action_time) < strftime('%s', ?)"
            " AND status = 'Поиск билета'",
            (current_time,)
        )
        passengers_start = c.fetchall()

        for passenger_id, passenger_behavior in passengers_start:
            flight_info = random.choice(data)
            flight_id = flight_info.get("FlightID")
            check_in_start = convert_to_sqlite_format(flight_info.get("CheckinStart"))
            departure_time = convert_to_sqlite_format(flight_info.get("DepartureTime"))

            if passenger_behavior == "Мошенник касса":
                status = 'Продажа билета'
                model_time = random_time(current_time, manipulate_time(departure_time, '-', ticket_office_close))
            elif passenger_behavior == 'Мошенник регистрация':
                status = 'Регистрация'
                model_time = random_time(check_in_start, manipulate_time(departure_time, '-', check_in_end))
            elif passenger_behavior == 'Опоздавший касса':
                status = 'Покупка билета'
                model_time = random_time(manipulate_time(departure_time, '-', ticket_office_close), departure_time)
            else:
                status = 'Покупка билета'
                model_time = random_time(current_time, manipulate_time(departure_time, '-', ticket_office_close))
            c.execute(
                "UPDATE passengers SET status = ?, action_time = ?, flight_id = ?, registration_start = ?, "
                "departure_time = ? WHERE id = ?",
                (status, model_time, flight_id, check_in_start, departure_time, passenger_id)
            )
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Поиск билета' на '{status}'.")
        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

    return jsonify(), 200

@app.route('/passenger/ticket', methods=['POST'])
def buy_ticket():
    data = request.json
    global current_time

    for info in data:
        passenger_id = info.get("PassengerId")
        status = info.get("Status")

        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            c.execute("SELECT behavior, registration_start, departure_time FROM passengers WHERE id = ?", (passenger_id,))
            behavior, registration_start ,departure_time = c.fetchone()

            new_status = ''
            model_time = ''

            if status == 'Successful':
                if behavior == "Продажа":
                    new_status = "Продажа билета"
                    model_time = random_time(current_time, manipulate_time(departure_time, '-', ticket_office_close))
                elif behavior == "Опоздавший регистрация":
                    new_status = "Регистрация"
                    model_time = random_time(manipulate_time(departure_time, '-', check_in_end), departure_time)
                else:
                    new_status = "Регистрация"
                    model_time = random_time(registration_start, manipulate_time(departure_time, '-', check_in_end))
            elif status == 'Unsuccessful':
                if random.random() > 0.2:
                    new_status = 'Поиск билета'
                    model_time = current_time
                else:
                    new_status = 'Удаление'
                    model_time = current_time

            print(status, model_time, passenger_id)
            c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",
                  (new_status, model_time, passenger_id))
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Покупка билета' на '{new_status}'.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200

@app.route('/passenger/return-ticket', methods=['POST'])
def return_ticket():
    data = request.json

    for info in data:
        new_status = ''
        passenger_id = info.get("PassengerId")
        status = info.get("Status")

        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()

        try:
            if status == 'Successful':
                new_status = 'Удаление'
            elif status == 'Unsuccessful':
                if random.random() > 0.3:
                    new_status = 'Удаление'
                else:
                    new_status = 'Поиск билета'

            c.execute("UPDATE passengers SET status = ? where id = ?",
                      (new_status, passenger_id))
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Продажа билета' на '{status}'.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200

@app.route('/passenger/check-in', methods=['POST'])
def check_in():
    data = request.json
    global current_time

    for info in data:
        passenger_id = info.get("PassengerId")
        status = info.get("Status")

        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        print(info)
        try:
            if status == 'Successful':
                c.execute("SELECT departure_time FROM passengers WHERE id = ?", (passenger_id,))
                departure_time = c.fetchone()
                model_time = random_time(current_time, manipulate_time(departure_time[0], '-', late))
                c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",('На посадку', model_time, passenger_id))
                conn.commit()
                passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Регистрация' на 'На посадку'.")
            elif status == 'Unsuccessful':
                c.execute("UPDATE passengers SET status = ? WHERE id = ?",('Удаление', passenger_id))
                passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Регистрация' на 'Удаление'.")
                conn.commit()

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200

@app.route('/passenger/transporting', methods=['POST'])
def transporting():
    data = request.json

    for info in data:
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            passenger_id = info.get("passenger_id")
            c.execute("UPDATE passengers SET status = ? WHERE id = ?",
                      ("Транспортировка", passenger_id))
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'На посадку' на 'Транспортировка'.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200


@app.route('/passenger/on-board', methods=['POST'])
def on_board():
    data = request.json
    print(data)
    for info in data:
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            passenger_id = info.get("passengerId")
            c.execute("UPDATE passengers SET status = ? WHERE id = ?",
                      ("На борту", passenger_id))
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Транспортировка' на 'На борту'.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200


if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, jsonify
import sqlite3
import random
import threading
import time
import logging
import requests
from datetime import datetime, timedelta

# from LeaveMe import for_auto_create_passengers

app = Flask(__name__)

# Логирование действий пассажиров.
passenger_logger = logging.getLogger('passenger_actions')
passenger_logger.setLevel(logging.INFO)
handler = logging.FileHandler('passenger_actions.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))  # noqa
passenger_logger.addHandler(handler)

# Логирование действий пользователя.
user_logger = logging.getLogger('user_actions')
user_logger.setLevel(logging.INFO)
handler = logging.FileHandler('user_actions.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))  # noqa
user_logger.addHandler(handler)

#
flight_loger = logging.getLogger('flights_list')
flight_loger.setLevel(logging.INFO)
handler = logging.FileHandler('flights_list.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))  # noqa
flight_loger.addHandler(handler)

# Управление потоком авто-генерации.
auto_generation_thread = None
auto_generation_running = False

table = '26.228.200.110:5555'  # IP табло.
ticket_office = '26.109.26.0:5555'  # IP кассы.
transport = '26.132.135.106:5555'  # IP службы транспорта.

# Временные параметры.
time_period = 30
check_time = 3
action_await = 7

# Модельного время.
current_time = ''


def get_model_time():
    global current_time

    try:
        response = requests.get(f"http://{table}/dep-board/api/v1/time/now")  # noqa

        current_time = table_convert(response.text.strip())
        print(f"{time.strftime("%H:%M:%S", time.localtime())} - Текущее модельное время: {current_time}")

    except Exception:  # noqa
        print(f"{time.strftime("%H:%M:%S", time.localtime())} - Модуль 'Табло' временно недоступен.")


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
    behaviors = ['Обычный', 'Возврат', 'Мошенник касса', 'Мошенник регистрация', 'Опоздавший касса',
                 'Опоздавший регистрация']
    weights = [70, 10, 5, 5, 5, 5]
    return random.choices(behaviors, weights=weights, k=1)[0]


# Рандомизация веса багажа.
def random_baggage_weight():
    return random.randint(0, 5)


# Обработка времени действия.
def action_time_thread():
    time.sleep(action_await)
    while True:
        get_model_time()
        global current_time

        if current_time != '':
            conn = sqlite3.connect('passengers.db')
            c = conn.cursor()
            try:
                with app.app_context():
                    c.execute("UPDATE passengers set action_time = ? where action_time = ''", (current_time,))
                    conn.commit()

                    c.execute(
                    "SELECT id, behavior, status, action_time, flight_id, baggage_weight FROM passengers WHERE "
                    "strftime('%s', action_time) < strftime('%s', ?)",
                    (current_time,))
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
            except sqlite3.OperationalError:
                print(f'{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка при поиске активных пассажиров.')
            finally:
                conn.close()
        time.sleep(check_time)


# Функция для обновления статуса группы пассажиров
def update_passenger_status(status, passenger_group, model_time):
    if status == "Поиск билета":
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()

        try:
            c.execute("SELECT EXISTS (SELECT 1 FROM flights WHERE is_check_in = '0');")
            result = c.fetchone()[0]

            if result == 1:
                c.execute(
                    "SELECT id, behavior FROM passengers WHERE strftime('%s', action_time) < strftime('%s', ?)"
                    " AND status = 'Поиск билета'",
                    (current_time,)
                )
                passengers_start = c.fetchall()

                for passenger_id, passenger_behavior in passengers_start:
                    c.execute("SELECT flight_id FROM flights ORDER BY RANDOM() LIMIT 1;")
                    flight_id = c.fetchone()
                    if passenger_behavior == "Мошенник касса":
                        status = 'Возврат билета'
                        model_time = random_time(current_time, manipulate_time(current_time, '+', time_period))
                    elif passenger_behavior == 'Мошенник регистрация':
                        status = 'Ожидание регистрации'
                        model_time = current_time
                    elif passenger_behavior == 'Опоздавший касса':
                        status = 'Ожидание покупки билета'
                        model_time = random_time(current_time, manipulate_time(current_time, '+', time_period))
                    else:
                        status = 'Покупка билета'
                        model_time = random_time(current_time, manipulate_time(current_time, '+', time_period))
                    c.execute(
                        "UPDATE passengers SET status = ?, action_time = ?, flight_id = ? WHERE id = ?",
                        (status, model_time, flight_id[0], passenger_id))

                    passenger_logger.info(
                        f"Пассажир {passenger_id} изменил свой статус с 'Поиск билета' на '{status}'.")
                    conn.commit()
            else:
                c.execute("delete from passengers where status = 'Поиск билета'")
                deleted = c.rowcount
                passenger_logger.info(f"{deleted} людей покинуло аэропорт ввиду отсутствия доступных рейсов.")
                conn.commit()

        except Exception as e:
            conn.rollback()
            print(
                f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время отбора рейсов для пассажиров.")
            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    elif status == "Покупка билета":
        ticket_data = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2],
                "baggage_quantity": passenger[3]
            }
            for passenger in passenger_group
        ]
        try:
            _ = requests.post(f"http://{ticket_office}/ticket-office/buy-ticket", json=ticket_data)  # noqa
        except Exception: # noqa
            print(f"{time.strftime("%H:%M:%S", time.localtime())} - Модуль 'Касса' недоступен для покупки билетов.")

    elif status == "Возврат билета":
        return_data = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2]
            }
            for passenger in passenger_group
        ]
        try:
            _ = requests.post(f"http://{ticket_office}/ticket-office/return-ticket", json=return_data)  # noqa
        except Exception: # noqa
            print(f"{time.strftime("%H:%M:%S", time.localtime())} - Модуль 'Касса' недоступен для возврата билетов.")

    elif status == "Регистрация":
        passenger_ids = [
            {
                "passenger_id": passenger[0],
                "flight_id": passenger[2]
            }
            for passenger in passenger_group
        ]
        try:
            _ = requests.post(f"http://{ticket_office}/checkin/passenger", json=passenger_ids)  # noqa
        except Exception: # noqa
            print(
                f"{time.strftime("%H:%M:%S", time.localtime())} - Модуль 'Регистрация' недоступен для регистрации пассажиров.")

    elif status == "На борту":
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            for passenger in passenger_group:
                passenger_id, behavior, flight_id, baggage_weight = passenger
                c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",
                          ("Удаление", model_time, passenger_id))
            conn.commit()
        except sqlite3.OperationalError:
            conn.rollback()
            print(
                f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка при изменении статуса с 'На борту' на 'Удаление'.")
        finally:
            conn.close()

    elif status == "Удаление":
        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            c.execute("DELETE from passengers WHERE status like 'Удаление'")
            deleted_rows = c.rowcount
            passenger_logger.info(f"Аэропорт покинуло {deleted_rows} человек.")
            conn.commit()
        except sqlite3.OperationalError:
            conn.rollback()
            print(f'{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка при удалении пассажиров.')
        finally:
            conn.close()


# Авто-генерация пассажиров.
def auto_generate_passengers(num_passengers, interval, behavior, baggage_weight):
    global auto_generation_running
    while auto_generation_running:
        conn = sqlite3.connect('passengers.db')  # noqa
        c = conn.cursor()
        try:
            if behavior == 'Все': # noqa
                behaviors = ['Обычный', 'Возврат', 'Мошенник касса', 'Мошенник регистрация', 'Опоздавший касса',
                             'Опоздавший регистрация']

                for b in behaviors:
                    for _ in range(num_passengers):
                        current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
                        c.execute(
                            "INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                            (b, 'Поиск билета', current_baggage_weight, current_time)
                        )
            else:
                for _ in range(num_passengers):
                    current_behavior = behavior if behavior != 'Случайно' else random_behavior()
                    current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
                    c.execute(
                        "INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                        (current_behavior, 'Поиск билета', current_baggage_weight, current_time)
                    )

            conn.commit()
        except sqlite3.OperationalError:
            conn.rollback()
            print(
                f"{time.strftime('%H:%M:%S', time.localtime())} - Произошла ошибка во время авто-генерации пассажиров.")
        finally:
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
# threading.Thread(target=for_auto_create_passengers, daemon=True).start()


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

    conn = sqlite3.connect('passengers.db')  # noqa
    c = conn.cursor()
    try:
        if behavior == 'Все': # noqa
            # Список всех возможных типов поведения
            behaviors = ['Обычный', 'Возврат', 'Мошенник касса', 'Мошенник регистрация', 'Опоздавший касса',
                         'Опоздавший регистрация']

            # Создаем num_passengers пассажиров для каждого типа поведения
            for b in behaviors:
                for _ in range(num_passengers):
                    current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
                    c.execute(
                        "INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                        (b, 'Поиск билета', current_baggage_weight, current_time)
                    )
        else:
            # Создаем пассажиров с указанным поведением
            for _ in range(num_passengers):
                current_behavior = behavior if behavior != 'Случайно' else random_behavior()
                current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
                c.execute(
                    "INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                    (current_behavior, 'Поиск билета', current_baggage_weight, current_time)
                )

        conn.commit()

        user_logger.info(
            f"Пользователь сгенерировал {num_passengers * 6 if behavior == 'Все' else num_passengers} "
            f"пассажиров с характеристиками: поведение - {behavior}, "
            f"вес багажа - {baggage_weight if baggage_weight is not None else 'Случайно'}"
        )

        return jsonify({
                           "message": f"Успешно было создано {num_passengers * 6 if behavior == 'Все' else num_passengers} пассажиров."}), 200

    except sqlite3.OperationalError as e:
        conn.rollback()
        print(f"{time.strftime('%H:%M:%S', time.localtime())} - Произошла ошибка во время создания пассажиров.")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


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
        auto_generation_thread.join()  # noqa

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
        auto_generation_thread.join()  # noqa
        auto_generation_thread = None

    user_logger.info(f"Пользователь отключил авто-генерацию пассажиров.")
    return jsonify({"message": "Авто-генерация остановлена."}), 200


@app.route('/passenger/available-flight', methods=['POST'])
def available_flights():
    data = request.json
    flight_id = data.get('flightId')
    airplane_id = data.get('airplaneId')

    conn = sqlite3.connect('passengers.db')
    c = conn.cursor()

    try:
        c.execute('insert into flights (flight_id, airplane_id, is_check_in) VALUES (?, ?, 0)',
                  (flight_id, airplane_id,))
        flight_loger.info(f"Рейс №{flight_id} стал доступен для покупки билетов.")
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время появления нового рейса.")

        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify(), 200


@app.route('/passenger/check-in/start/<int:flightId>', methods=['POST'])
def check_in_start(flightId):  # noqa
    check_in_end_time = table_convert(request.json)

    conn = sqlite3.connect('passengers.db')
    c = conn.cursor()

    try:
        c.execute('update flights set is_check_in=1, check_in_end_time = ? where flight_id=?',
                  (check_in_end_time, flightId))
        flight_loger.info(f"Началась регистрация на рейс №{flightId}.")

        c.execute("SELECT id FROM passengers WHERE flight_id = ? and status = 'Ожидание регистрации' and behavior != 'Опоздавший регистрация'", (flightId,))
        rows = c.fetchall()

        for row in rows:
            passenger_id = row[0]
            random_action_time = random_time(current_time, check_in_end_time)
            c.execute("""
                UPDATE passengers 
                SET check_in_end_time = ?, 
                    action_time = ?, 
                    status = 'Регистрация' 
                WHERE id = ?
            """, (check_in_end_time, random_action_time, passenger_id))

        c.execute("update passengers set status = 'Покупка билета' where flight_id=? and status = 'Ожидание покупки билета'",
                  (flightId,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(
            f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время начала регистрации на рейс {flightId}.")

        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify(), 200


@app.route('/passenger/check-in/end/<int:flightId>', methods=['POST'])
def check_in_end(flightId):  # noqa
    conn = sqlite3.connect('passengers.db')
    c = conn.cursor()

    try:
        c.execute('delete from flights where flight_id = ?', (flightId,))
        flight_loger.info(f"Закончилась регистрация на рейс №{flightId}.")

        c.execute("update passengers set status='Регистрация' where flight_id=? and status = 'Ожидание регистрации'", (flightId,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(
            f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время закрытия регистрации на рейс {flightId}.")

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
            c.execute("SELECT behavior FROM passengers WHERE id = ?", (passenger_id,))
            behavior = c.fetchone()[0]

            if status == 'Successful':
                if behavior == "Возврат":
                    new_status = "Возврат билета"
                    model_time = random_time(current_time, manipulate_time(current_time, '+', time_period))
                elif behavior == "Опоздавший регистрация":
                    new_status = "Ожидание регистрации"
                    model_time = current_time
                else:
                    new_status = "Ожидание регистрации"
                    model_time = current_time

                c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",
                          (new_status, model_time, passenger_id))

            elif status == 'Unsuccessful':
                c.execute("SELECT EXISTS (SELECT 1 FROM flights WHERE is_check_in = '0');")
                result = c.fetchone()[0]

                if result:
                    if random.random() > 0.2:
                        c.execute("SELECT flight_id FROM flights ORDER BY RANDOM() LIMIT 1;")
                        flight_id = c.fetchone()[0]
                        new_status = 'Поиск билета'
                        model_time = current_time

                        c.execute("UPDATE passengers SET status = ?, action_time = ?, flight_id = ? WHERE id = ?",
                              (new_status, model_time, flight_id, passenger_id))
                    else:
                        new_status = 'Удаление'
                        model_time = current_time

                        c.execute("UPDATE passengers SET status = ?, action_time = ? WHERE id = ?",
                              (new_status, model_time, passenger_id))
                    passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Покупка билета' на '{new_status}'.")
                else:
                    c.execute("delete from passengers where status = 'Покупка билета'")
                    deleted = c.rowcount
                    passenger_logger.info(f"{deleted} людей покинуло аэропорт ввиду отсутствия доступных рейсов.")

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(
                f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время покупки билетов пассажирами.")

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
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Возврат билета' на '{status}'.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(
                f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время возврата билетов пассажирами.")

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
        new_status = ''

        conn = sqlite3.connect('passengers.db')
        c = conn.cursor()
        try:
            if status == 'Successful':
                c.execute("UPDATE passengers SET status = ? WHERE id = ?",
                          ('На посадку', passenger_id))
                new_status = 'На посадку'

            elif status == 'Unsuccessful':
                c.execute("UPDATE passengers SET status = ? WHERE id = ?", ('Удаление', passenger_id))
                new_status = 'Удаление'

            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'Регистрация' на {new_status}.")
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка во время регистрации пассажиров.")

            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200


@app.route('/passenger/transporting', methods=['POST'])
def transporting():
    data = request.json
    passengers = [item['passenger_id'] for item in data]
    
    conn = sqlite3.connect('passengers.db')
    c = conn.cursor()

    try:
        for passenger_id in passengers:
            c.execute("UPDATE passengers SET status = ? WHERE id = ?", ("Транспортировка", passenger_id))
            passenger_logger.info(f"Пассажир {passenger_id} изменил свой статус с 'На посадку' на 'Транспортировка'.")

        conn.commit()

    except sqlite3.OperationalError as e:
        conn.rollback()
        print(f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла ошибка при транспортировки пассажиров.")

        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

    return jsonify(), 200


@app.route('/passenger/on-board', methods=['POST'])
def on_board():
    data = request.json

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
            print(f"{time.strftime("%H:%M:%S", time.localtime())} - Произошла во время посадки пассажиров в самолёт.")

            return jsonify({"error": str(e)}), 500

        finally:
            conn.close()

    return jsonify(), 200


if __name__ == '__main__':
    app.run(debug=True)

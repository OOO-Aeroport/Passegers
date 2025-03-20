num_passengers = 10
delete_interval = 15
behavior = 'Случайно'
baggage_weight = None
sleeper = 5

def for_auto_create_passengers():
    import sqlite3
    import time
    from app import random_behavior, random_baggage_weight, current_time, user_logger

    last_delete_time = time.time()

    while True:
        conn = sqlite3.connect('passengers.db')  # noqa
        c = conn.cursor()

        try:
            current_time_seconds = time.time()
            if current_time_seconds - last_delete_time >= delete_interval:
                c.execute('DELETE FROM passengers') # noqa
                c.execute('DELETE FROM flights') # noqa
                conn.commit()
                last_delete_time = current_time_seconds
                print(f"{time.strftime('%H:%M:%S', time.localtime())} - Данные из таблиц passengers и flights удалены.")

            for _ in range(num_passengers):  # noqa
                current_behavior = behavior if behavior != 'Случайно' else random_behavior()
                current_baggage_weight = baggage_weight if baggage_weight is not None else random_baggage_weight()
                c.execute("INSERT INTO passengers (behavior, status, baggage_weight, action_time) VALUES (?, ?, ?, ?)",
                          (current_behavior, 'Поиск билета', current_baggage_weight, current_time))
            conn.commit()

            user_logger.info(f"Пользователь сгенерировал {num_passengers} пассажиров с характеристиками: поведение - {behavior},"
                            f" вес багажа - {baggage_weight if baggage_weight is not None else 'Случайно'}")

            print(f"{time.strftime('%H:%M:%S', time.localtime())} - Авто-генерация прошла успешно.")

        except sqlite3.OperationalError:
            conn.rollback()
            print(f"{time.strftime('%H:%M:%S', time.localtime())} - Произошла ошибка во время создания пассажиров.")

        finally:
            conn.close()
            time.sleep(sleeper)
from flask import Flask, jsonify, redirect
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)

# Доступ к Swagger.
swaggerui_blueprint = get_swaggerui_blueprint(
    '/api/docs',  # Путь для Swagger UI
    '/static/swagger.json',  # Путь к JSON-файлу с описанием API
    config={'app_name': "Airport Passenger Simulation API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix='/api/docs')

# Перенаправление с корневого пути на /api/docs
@app.route('/')
def index():
    return redirect('/api/docs')

# Описание API.
@app.route('/static/swagger.json')
def swagger():
    swagger_doc = {
        "openapi": "3.0.0",
        "info": {
            "title": "Module 'Passengers' API",
            "version": "1.0.0",
            "description": "API для симуляции поведения пассажиров в аэропорту."
        },
        "tags": [
            {
                "name": "Создание пассажиров",
                "description": "Операции для создания и управления пассажирами."
            },
            {
                "name": "Взаимодействие с кассой и регистрацией",
                "description": "Операции, связанные с покупкой билетов, возвратом и регистрацией."
            },
            {
                "name": "Посадка на рейс",
                "description": "Операции, связанные с транспортировкой и посадкой пассажиров на борт."
            },
            {
                "name": "Взаимодействие с табло",
                "description": "Операции, связанные с управлением рейсами и временем регистрации."
            }
        ],
        "paths": {
            # Секция: Создание пассажиров
            "/create_passengers": {
                "post": {
                    "tags": ["Создание пассажиров"],
                    "summary": "Создание пассажиров",
                    "description": "Создает указанное количество пассажиров с заданным поведением и весом багажа.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "num_passengers": {
                                            "type": "integer",
                                            "description": "Количество пассажиров для создания"
                                        },
                                        "behavior": {
                                            "type": "string",
                                            "description": "Тип поведения пассажиров"
                                        },
                                        "baggage_weight": {
                                            "type": "integer",
                                            "description": "Вес багажа"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Пассажиры успешно созданы."
                        },
                        "400": {
                            "description": "Один из параметров не был заполнен."
                        },
                        "500": {
                            "description": "Ошибка сервера при создании пассажиров."
                        }
                    }
                }
            },
            "/start_auto_generation": {
                "post": {
                    "tags": ["Создание пассажиров"],
                    "summary": "Запуск авто-генерации пассажиров",
                    "description": "Запускает автоматическую генерацию пассажиров с заданными параметрами.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "num_passengers": {
                                            "type": "integer",
                                            "description": "Количество пассажиров для генерации"
                                        },
                                        "interval": {
                                            "type": "integer",
                                            "description": "Интервал генерации пассажиров в секундах"
                                        },
                                        "behavior": {
                                            "type": "string",
                                            "description": "Тип поведения пассажиров"
                                        },
                                        "baggage_weight": {
                                            "type": "integer",
                                            "description": "Вес багажа"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Авто-генерация успешно запущена."
                        },
                        "400": {
                            "description": "Один из параметров не был заполнен."
                        }
                    }
                }
            },
            "/stop_auto_generation": {
                "post": {
                    "tags": ["Создание пассажиров"],
                    "summary": "Остановка авто-генерации пассажиров",
                    "description": "Останавливает автоматическую генерацию пассажиров.",
                    "responses": {
                        "200": {
                            "description": "Авто-генерация успешно остановлена."
                        }
                    }
                }
            },

            # Секция: Взаимодействие с кассой и регистрацией
            "/passenger/ticket": {
                "post": {
                    "tags": ["Взаимодействие с кассой и регистрацией"],
                    "summary": "Покупка билета",
                    "description": "Обрабатывает покупку билета пассажиром.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "PassengerId": {
                                            "type": "integer",
                                            "description": "ID пассажира"
                                        },
                                        "Status": {
                                            "type": "string",
                                            "description": "Статус покупки билета"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Покупка билета успешно обработана."
                        },
                        "500": {
                            "description": "Ошибка сервера при покупке билета."
                        }
                    }
                }
            },
            "/passenger/return-ticket": {
                "post": {
                    "tags": ["Взаимодействие с кассой и регистрацией"],
                    "summary": "Возврат билета",
                    "description": "Обрабатывает возврат билета пассажиром.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "PassengerId": {
                                            "type": "integer",
                                            "description": "ID пассажира"
                                        },
                                        "Status": {
                                            "type": "string",
                                            "description": "Статус возврата билета"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Возврат билета успешно обработан."
                        },
                        "500": {
                            "description": "Ошибка сервера при возврате билета."
                        }
                    }
                }
            },
            "/passenger/check-in": {
                "post": {
                    "tags": ["Взаимодействие с кассой и регистрацией"],
                    "summary": "Регистрация пассажира",
                    "description": "Обрабатывает регистрацию пассажира на рейс.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "PassengerId": {
                                            "type": "integer",
                                            "description": "ID пассажира"
                                        },
                                        "Status": {
                                            "type": "string",
                                            "description": "Статус регистрации"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Регистрация успешно обработана."
                        },
                        "500": {
                            "description": "Ошибка сервера при регистрации."
                        }
                    }
                }
            },

            # Секция: Посадка на рейс
            "/passenger/transporting": {
                "post": {
                    "tags": ["Посадка на рейс"],
                    "summary": "Транспортировка пассажиров",
                    "description": "Обрабатывает транспортировку пассажиров к самолету.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "passenger_id": {
                                            "type": "integer",
                                            "description": "ID пассажира"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Транспортировка успешно обработана."
                        },
                        "500": {
                            "description": "Ошибка сервера при транспортировке."
                        }
                    }
                }
            },
            "/passenger/on-board": {
                "post": {
                    "tags": ["Посадка на рейс"],
                    "summary": "Посадка пассажиров на борт",
                    "description": "Обрабатывает посадку пассажиров на борт самолета.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "passenger_id": {
                                            "type": "integer",
                                            "description": "ID пассажира"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Посадка успешно обработана."
                        },
                        "500": {
                            "description": "Ошибка сервера при посадке."
                        }
                    }
                }
            },
            "/passenger/available-flight": {
                "post": {
                    "tags": ["Взаимодействие с табло"],
                    "summary": "Добавление нового рейса",
                    "description": "Добавляет новый рейс в базу данных, делая его доступным для покупки билетов.",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "required": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "flightId": {
                                        "type": "string",
                                        "description": "Идентификатор рейса."
                                    },
                                    "airplaneId": {
                                        "type": "string",
                                        "description": "Идентификатор самолета."
                                    }
                                },
                                "required": ["flightId", "airplaneId"]
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Рейс успешно добавлен и доступен для покупки билетов."
                        },
                        "500": {
                            "description": "Ошибка сервера при добавлении рейса."
                        }
                    }
                }
            },
            "/passenger/check-in/start/{flightId}": {
                "post": {
                    "tags": ["Взаимодействие с табло"],
                    "summary": "Начало регистрации на рейс",
                    "description": "Уведомляет о начале регистрации на указанный рейс.",
                    "parameters": [
                        {
                            "name": "flightId",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "integer"
                            }
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "check_in_end_time": {
                                            "type": "string",
                                            "description": "Время окончания регистрации"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Регистрация успешно начата."
                        },
                        "500": {
                            "description": "Ошибка сервера при начале регистрации."
                        }
                    }
                }
            },
            "/passenger/check-in/end/{flightId}": {
                "post": {
                    "tags": ["Взаимодействие с табло"],
                    "summary": "Завершение регистрации на рейс",
                    "description": "Уведомляет об окончании регистрации на указанный рейс.",
                    "parameters": [
                        {
                            "name": "flightId",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "integer"
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Регистрация успешно завершена."
                        },
                        "500": {
                            "description": "Ошибка сервера при завершении регистрации."
                        }
                    }
                }
            }
        }
    }
    return jsonify(swagger_doc)

if __name__ == '__main__':
    app.run(port=5001, debug=True)
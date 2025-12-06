Дипломный проект профессии «Python-разработчик: расширенный курс»

🚀 Установка и запуск
Требования:
Python 3.10 

pip (менеджер пакетов Python)

Git


Шаг 1: Клонирование репозитория
git clone https://github.com/JonSnow011/diplom.git
cd diplom

Шаг 2: Создание виртуального окружения
python -m venv venv
venv\Scripts\activate

Шаг 3: Установка зависимостей
pip install -r requirements.txt

Шаг 4: ⚙️ Конфигурация
Файл окружения (.env)
# Email settings
EMAIL_HOST=smtp.mail.ru
EMAIL_PORT=465
EMAIL_HOST_USER=alanshagirov@bk.ru
EMAIL_HOST_PASSWORD=T83DNeWW8gqeDLDgx840
EMAIL_USE_SSL=True
ADMIN_EMAIL=alanshagirov@bk.ru
DEFAULT_FROM_EMAIL=alanshagirov@bk.ru


Шаг 5: Применение миграций
python manage.py makemigrations
python manage.py migrate


Шаг 7: Запуск сервера
python manage.py runserver

Шаг 8: Доступ к приложению
🌐 Веб-приложение: http://localhost:8000

👨‍💼 Админ-панель: http://localhost:8000/admin

📚 API документация: http://localhost:8000/api/schema/swagger-ui/

📊 Профилирование: http://localhost:8000/silk/

Важные моменты:
Пароль приложения — для mail.ru необходимо создать пароль приложения в настройках безопасности почты

Секретный ключ — сгенерируйте уникальный ключ для Django

Тестирование отправки email
bash
# Запуск полного теста
python test_order_emails.py

# Простой тест отправки
python simple_email_test.py

# Тест с реальным пользователем
python test_real_user_email.py

Запуск тестов
bash
# Тестирование всей цепочки email
python test_order_emails.py

# Проверка SMTP настроек
python check_email.py

# Создание тестового заказа
python create_order_for_alanshagirov.py
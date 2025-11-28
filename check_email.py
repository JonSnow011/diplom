import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("=" * 50)
print("ПРОВЕРКА ОТПРАВКИ EMAIL")
print("=" * 50)

print(f"Отправляем с: {settings.EMAIL_HOST_USER}")
print(f"Отправляем на: {settings.ADMIN_EMAIL}")
print(f"SMTP сервер: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")

try:
    result = send_mail(
        'Тест отправки email из Django',
        'Это тестовое сообщение. Если вы его получили - отправка работает!',
        settings.EMAIL_HOST_USER,
        [settings.ADMIN_EMAIL],
        fail_silently=False,
    )

    print("=" * 50)
    print("✅ РЕЗУЛЬТАТ: Письмо отправлено успешно!")
    print(f"Код результата: {result}")
    print("📧 Проверьте папку 'Входящие' в почте alanshioff@bk.ru")
    print("Если письма нет, проверьте 'Спам'")

except Exception as e:
    print("=" * 50)
    print("❌ ОШИБКА ОТПРАВКИ:")
    print(f"Тип ошибки: {type(e).__name__}")
    print(f"Сообщение: {e}")
    print("\n🔧 Возможные причины:")
    print("1. Неправильный пароль приложения")
    print("2. Неверные настройки SMTP")
    print("3. Блокировка антивирусом/файрволом")
    print("4. Проблемы с интернет-соединением")
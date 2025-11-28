import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings


def test_simple_email():
    print("🧪 Тестируем отправку простого email...")

    try:
        print("=== Настройки Email ===")
        print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        print(f"EMAIL_USER: {settings.EMAIL_HOST_USER}")
        print(f"ADMIN_EMAIL: {getattr(settings, 'ADMIN_EMAIL', 'Not set')}")

        # Простой тест отправки
        send_mail(
            'Тестовое письмо из Diplom проекта',
            'Это тестовое сообщение для проверки отправки email.',
            settings.EMAIL_HOST_USER,
            [settings.ADMIN_EMAIL],  # Отправляем самому себе
            fail_silently=False,
        )
        print("✅ Тестовое письмо отправлено успешно!")

    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        print("⚠️  Проверьте:")
        print("   - Правильность EMAIL_HOST_PASSWORD в .env")
        print("   - Настройки SMTP сервера mail.ru")
        print("   - Разрешения для приложений в почте mail.ru")


if __name__ == "__main__":
    test_simple_email()
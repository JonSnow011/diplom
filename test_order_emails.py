import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from backend.models import User, Order, Contact
from backend.core.email_service import EmailService


def test_order_email_chain():
    print("ТЕСТИРОВАНИЕ ПОЛНОЙ ЦЕПОЧКИ EMAIL ДЛЯ ЗАКАЗОВ")
    print("=" * 55)

    # 1. Получаем или создаем тестовые данные
    user = User.objects.first()
    if not user:
        print("Нет пользователей. Создайте пользователя через:")
        print("   - Админку: http://localhost:8000/admin")
        print("   - Или API: POST /api/v1/user/register")
        return

    print(f"Пользователь: {user.email}")

    # 2. Создаем контакт
    contact, created = Contact.objects.get_or_create(
        user=user,
        defaults={
            'city': 'Москва',
            'street': 'Тестовая улица',
            'house': '1',
            'phone': '+79999999999'
        }
    )
    if created:
        print(f"Создан контакт: {contact.city}, {contact.street}")

    # 3. Создаем заказ
    order, created = Order.objects.get_or_create(
        user=user,
        state='new',
        defaults={'contact': contact}
    )

    if created:
        print(f"Создан новый заказ #{order.id}")
    else:
        print(f"Используем существующий заказ #{order.id}")

    # 4. Тестируем отправку писем через EmailService
    print("\nЗАПУСКАЕМ ОТПРАВКУ EMAIL...")
    print("-" * 30)

    results = EmailService.send_emails_for_order(
        order=order,
        customer_email=user.email,
        admin_email="admin@myshop.com"
    )

    # 5. Выводим результаты
    print("\nРЕЗУЛЬТАТЫ ОТПРАВКИ:")
    print("=" * 25)

    if results["admin_email_sent"]:
        print("Администратору: УСПЕШНО")
        print("   Тема: Накладная для заказа...")
    else:
        print("Администратору: ОШИБКА")

    if results["customer_email_sent"]:
        print("Клиенту: УСПЕШНО")
        print("   Тема: Подтверждение заказа...")
    else:
        print("Клиенту: ОШИБКА")

    # 6. Финальный вывод
    print("\n" + "=" * 20)
    if results["admin_email_sent"] and results["customer_email_sent"]:
        print("ВСЯ ФУНКЦИОНАЛЬНОСТЬ ОТПРАВКИ EMAIL РАБОТАЕТ КОРРЕКТНО!")
        print("\nДля перехода на реальную отправку:")
        print("   1. Настройте пароль приложения в mail.ru")
        print("   2. Обновите EMAIL_HOST_PASSWORD в .env")
        print("   3. Верните SMTP настройки в settings.py")
    else:
        print("Есть проблемы с отправкой некоторых писем")
        print("Проверьте логи и шаблоны emails/")

    print("=" * 20)


if __name__ == "__main__":
    test_order_email_chain()
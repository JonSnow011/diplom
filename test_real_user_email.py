import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from backend.models import User, Order, Contact
from backend.core.email_service import EmailService


def test_real_user_email_chain():
    print("ТЕСТИРОВАНИЕ EMAIL ДЛЯ РЕАЛЬНОГО ПОЛЬЗОВАТЕЛЯ")
    print("=" * 55)

    # 1. Используем реального пользователя
    try:
        user = User.objects.get(email='alanshagirov@bk.ru')
        print(f"Пользователь: {user.email}")
    except User.DoesNotExist:
        print("Пользователь alanshagirov@bk.ru не найден")
        return

    # 2. Используем заказ #3 который создали
    try:
        order = Order.objects.get(id=3, user=user)
        print(f"Используем заказ #{order.id}")
    except Order.DoesNotExist:
        print("Заказ #3 не найден для пользователя alanshagirov@bk.ru")
        return

    # 3. Тестируем отправку писем через EmailService
    print("\nЗАПУСКАЕМ ОТПРАВКУ EMAIL...")
    print("-" * 30)

    results = EmailService.send_emails_for_order(
        order=order,
        customer_email=user.email,  # Отправляем на реальный email
        admin_email="alanshagirov@bk.ru"  # Администратору тоже на реальный email
    )

    # 4. Выводим результаты
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

    # 5. Финальный вывод
    print("\n" + "=" * 20)
    if results["admin_email_sent"] and results["customer_email_sent"]:
        print("ВСЯ ФУНКЦИОНАЛЬНОСТЬ ОТПРАВКИ EMAIL РАБОТАЕТ КОРРЕКТНО!")
        print("Проверьте почту alanshagirov@bk.ru")
    else:
        print("Есть проблемы с отправкой некоторых писем")
        if not results["customer_email_sent"]:
            print("Проблема: Mail.ru блокирует письма как спам")
            print("Решение: Попробуем изменить тему письма")

    print("=" * 20)


if __name__ == "__main__":
    test_real_user_email_chain()
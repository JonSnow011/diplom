import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from backend.models import User, Order, Contact


def create_order_for_real_user():
    print("Создаем заказ для реального пользователя...")

    # Находим пользователя
    user = User.objects.get(email='alanshagirov@bk.ru')
    print(f"Найден пользователь: {user.email}")

    # Создаем контакт
    contact, created = Contact.objects.get_or_create(
        user=user,
        defaults={
            'city': 'Москва',
            'street': 'Главная улица',
            'house': '15',
            'phone': '+79991234567'
        }
    )

    # Создаем заказ
    order = Order.objects.create(
        user=user,
        contact=contact,
        state='new'
    )

    print(f"Создан заказ #{order.id} для {user.email}")
    return order


if __name__ == "__main__":
    create_order_for_real_user()
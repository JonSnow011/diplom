from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

from backend.models import User, Order

# Добавляем импорт нашего сервиса
from backend.core.email_service import EmailService

from backend.tasks import send_email
from celery import shared_task

new_user_registered = Signal("user_id")

new_order = Signal("user_id")


@shared_task()
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля
    """
    subject = f"Токен для сброса пароля {reset_password_token.user}"
    message = reset_password_token.key
    from_email = settings.EMAIL_HOST_USER
    to_email = reset_password_token.user.email
    send_email.delay(subject, message, from_email, to_email)


@shared_task()
def new_user_registered_signal(user_id: int, **kwargs):
    """
    Отправляем письмо с подтверждением регистрации
    """
    user = User.objects.get(id=user_id)
    subject = f"Подтверждение регистрации {user.email}"
    to = [
        user.email,
    ]
    body = "Вы успешно зарегистрировались."
    message = EmailMultiAlternatives(
        subject=subject, body=body, from_email=settings.EMAIL_HOST_USER, to=to
    )
    message.send()


@shared_task()
def new_order_signal(user_id: int, **kwargs):
    """
    ОТПРАВЛЯЕМ ДВА ПИСЬМА ПРИ СОЗДАНИИ ЗАКАЗА:
    1. Администратору - накладная для исполнения
    2. Клиенту - подтверждение заказа
    """
    try:
        # Находим пользователя и его последний заказ
        user = User.objects.get(id=user_id)

        # Находим последний новый заказ пользователя (не корзину)
        order = (
            Order.objects.filter(user_id=user_id, state="new")
            .prefetch_related(
                "ordered_items__product_info__product",
                "ordered_items__product_info__product__category",
                "contact",
            )
            .latest("dt")
        )

        # Получаем email администратора из настроек
        admin_email = getattr(settings, "ADMIN_EMAIL", "admin@myshop.com")

        # Отправляем оба письма через наш EmailService
        email_results = EmailService.send_emails_for_order(
            order=order, customer_email=user.email, admin_email=admin_email
        )

        # Логируем результаты отправки
        if email_results["admin_email_sent"] and email_results["customer_email_sent"]:
            print("Оба email отправлены для заказа #{}".format(order.id))  # Исправлено!
        else:
            print(
                "⚠️ Не все email отправлены для заказа #{}. "
                "Админ: {}, "
                "Клиент: {}".format(
                    order.id,
                    email_results["admin_email_sent"],
                    email_results["customer_email_sent"],
                )
            )

    except Order.DoesNotExist:
        print("❌ Заказ не найден для пользователя {}".format(user_id))
    except Exception as e:
        print("❌ Ошибка отправки email для заказа: {}".format(e))


# Дополнительный обработчик через декоратор для надежности
@receiver(post_save, sender=Order)
def send_order_emails_on_save(sender, instance, created, **kwargs):
    """
    Дополнительный обработчик для отправки email при сохранении заказа
    """
    # Отправляем email только для новых заказов (не корзины)
    if created and instance.state == "new":
        # Запускаем асинхронную задачу
        new_order_signal.delay(instance.user.id)

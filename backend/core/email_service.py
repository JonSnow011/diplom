import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Сервис для отправки email уведомлений
    """

    @staticmethod
    def send_order_to_admin(order, admin_email):
        """
        Отправка накладной администратору для исполнения заказа
        """
        try:
            subject = (
                f'Накладная для заказа #{order.id} от {order.dt.strftime("%d.%m.%Y")}'
            )

            # Подготавливаем данные для шаблона
            context = {
                "order": order,
                "items": order.ordered_items.all(),
                "total_price": order.total_price,
            }

            # Рендерим HTML шаблон
            message = render_to_string("emails/order_to_admin.html", context)

            # Создаем объект письма
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_email],
            )
            email.content_subtype = "html"
            email.send()

            logger.info(
                f"Накладная отправлена администратору для заказа #{order.id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Ошибка отправки email администратору для заказа #{order.id}: {e}"
            )
            return False

    @staticmethod
    def send_order_confirmation_to_customer(order, customer_email):
        """
        Отправка подтверждения заказа клиенту
        """
        try:
            subject = f"Подтверждение заказа #{order.id}"

            # Подготавливаем данные для шаблона
            context = {
                "order": order,
                "items": order.ordered_items.all(),
                "total_price": order.total_price,
            }

            # Рендерим HTML шаблон
            message = render_to_string("emails/order_confirmation.html", context)

            # Создаем объект письма
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[customer_email],
            )
            email.content_subtype = "html"
            email.send()

            logger.info(
                f"Подтверждение заказа отправлено клиенту для заказа #{order.id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Ошибка отправки email подтверждения клиенту для заказа #{order.id}: {e}"
            )
            return False

    @staticmethod
    def send_emails_for_order(order, customer_email, admin_email):
        """
        Отправка обоих писем для заказа
        """
        try:
            results = {"admin_email_sent": False, "customer_email_sent": False}

            # Отправляем письмо администратору
            results["admin_email_sent"] = EmailService.send_order_to_admin(
                order=order, admin_email=admin_email
            )

            # Отправляем письмо клиенту
            results["customer_email_sent"] = (
                EmailService.send_order_confirmation_to_customer(
                    order=order, customer_email=customer_email
                )
            )

            # Логируем общий результат
            if results["admin_email_sent"] and results["customer_email_sent"]:
                logger.info(f"Оба письма успешно отправлены для заказа #{order.id}")
            else:
                logger.warning(
                    f"Не все письма отправлены для заказа #{order.id}. "
                    f'Администратор: {results["admin_email_sent"]}, '
                    f'Клиент: {results["customer_email_sent"]}'
                )

            return results

        except Exception as e:
            logger.error(f"Ошибка при отправке email для заказа #{order.id}: {e}")
            return {"admin_email_sent": False, "customer_email_sent": False}
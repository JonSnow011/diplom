"""
Refactored views with PEP8 compliance and error handling.
"""

import logging
from distutils.util import strtobool

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json

from backend.models import (
    Shop,
    Category,
    ProductInfo,
    Order,
    OrderItem,
    Contact,
    ConfirmEmailToken,
)
from backend.serializers import (
    UserSerializer,
    CategorySerializer,
    ShopSerializer,
    ProductInfoSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ContactSerializer,
)
from backend.signals import new_order
from backend.core.import_service import ImportService

logger = logging.getLogger(__name__)


class RegisterAccount(APIView):
    """API for user registration."""

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Register a new user."""
        required_fields = {
            "first_name",
            "last_name",
            "email",
            "password",
            "company",
            "position",
        }

        if not required_fields.issubset(request.data):
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
            )

        try:
            validate_password(request.data["password"])
        except ValidationError as password_error:
            error_array = [str(item) for item in password_error]
            return JsonResponse({"Status": False, "Errors": {"password": error_array}})

        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse({"Status": False, "Errors": serializer.errors})

        try:
            user = serializer.save()
            user.set_password(request.data["password"])
            user.save()
            return JsonResponse({"Status": True})
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при создании пользователя"}
            )


class ConfirmAccount(APIView):
    """API for email confirmation."""

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Confirm user email with token."""
        if not {"email", "token"}.issubset(request.data):
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
            )

        try:
            token = ConfirmEmailToken.objects.get(
                user__email=request.data["email"], key=request.data["token"]
            )
            token.user.is_active = True
            token.user.save()
            token.delete()
            return JsonResponse({"Status": True})
        except ObjectDoesNotExist:
            return JsonResponse(
                {"Status": False, "Errors": "Неправильно указан токен или email"}
            )
        except Exception as e:
            logger.error(f"Error confirming email: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при подтверждении email"}
            )


class AccountDetails(APIView):
    """API for user account management."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get current user details."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Update user account details."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if "password" in request.data:
            try:
                validate_password(request.data["password"])
                request.user.set_password(request.data["password"])
            except ValidationError as password_error:
                error_array = [str(item) for item in password_error]
                return JsonResponse(
                    {"Status": False, "Errors": {"password": error_array}}
                )

        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"Status": True})
        else:
            return JsonResponse({"Status": False, "Errors": serializer.errors})


class LoginAccount(APIView):
    """API for user authentication."""

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Authenticate user and return token."""
        if not {"email", "password"}.issubset(request.data):
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
            )

        user = authenticate(
            request, username=request.data["email"], password=request.data["password"]
        )

        if user is not None and user.is_active:
            token, _ = Token.objects.get_or_create(user=user)
            return JsonResponse({"Status": True, "Token": token.key})

        return JsonResponse({"Status": False, "Errors": "Не удалось авторизовать"})


class CategoryView(ListAPIView):
    """API for viewing categories."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """API for viewing active shops."""

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """API for searching products."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get products with filters."""
        query = Q(shop__state=True)

        shop_id = request.query_params.get("shop_id")
        category_id = request.query_params.get("category_id")

        if shop_id:
            query &= Q(shop_id=shop_id)
        if category_id:
            query &= Q(product__category_id=category_id)

        queryset = (
            ProductInfo.objects.filter(query)
            .select_related("shop", "product__category")
            .prefetch_related("product_parameters__parameter")
            .distinct()
        )

        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    """API for shopping basket management."""

    def _get_basket(self, user_id: int) -> Order:
        """Get or create user's basket."""
        basket, _ = Order.objects.get_or_create(user_id=user_id, state="basket")
        return basket

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get basket contents."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        basket = (
            Order.objects.filter(user_id=request.user.id, state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Add items to basket."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        items_string = request.data.get("items")
        if not items_string:
            return JsonResponse({"Status": False, "Errors": "Не указаны товары"})

        try:
            items_dict = load_json(items_string)
        except ValueError:
            return JsonResponse({"Status": False, "Errors": "Неверный формат запроса"})

        basket = self._get_basket(request.user.id)
        objects_created = 0

        for order_item in items_dict:
            order_item["order"] = basket.id
            serializer = OrderItemSerializer(data=order_item)

            if serializer.is_valid():
                try:
                    serializer.save()
                    objects_created += 1
                except IntegrityError as e:
                    return JsonResponse({"Status": False, "Errors": str(e)})
            else:
                return JsonResponse({"Status": False, "Errors": serializer.errors})

        return JsonResponse({"Status": True, "Создано объектов": objects_created})

    def delete(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Remove items from basket."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        items_string = request.data.get("items")
        if not items_string:
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны товары для удаления"}
            )

        items_list = items_string.split(",")
        basket = self._get_basket(request.user.id)

        query = Q()
        valid_items = False

        for item_id in items_list:
            if item_id.isdigit():
                query |= Q(order_id=basket.id, id=int(item_id))
                valid_items = True

        if not valid_items:
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны корректные ID товаров"}
            )

        try:
            deleted_count = OrderItem.objects.filter(query).delete()[0]
            return JsonResponse({"Status": True, "Удалено объектов": deleted_count})
        except Exception as e:
            logger.error(f"Error deleting basket items: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при удалении товаров"}
            )

    def put(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Update item quantities in basket."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        items_string = request.data.get("items")
        if not items_string:
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны товары для обновления"}
            )

        try:
            items_dict = load_json(items_string)
        except ValueError:
            return JsonResponse({"Status": False, "Errors": "Неверный формат запроса"})

        basket = self._get_basket(request.user.id)
        objects_updated = 0

        for order_item in items_dict:
            if isinstance(order_item.get("id"), int) and isinstance(
                order_item.get("quantity"), int
            ):
                objects_updated += OrderItem.objects.filter(
                    order_id=basket.id, id=order_item["id"]
                ).update(quantity=order_item["quantity"])

        return JsonResponse({"Status": True, "Обновлено объектов": objects_updated})


class PartnerUpdate(APIView):
    """API for partner price list updates."""

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Update partner price list with error handling."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if request.user.type != "shop":
            return JsonResponse(
                {"Status": False, "Error": "Только для магазинов"}, status=403
            )

        url = request.data.get("url")
        if not url:
            return JsonResponse({"Status": False, "Error": "Не указан URL"}, status=400)

        try:
            # 1. Validate URL
            ImportService.validate_url(url)

            # 2. Download data with network error handling
            stream = ImportService.download_data(url)

            # 3. Parse YAML data
            data = ImportService.parse_yaml_data(stream)

            # 4. Validate data structure
            ImportService.validate_yaml_structure(data)

            # 5. Create or update shop
            shop, created = Shop.objects.get_or_create(
                name=data["shop"], user_id=request.user.id, defaults={"state": True}
            )

            # 6. Import products with error handling
            import_stats = ImportService.import_products(shop, data)

            response_data = {
                "Status": True,
                "Message": "Прайс-лист успешно обновлен",
                "Details": {
                    "shop": shop.name,
                    "shop_created": created,
                    "import_stats": {
                        "categories_created": import_stats["categories_created"],
                        "categories_updated": import_stats["categories_updated"],
                        "products_created": import_stats["products_created"],
                        "products_updated": import_stats["products_updated"],
                        "total_errors": len(import_stats["errors"]),
                    },
                },
            }

            if import_stats["errors"]:
                response_data["Warnings"] = import_stats["errors"][:10]

            return JsonResponse(response_data)

        except ValidationError as e:
            logger.error(f"Data validation error: {e}")
            return JsonResponse(
                {"Status": False, "Error": f"Ошибка валидации данных: {str(e)}"},
                status=400,
            )
        except Exception as e:
            logger.error(f"Import error: {e}")
            return JsonResponse(
                {"Status": False, "Error": f"Ошибка импорта: {str(e)}"}, status=500
            )


class PartnerState(APIView):
    """API for managing partner state."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get partner shop state."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if request.user.type != "shop":
            return JsonResponse(
                {"Status": False, "Error": "Только для магазинов"}, status=403
            )

        try:
            shop = request.user.shop
            serializer = ShopSerializer(shop)
            return Response(serializer.data)
        except ObjectDoesNotExist:
            return JsonResponse(
                {"Status": False, "Error": "Магазин не найден"}, status=404
            )

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Update partner shop state."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if request.user.type != "shop":
            return JsonResponse(
                {"Status": False, "Error": "Только для магазинов"}, status=403
            )

        state = request.data.get("state")
        if not state:
            return JsonResponse({"Status": False, "Errors": "Не указан статус"})

        try:
            Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
            return JsonResponse({"Status": True})
        except ValueError as e:
            return JsonResponse({"Status": False, "Errors": str(e)})


class PartnerOrders(APIView):
    """API for partner order management."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get orders for partner."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if request.user.type != "shop":
            return JsonResponse(
                {"Status": False, "Error": "Только для магазинов"}, status=403
            )

        orders = (
            Order.objects.filter(
                ordered_items__product_info__shop__user_id=request.user.id
            )
            .exclude(state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .select_related("contact")
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """API for user contact management."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get user contacts."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Create new contact."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        required_fields = {"city", "street", "phone"}
        if not required_fields.issubset(request.data):
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
            )

        request.data._mutable = True
        request.data["user"] = request.user.id

        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"Status": True})
        else:
            return JsonResponse({"Status": False, "Errors": serializer.errors})

    def delete(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Delete contacts."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        items_string = request.data.get("items")
        if not items_string:
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны контакты для удаления"}
            )

        items_list = items_string.split(",")
        query = Q()
        valid_items = False

        for contact_id in items_list:
            if contact_id.isdigit():
                query |= Q(user_id=request.user.id, id=int(contact_id))
                valid_items = True

        if not valid_items:
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны корректные ID контактов"}
            )

        try:
            deleted_count = Contact.objects.filter(query).delete()[0]
            return JsonResponse({"Status": True, "Удалено объектов": deleted_count})
        except Exception as e:
            logger.error(f"Error deleting contacts: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при удалении контактов"}
            )

    def put(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Update contact."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        contact_id = request.data.get("id")
        if not contact_id or not contact_id.isdigit():
            return JsonResponse(
                {"Status": False, "Errors": "Не указан корректный ID контакта"}
            )

        try:
            contact = Contact.objects.get(id=int(contact_id), user_id=request.user.id)
            serializer = ContactSerializer(contact, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({"Status": True})
            else:
                return JsonResponse({"Status": False, "Errors": serializer.errors})

        except ObjectDoesNotExist:
            return JsonResponse({"Status": False, "Errors": "Контакт не найден"})
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при обновлении контакта"}
            )


class OrderView(APIView):
    """API for order management."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get user orders."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        orders = (
            Order.objects.filter(user_id=request.user.id)
            .exclude(state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .select_related("contact")
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args, **kwargs) -> JsonResponse:
        """Create order from basket."""
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"}, status=403
            )

        if not {"id", "contact"}.issubset(request.data):
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
            )

        order_id = request.data["id"]
        if not order_id.isdigit():
            return JsonResponse(
                {"Status": False, "Errors": "Неверный формат ID заказа"}
            )

        try:
            is_updated = Order.objects.filter(
                user_id=request.user.id, id=int(order_id)
            ).update(contact_id=request.data["contact"], state="new")

            if is_updated:
                new_order.send(sender=self.__class__, user_id=request.user.id)
                return JsonResponse({"Status": True})
            else:
                return JsonResponse({"Status": False, "Errors": "Заказ не найден"})

        except IntegrityError as e:
            logger.error(f"Error creating order: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Неправильно указаны аргументы"}
            )
        except Exception as e:
            logger.error(f"Unexpected error creating order: {e}")
            return JsonResponse(
                {"Status": False, "Errors": "Ошибка при создании заказа"}
            )

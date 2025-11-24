import logging
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from yaml import load, Loader, YAMLError
from urllib.parse import urlparse
import time

logger = logging.getLogger(__name__)


class ImportService:
    """
    Сервис для импорта товаров с обработкой ошибок и валидацией данных
    """

    @staticmethod
    def validate_url(url):
        """
        Валидация URL с подробными ошибками
        """
        try:
            validate_url = URLValidator()
            validate_url(url)

            # Дополнительная проверка схемы URL
            parsed_url = urlparse(url)
            if parsed_url.scheme not in ["http", "https"]:
                raise ValidationError("URL должен использовать HTTP или HTTPS протокол")

            return True

        except ValidationError as e:
            logger.error(f"[ERROR] Невалидный URL: {url} - {e}")
            raise

    @staticmethod
    def download_data(url, timeout=30, max_retries=3):
        """
        Загрузка данных с обработкой сетевых ошибок и повторными попытками
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"[INFO] Попытка {attempt + 1} загрузки данных из {url}")

                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; ShopImporter/1.0)"
                    },
                )

                response.raise_for_status()  # Проверка HTTP статуса

                # Проверка размера контента (максимум 10MB)
                content_length = len(response.content)
                if content_length > 10 * 1024 * 1024:
                    raise RequestException(
                        f"Файл слишком большой: {content_length} bytes"
                    )

                # Проверка Content-Type
                content_type = response.headers.get("content-type", "")
                if "yaml" not in content_type and "yml" not in content_type:
                    logger.warning(
                        f"[WARNING] Неожиданный Content-Type: {content_type}"
                    )

                logger.info(
                    f"[SUCCESS] Данные успешно загружены ({content_length} bytes)"
                )
                return response.content

            except Timeout:
                logger.warning(
                    f"[WARNING] Таймаут при загрузке {url} (попытка {attempt + 1})"
                )
                if attempt == max_retries - 1:
                    raise RequestException(
                        f"Превышено время ожидания для {url} после {max_retries} попыток"
                    )

            except ConnectionError:
                logger.warning(
                    f"[WARNING] Ошибка соединения с {url} (попытка {attempt + 1})"
                )
                if attempt == max_retries - 1:
                    raise RequestException(
                        f"Не удалось подключиться к {url} после {max_retries} попыток"
                    )

            except HTTPError as e:
                status_code = e.response.status_code
                logger.error(f"[ERROR] HTTP ошибка {status_code} для {url}")
                if status_code == 404:
                    raise RequestException(f"Файл не найден по указанному URL: {url}")
                elif status_code == 403:
                    raise RequestException(f"Доступ запрещен к {url}")
                elif status_code >= 500:
                    raise RequestException(f"Ошибка сервера {status_code} для {url}")
                else:
                    raise RequestException(
                        f"HTTP ошибка {status_code}: {e.response.reason}"
                    )

            except RequestException as e:
                logger.error(f"[ERROR] Ошибка сети: {e}")
                if attempt == max_retries - 1:
                    raise RequestException(f"Сетевая ошибка: {str(e)}")

            # Пауза между попытками (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2**attempt
                logger.info(
                    f"[INFO] Ожидание {wait_time} секунд перед повторной попыткой"
                )
                time.sleep(wait_time)

        raise RequestException(
            f"Не удалось загрузить данные после {max_retries} попыток"
        )

    @staticmethod
    def validate_yaml_structure(data):
        """
        Валидация структуры YAML данных
        """
        required_keys = ["shop", "categories", "goods"]

        if not isinstance(data, dict):
            raise ValidationError("Данные должны быть в формате словаря")

        # Проверка обязательных ключей
        for key in required_keys:
            if key not in data:
                raise ValidationError(f"Отсутствует обязательный ключ: {key}")

        # Валидация структуры магазина
        if not isinstance(data["shop"], str) or not data["shop"].strip():
            raise ValidationError("Название магазина должно быть непустой строкой")

        # Валидация категорий
        if not isinstance(data["categories"], list):
            raise ValidationError("Категории должны быть списком")

        if len(data["categories"]) == 0:
            raise ValidationError("Список категорий не может быть пустым")

        category_ids = set()
        for i, category in enumerate(data["categories"]):
            if not isinstance(category, dict):
                raise ValidationError(f"Категория #{i} должна быть словарем")

            if "id" not in category or "name" not in category:
                raise ValidationError(f"Категория #{i} должна содержать id и name")

            # Проверка уникальности ID категорий
            if category["id"] in category_ids:
                raise ValidationError(f'Дублирующийся ID категории: {category["id"]}')
            category_ids.add(category["id"])

        # Валидация товаров
        if not isinstance(data["goods"], list):
            raise ValidationError("Товары должны быть списком")

        if len(data["goods"]) == 0:
            raise ValidationError("Список товаров не может быть пустым")

        required_goods_fields = ["id", "name", "category", "price", "quantity"]

        product_ids = set()
        for i, product in enumerate(data["goods"]):
            if not isinstance(product, dict):
                raise ValidationError(f"Товар #{i} должен быть словарем")

            for field in required_goods_fields:
                if field not in product:
                    raise ValidationError(f"Товар #{i} отсутствует поле: {field}")

            # Проверка уникальности ID товаров
            if product["id"] in product_ids:
                raise ValidationError(f'Дублирующийся ID товара: {product["id"]}')
            product_ids.add(product["id"])

            # Валидация типов данных
            if not isinstance(product["id"], int) or product["id"] <= 0:
                raise ValidationError(f"Товар #{i} id должен быть положительным числом")

            if not isinstance(product["price"], (int, float)) or product["price"] < 0:
                raise ValidationError(
                    f"Товар #{i} price должен быть неотрицательным числом"
                )

            if not isinstance(product["quantity"], int) or product["quantity"] < 0:
                raise ValidationError(
                    f"Товар #{i} quantity должен быть неотрицательным целым числом"
                )

            # Проверка существования категории
            if product["category"] not in category_ids:
                raise ValidationError(
                    f'Товар #{i} ссылается на несуществующую категорию: {product["category"]}'
                )

        logger.info(
            f'[SUCCESS] Структура данных валидна: {len(data["categories"])} категорий, {len(data["goods"])} товаров'
        )
        return True

    @staticmethod
    def parse_yaml_data(stream):
        """
        Парсинг YAML данных с обработкой ошибок
        """
        try:
            data = load(stream, Loader=Loader)
            return data
        except YAMLError as e:
            logger.error(f"[ERROR] Ошибка парсинга YAML: {e}")
            raise ValidationError(f"Ошибка формата YAML: {str(e)}")
        except Exception as e:
            logger.error(f"[ERROR] Неожиданная ошибка при парсинге: {e}")
            raise ValidationError(f"Ошибка обработки данных: {str(e)}")

    @staticmethod
    def import_products(shop, data):
        """
        Импорт товаров в базу данных с обработкой ошибок
        """
        stats = {
            "categories_created": 0,
            "categories_updated": 0,
            "products_created": 0,
            "products_updated": 0,
            "errors": [],
        }

        try:
            from backend.models import (
                Category,
                Product,
                ProductInfo,
                Parameter,
                ProductParameter,
            )

            # Обработка категорий
            category_map = {}
            for category_data in data["categories"]:
                try:
                    category, created = Category.objects.get_or_create(
                        id=category_data["id"], defaults={"name": category_data["name"]}
                    )

                    if not created:
                        # Обновляем название категории если оно изменилось
                        if category.name != category_data["name"]:
                            category.name = category_data["name"]
                            category.save()
                            stats["categories_updated"] += 1
                    else:
                        stats["categories_created"] += 1

                    # Добавляем магазин к категории
                    category.shops.add(shop)
                    category.save()
                    category_map[category_data["id"]] = category

                    logger.debug(f"[DEBUG] Обработана категория: {category.name}")

                except Exception as e:
                    error_msg = f'Ошибка обработки категории {category_data.get("id", "unknown")}: {str(e)}'
                    logger.error(f"[ERROR] {error_msg}")
                    stats["errors"].append(error_msg)

            # Удаляем старые данные товаров этого магазина
            deleted_count = ProductInfo.objects.filter(shop=shop).delete()[0]
            logger.info(f"[INFO] Удалено старых записей: {deleted_count}")

            # Обработка товаров
            for product_data in data["goods"]:
                try:
                    category = category_map.get(product_data["category"])
                    if not category:
                        raise ValueError(
                            f'Категория {product_data["category"]} не найдена'
                        )

                    # Создаем или обновляем продукт
                    product, created = Product.objects.get_or_create(
                        name=product_data["name"],
                        category=category,
                        defaults={"name": product_data["name"]},
                    )

                    if created:
                        stats["products_created"] += 1
                        logger.debug(f"[DEBUG] Создан продукт: {product.name}")
                    else:
                        stats["products_updated"] += 1
                        logger.debug(f"[DEBUG] Обновлен продукт: {product.name}")

                    # Создаем информацию о продукте
                    product_info = ProductInfo.objects.create(
                        product=product,
                        external_id=product_data["id"],
                        model=product_data.get("model", ""),
                        price=product_data["price"],
                        price_rrc=product_data.get("price_rrc", product_data["price"]),
                        quantity=product_data["quantity"],
                        shop=shop,
                    )

                    # Обработка параметров
                    parameters = product_data.get("parameters", {})
                    for param_name, param_value in parameters.items():
                        try:
                            if not param_name.strip():
                                continue

                            parameter, _ = Parameter.objects.get_or_create(
                                name=param_name.strip()
                            )
                            ProductParameter.objects.create(
                                product_info=product_info,
                                parameter=parameter,
                                # Ограничение длины
                                value=str(param_value)[:100],
                            )
                        except Exception as e:
                            error_msg = f'Ошибка параметра "{param_name}" для товара {product_data["id"]}: {str(e)}'
                            logger.warning(f"[WARNING] {error_msg}")
                            stats["errors"].append(error_msg)

                except Exception as e:
                    error_msg = f'Ошибка обработки товара {product_data.get("id", "unknown")}: {str(e)}'
                    logger.error(f"[ERROR] {error_msg}")
                    stats["errors"].append(error_msg)

            logger.info(f"[SUCCESS] Импорт завершен: {stats}")
            return stats

        except Exception as e:
            logger.error(f"[ERROR] Критическая ошибка импорта: {e}")
            stats["errors"].append(f"Критическая ошибка: {str(e)}")
            return stats

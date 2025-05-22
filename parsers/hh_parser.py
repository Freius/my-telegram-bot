import requests
from fake_useragent import UserAgent
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

def get_hh_vacancies(query: str, area_id: int) -> list:
    """Получение вакансий с HeadHunter API с улучшенным поиском"""
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'application/json'
    }
    
    # Упрощаем запрос, чтобы он точно работал с search_field=name
    clean_query = query.replace('AND', '').replace('(', '').replace(')', '')

    params = {
        'text': clean_query.strip(),
        'area': area_id,
        'per_page': 20,
        'search_field': 'name',
        'order_by': 'publication_time',
        'period': 30
    }

    try:
        response = requests.get('https://api.hh.ru/vacancies ', headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        vacancies = data.get('items', [])

        # Сортировка по дате публикации (самые свежие впереди)
        vacancies.sort(key=lambda v: v.get('published_at', ''), reverse=True)

        logger.info(f"Найдено {len(vacancies)} вакансий для запроса '{query}' в регионе {area_id}")
        return vacancies[:20]

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API HH: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)

    return []
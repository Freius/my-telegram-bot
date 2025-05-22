import requests
from fake_useragent import UserAgent
import logging
import time

logger = logging.getLogger(__name__)

def get_hh_vacancies(query: str, area_id: int) -> list:
    """Получение всех вакансий с HeadHunter API по компании и региону"""
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    all_vacancies = []
    page = 0
    per_page = 100  # максимум допустимый HH API
    max_pages = 20  # ограничим до 2000 вакансий, чтобы избежать чрезмерной загрузки

    while page < max_pages:
        params = {
            'text': query,
            'area': area_id,
            'per_page': per_page,
            'page': page,
            'search_field': 'company_name',
            'order_by': 'publication_time',
            'period': 30
        }

        try:
            response = requests.get('https://api.hh.ru/vacancies', headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            vacancies = data.get('items', [])

            if not vacancies:
                break

            all_vacancies.extend(vacancies)

            if page >= data.get('pages', 0) - 1:
                break  # достигли последней страницы

            page += 1
            time.sleep(0.1)  # чтобы не перегрузить API
        except Exception as e:
            logger.error(f"Ошибка при запросе вакансий (страница {page}): {e}")
            break

    logger.info(f"Найдено всего {len(all_vacancies)} вакансий для '{query}' в регионе {area_id}")
    return all_vacancies

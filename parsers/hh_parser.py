import requests
from fake_useragent import UserAgent
import logging

logger = logging.getLogger(__name__)

def get_hh_vacancies(query: str, area_id: int) -> list:
    """Получение вакансий с HeadHunter API"""
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    params = {
        'text': query,
        'area': area_id,
        'per_page': 20,  # Увеличили количество результатов
        'search_field': 'company_name',  # Ищем в названии компании
        'order_by': 'publication_time',  # Сортировка по дате публикации
        'period': 30  # Вакансии за последние 30 дней
    }
    
    try:
        response = requests.get('https://api.hh.ru/vacancies', headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        vacancies = data.get('items', [])
        
        logger.info(f"Найдено {len(vacancies)} вакансий для запроса '{query}' в регионе {area_id}")
        return vacancies
        
    except Exception as e:
        logger.error(f"Ошибка при запросе вакансий: {e}")
        return []
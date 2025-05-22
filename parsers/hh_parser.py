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
    
    params = {
        'text': query,
        'area': area_id,
        'per_page': 50,  # Увеличили количество результатов
        'search_field': 'name',  # Ищем в названии вакансии
        'order_by': 'publication_time',
        'period': 30
    }
    
    try:
        response = requests.get('https://api.hh.ru/vacancies', headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        vacancies = data.get('items', [])
        
        logger.info(f"Найдено {len(vacancies)} вакансий для запроса '{query}' в регионе {area_id}")
        return vacancies
        
    except Exception as e:
        logger.error(f"Ошибка при запросе вакансий: {e}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API HH: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
    
    # Сортируем вакансии по дате публикации (новые сначала)
    all_vacancies.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    
    logger.info(f"Итого найдено {len(all_vacancies)} уникальных вакансий для запроса '{query}'")
    return all_vacancies[:20]  # Возвращаем максимум 20 вакансий
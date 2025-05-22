import requests
from fake_useragent import UserAgent
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

def get_hh_vacancies(query: str, area_id: int) -> list:
    """Получение вакансий с HeadHunter API"""
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'application/json',
        'Host': 'api.hh.ru'
    }
    
    # Параметры для разных стратегий поиска
    search_strategies = [
        # 1. Точный поиск по названию компании и должности
        {
            'text': f'"{query}"',  # Точное совпадение
            'search_field': 'company_name',
            'per_page': 20,
            'order_by': 'publication_time',
            'period': 30
        },
        # 2. Поиск по названию компании (без кавычек)
        {
            'text': query,
            'search_field': 'company_name',
            'per_page': 20,
            'order_by': 'publication_time',
            'period': 30
        },
        # 3. Общий поиск (по всему тексту вакансии)
        {
            'text': query,
            'per_page': 20,
            'order_by': 'publication_time',
            'period': 30
        }
    ]
    
    all_vacancies = []
    seen_ids = set()  # Для исключения дубликатов
    
    try:
        for strategy in search_strategies:
            strategy['area'] = area_id
            logger.info(f"Пробуем стратегию поиска: {strategy}")
            
            response = requests.get(
                'https://api.hh.ru/vacancies',
                headers=headers,
                params=strategy,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            vacancies = data.get('items', [])
            
            # Добавляем только уникальные вакансии
            for vacancy in vacancies:
                if vacancy['id'] not in seen_ids:
                    seen_ids.add(vacancy['id'])
                    all_vacancies.append(vacancy)
            
            logger.info(f"Найдено {len(vacancies)} вакансий по этой стратегии")
            
            # Если нашли достаточно результатов, прекращаем поиск
            if len(all_vacancies) >= 10:
                break
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API HH: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
    
    # Сортируем вакансии по дате публикации (новые сначала)
    all_vacancies.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    
    logger.info(f"Итого найдено {len(all_vacancies)} уникальных вакансий для запроса '{query}'")
    return all_vacancies[:20]  # Возвращаем максимум 20 вакансий
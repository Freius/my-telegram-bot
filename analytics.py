def analyze_vacancy(vacancy: dict, sber_benchmark: dict = None) -> dict:
    """Анализ одной вакансии с учетом эталона Сбербанка"""
    # Если эталон не передан, создаем пустой словарь
    if sber_benchmark is None:
        sber_benchmark = {
            "salary_avg": 0,
            "benefits": [],
            "tech_stack": []
        }

    salary = vacancy.get("salary", {})
    description = str(vacancy.get("description", "")).lower()
    salary_from = salary.get('from', 0) or 0
    salary_to = salary.get('to', 0) or 0

    # Сравнение с Сбером
    sber_salary = sber_benchmark.get("salary_avg", 0)
    salary_comparison = (
        "Лучше" if salary_from > sber_salary else
        "Хуже" if salary_from < sber_salary else
        "Аналогично"
    )

    return {
        "Название банка": vacancy.get("employer", {}).get("name", "Не указан"),
        "Должность": vacancy.get("name", "Без названия"),
        "Зарплата": f"{salary_from}-{salary_to} {salary.get('currency', '')}".strip(),
        "Преимущества": "Гибкий график" if "гибкий" in description else "Стандартные условия",
        "Недостатки": "Высокая нагрузка" if "нагрузка" in description else "Нет",
        "Соцпакет": "Да" if any(benefit in description for benefit in sber_benchmark["benefits"]) else "Да, смотри по ссылке в условиях",
        "Технологичность": "Высокая" if any(tech in description for tech in sber_benchmark["tech_stack"]) else "Средняя",
        "Сравнение с Сбером": salary_comparison
    }

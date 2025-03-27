def generate_report(vacancies: list) -> str:
    """Генерация читаемого отчета из списка вакансий"""
    report = []
    for vacancy in vacancies[:3]:  # Берем первые 3 вакансии
        data = analyze_vacancy(vacancy)
        if data:
            report.append(
                f"🏦 Банк: {data['bank']}\n"
                f"📌 Должность: {data['title']}\n"
                f"💰 Зарплата: {data['salary']}\n"
                f"🌍 Город: {data['city']}\n"
                f"🔗 Ссылка: {data['url']}\n"
            )
    return "\n".join(report) if report else "Нет данных для отображения"

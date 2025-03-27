from bs4 import BeautifulSoup
import requests

def parse_alfa_vacancies() -> list[dict]:
    """Парсит вакансии с сайта Альфа-Банка."""
    url = "https://hr.alfabank.ru/vacancies"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    vacancies = []
    for card in soup.find_all("div", class_="vacancy-card"):
        title = card.find("h3").text.strip()
        link = card.find("a")["href"]
        salary = card.find("div", class_="salary").text if card.find("div", class_="salary") else "Не указана"
        
        vacancies.append({
            "Банк": "Альфа-Банк",
            "Должность": title,
            "Зарплата": salary,
            "Ссылка": f"https://hr.alfabank.ru{link}",
        })
    
    return vacancies

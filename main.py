import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from config import API_TOKEN
from parsers.hh_parser import get_hh_vacancies
from analytics import analyze_vacancy

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройки банков
BANK_MAPPING = {
    "alfa": "Альфа-Банк",
    "vtb": "ВТБ",
    "rshb": "Россельхозбанк",
    "gazprom": "Газпромбанк", 
    "tinkoff": "Тинькофф"
}

# Настройки городов (ID из API HeadHunter)
CITIES = {
    "Великий Новгород": 67,
    "Калининград": 41,
    "Санкт-Петербург": 2,
    "Архангельск": 14,
    "Вологда": 25,
    "Псков": 75,
    "Коми": 1041,
    "Карелия": 1077,
    "Лен. обл.": 145,
    "Мурманск": 64
}

# Популярные должности
POSITIONS = {
    "Руководитель": "Руководитель",
    "Клиентский менеджер": "Клиентский менеджер",
    "Менеджер": "Менеджер",
    "Любая": "Любая должность"
}

DEFAULT_CITY = "Великий Новгород"
DEFAULT_CITY_ID = CITIES[DEFAULT_CITY]

SBER_BENCHMARK = {
    "salary_avg": 120000,
    "benefits": ["медицинская страховка", "обучение", "ДМС"],
    "tech_stack": ["Python", "SQL", "Kafka"]
}

# Хранение выбора пользователей
user_data = {}

def generate_report(vacancies: list, bank_name: str, city: str, position: str = None) -> str:
    """Генерирует отчет по вакансиям с указанием города и должности"""
    if not vacancies:
        position_text = f" по должности '{position}'" if position and position != "Любая должность" else ""
        return (f"😕 В {city} не найдено вакансий для {bank_name}{position_text}\n"
                "Попробуйте изменить параметры поиска или выбрать другую должность/город")
    
    report = [f"📊 Отчет по вакансиям {bank_name} ({city})"]
    if position and position != "Любая должность":
        report.append(f"по должности '{position}':\n")
    else:
        report.append(":\n")
    
    for i, vacancy in enumerate(vacancies[:5], 1):
        try:
            analyzed = analyze_vacancy(vacancy, SBER_BENCHMARK)
            salary = format_salary(vacancy.get('salary'))
            salary_comparison = ""
            
            if vacancy.get('salary') and vacancy['salary'].get('from'):
                salary_diff = vacancy['salary']['from'] - SBER_BENCHMARK['salary_avg']
                if salary_diff > 0:
                    salary_comparison = f"(🔺 )"
                elif salary_diff < 0:
                    salary_comparison = f"(🔻 )"
                else:
                    salary_comparison = "(≈ как в Сбере)"
            
            report.append(
                f"\n{i}. 🏦 {analyzed.get('Название банка', vacancy.get('employer', {}).get('name', 'Не указано'))}\n"
                f"   📌 Должность: {vacancy.get('name', 'Не указана')}\n"
                f"   💰 Зарплата: {salary} {salary_comparison}\n"
                f"   ✔️ Преимущества: {analyzed.get('Преимущества', 'Нет')}\n"
                f"   🎁 Соцпакет: {analyzed.get('Соцпакет', 'см. в условиях')}\n"
                f"   💻 Технологичность: {analyzed.get('Технологичность', 'Средняя')}\n"
                f"   🔍 Сравнение с Сбером: {analyzed.get('Сравнение с Сбером', 'Нет данных')}\n"
                f"   🔗 Ссылка: {vacancy.get('alternate_url', 'нет')}"
            )
        except Exception as e:
            logger.error(f"Ошибка анализа вакансии: {e}")
            continue
            
    return "\n".join(report)

def format_salary(salary: dict) -> str:
    """Форматирование информации о зарплате"""
    if not salary:
        return "Не указана"
    from_s = f"от {salary['from']}" if salary.get('from') else ""
    to_s = f"до {salary['to']}" if salary.get('to') else ""
    currency = salary.get('currency', '').upper()
    return f"{from_s} {to_s} {currency}".strip()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура с банками"""
    builder = ReplyKeyboardBuilder()
    
    buttons = [
        "🏦 Альфа-Банк",
        "🏛 ВТБ",
        "🌾 Россельхозбанк",
        "⛽ Газпромбанк",
        "💳 Тинькофф",
        "🌆 Сменить город",
        "💼 Выбрать должность"
    ]
    
    for text in buttons:
        builder.add(KeyboardButton(text=text))
    
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_city_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора города"""
    builder = ReplyKeyboardBuilder()
    
    for city in CITIES.keys():
        builder.add(KeyboardButton(text=city))
    
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_position_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для выбора должности"""
    builder = InlineKeyboardBuilder()
    
    for position in POSITIONS.values():
        builder.add(InlineKeyboardButton(
            text=position,
            callback_data=f"position_{position}")
        )
    
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("start"))
async def start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_data[user_id] = {"city": DEFAULT_CITY, "position": "Любая должность"}
    
    await message.answer(
        f"🌆 Текущий город: {DEFAULT_CITY}\n"
        "🔍 Выберите банк для анализа вакансий:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🌆 Сменить город")
async def change_city(message: types.Message):
    """Обработчик смены города"""
    await message.answer(
        "Выберите город:",
        reply_markup=get_city_keyboard()
    )

@dp.message(F.text == "💼 Выбрать должность")
async def select_position(message: types.Message):
    """Обработчик выбора должности"""
    await message.answer(
        "Выберите должность:",
        reply_markup=get_position_keyboard()
    )

@dp.callback_query(F.data.startswith("position_"))
async def process_position(callback: types.CallbackQuery):
    """Обработка выбора должности"""
    user_id = callback.from_user.id
    position = callback.data.split("_")[1]
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]["position"] = position
    await callback.message.answer(
        f"💼 Выбрана должность: {position}\n"
        "Теперь выберите банк для анализа:",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.message(F.text.in_(CITIES.keys()))
async def set_city(message: types.Message):
    """Установка выбранного города"""
    user_id = message.from_user.id
    city = message.text
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]["city"] = city
    
    await message.answer(
        f"🌆 Город изменен на: {city}\n"
        "Теперь выберите банк для анализа:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_(["🏦 Альфа-Банк", "🏛 ВТБ", "🌾 Россельхозбанк", "⛽ Газпромбанк", "💳 Тинькофф"]))
async def handle_bank_button(message: types.Message):
    """Обработка нажатий кнопок банков"""
    bank_mapping = {
        "🏦 Альфа-Банк": "Альфа-Банк",
        "🏛 ВТБ": "ВТБ",
        "🌾 Россельхозбанк": "Россельхозбанк",
        "⛽ Газпромбанк": "Газпромбанк",
        "💳 Тинькофф": "Тинькофф"
    }
    
    user_id = message.from_user.id
    city = user_data.get(user_id, {}).get("city", DEFAULT_CITY)
    city_id = CITIES.get(city, DEFAULT_CITY_ID)
    bank_name = bank_mapping[message.text]
    position = user_data.get(user_id, {}).get("position", "Любая должность")
    
    try:
        logger.info(f"Запрос анализа для {bank_name} в городе {city} (ID: {city_id}), должность: {position}")
        await message.answer(f"🔍 Ищу вакансии {bank_name} в {city}{f' по должности {position}' if position != 'Любая должность' else ''}...")
        
        # Формируем поисковый запрос
        search_query = bank_name
        if position and position != "Любая должность":
            search_query = f"{bank_name} {position}"
        
        vacancies = get_hh_vacancies(search_query, city_id)
        
        report = generate_report(vacancies, bank_name, city, position)
        await message.answer(
            report,
            reply_markup=get_main_keyboard(),
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка в обработке банка {bank_name}: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке запроса",
            reply_markup=get_main_keyboard()
        )

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация бота
API_TOKEN = "YOUR_BOT_API_TOKEN"  # Заменить на свой токен
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройки банков
BANK_MAPPING = {
    "Альфа-Банк": "Альфа-Банк",
    "ВТБ": "ВТБ",
    "Россельхозбанк": "Россельхозбанк",
    "Газпромбанк": "Газпромбанк",
    "Тинькофф": "Тинькофф"
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
    "Менеджер": "Менеджер",
    "Руководитель": "Руководитель",
    "Специалист": "Специалист",
    "Заместитель": "Заместитель",
    "Любая": "Любая должность"
}

# Синонимы для поиска должностей
POSITION_SYNONYMS = {
    "Менеджер": [
        "менеджер", "manager", "менеджер по", "менеджер проекта",
        "менеджер продукта", "менеджер по продажам", "product manager", "project manager"
    ],
    "Руководитель": [
        "руководитель", "head", "chief", "руководитель отдела", "руководитель направления",
        "руководитель проекта", "team lead"
    ],
    "Специалист": [
        "специалист", "specialist", "эксперт", "ведущий специалист", "старший специалист",
        "главный специалист", "analyst"
    ],
    "Заместитель": [
        "заместитель", "зам.", "deputy", "заместитель руководителя", "заместитель директора",
        "заместитель начальника", "зам. руководителя"
    ]
}

DEFAULT_CITY = "Великий Новгород"
DEFAULT_CITY_ID = CITIES[DEFAULT_CITY]

# Бенчмарк сравнения с Сбером
SBER_BENCHMARK = {
    "salary_avg": 120000,
    "benefits": ["медицинская страховка", "обучение", "ДМС"],
    "tech_stack": ["Python", "SQL", "Kafka"]
}

# Хранение выбора пользователей
user_data = {}

# Импорты после определения SBER_BENCHMARK
from parsers.hh_parser import get_hh_vacancies
from analytics import analyze_vacancy


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
                    salary_comparison = "(🔺 выше)"
                elif salary_diff < 0:
                    salary_comparison = "(🔻 ниже)"
                else:
                    salary_comparison = "(≈ как в Сбере)"

            report.append(
                f"\n{i}. 🏦 {analyzed.get('Название банка', vacancy.get('employer', {}).get('name', 'Не указано'))}"
                f"\n   📌 Должность: {vacancy.get('name', 'Не указана')}"
                f"\n   💰 Зарплата: {salary} {salary_comparison}"
                f"\n   ✔️ Преимущества: {analyzed.get('Преимущества', 'Нет данных')}"
                f"\n   🎁 Соцпакет: {analyzed.get('Соцпакет', 'см. в условиях')}"
                f"\n   💻 Технологичность: {analyzed.get('Технологичность', 'Средняя')}"
                f"\n   🔍 Сравнение с Сбером: {analyzed.get('Сравнение с Сбером', 'Нет данных')}"
                f"\n   🔗 Ссылка: {vacancy.get('alternate_url', 'нет')}"
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
        f"🌆 Город изменён на: {city}\n"
        "Теперь выберите банк для анализа:",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text.in_(["🏦 Альфа-Банк", "🏛 ВТБ", "🌾 Россельхозбанк", "⛽ Газпромбанк", "💳 Тинькофф"]))
async def handle_bank_button(message: types.Message):
    """Обработка нажатий кнопок банков с улучшенным поиском по должностям"""
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
        logger.info(f"Поиск вакансий: {bank_name} в {city}, должность: {position}")
        await message.answer(f"🔍 Ищу вакансии {bank_name} в {city}{f' по должности {position}' if position != 'Любая должность' else ''}...")

        if position == "Любая должность":
            search_query = f'"{bank_name}"'
        else:
            synonyms = POSITION_SYNONYMS.get(position, [position.lower()])
            synonyms_query = " OR ".join([f'"{s}"' for s in synonyms])
            search_query = f'"{bank_name}" AND ({synonyms_query})'

        vacancies = get_hh_vacancies(search_query, city_id)

        if position != "Любая должность":
            synonyms_lower = [s.lower() for s in synonyms]
            vacancies = [
                v for v in vacancies
                if any(syn in v.get('name', '').lower() for syn in synonyms_lower)
            ]

        report = generate_report(vacancies, bank_name, city, position)
        await message.answer(
            report,
            reply_markup=get_main_keyboard(),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка поиска вакансий: {str(e)}", exc_info=True)
        await message.answer(
            "⚠️ Произошла ошибка при поиске вакансий. Попробуйте изменить параметры.",
            reply_markup=get_main_keyboard()
        )


async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
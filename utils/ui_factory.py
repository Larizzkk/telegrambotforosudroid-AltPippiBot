# Путь: utils/ui_factory.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

class UIFactory:
    TEXTS = {
        'en': {
            'start': 'Hello! I am ready to work. Send /help to see what I can do.',
            'help': (
                "Available commands:\n"
                "/bind <name> - link your account\n"
                "/u <name> - profile stats\n"
                "/prpic <name> - profile card (image)\n"
                "/topplays <name> - top plays\n"
                "/sr <query> - search beatmaps\n"
                "/pp <id> - calculate PP\n"
                "/roll [min max] - random number\n"
                "/yn - yes or no"
            ),
            'bind_ok': 'Account successfully linked: ',
            'profile_err': 'I could not find this player.',
            'map_info': 'Beatmap: {title}\nStars: {sr}*\nBPM: {bpm}',
            'pp_res': 'Result: {pp}pp (Acc: {acc}%, Mods: {mods})',
            'loading': 'Getting data...',
            'error': 'Error: {error}',
            'not_found': 'Not found',
            'download_start': 'Starting download...',
            'downloading': 'Downloading map {bid} ...',
            'download_ready': 'Almost done...',
            'download_error': 'Send error: {error}',
            'download_failed': 'All mirrors unavailable or file too large.',
            'recommendations': 'Recommendations'
        },
        'ru': {
            'start': 'Привет! Я готов к работе. Отправь /help, чтобы посмотреть список команд.',
            'help': (
                "Доступные команды:\n"
                "/bind <имя> - привязать аккаунт\n"
                "/u <имя> - статистика профиля\n"
                "/prpic <имя> - карточка профиля (изображение)\n"
                "/topplays <имя> - топ игры\n"
                "/sr <запрос> - поиск карт\n"
                "/roll [мин макс] - случайное число\n"
                "/yn - да или нет\n"
            ),
            'bind_ok': 'Аккаунт успешно привязан: ',
            'profile_err': 'Я не смог найти такого игрока.',
            'map_info': 'Карта: {title}\nЗвезды: {sr}*\nBPM: {bpm}',
            'pp_res': 'Итог: {pp}pp (Точность: {acc}%, Моды: {mods})',
            'loading': 'Получаю данные...',
            'error': 'Ошибка: {error}',
            'not_found': 'Не найдено',
            'download_start': 'Начинаю загрузку...',
            'downloading': 'Скачиваю карту {bid} ...',
            'download_ready': 'Секунду...',
            'download_error': 'Ошибка отправки: {error}',
            'download_failed': 'Все зеркала недоступны или файл слишком большой.',
            'recommendations': 'Рекомендации'
        }
    }

    @staticmethod
    def get_text(key, lang, **kwargs):
        lang_dict = UIFactory.TEXTS.get(lang, UIFactory.TEXTS['en'])
        return lang_dict.get(key, key).format(**kwargs)

    @staticmethod
    def top_plays_kb(uid, page=0):
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text="Recommendations", callback_data=f"tp_{uid}_{page-1}"),
            types.InlineKeyboardButton(text=">", callback_data=f"tp_{uid}_{page+1}")
        )
        return kb.as_markup()
    
    @staticmethod
    def download_kb(bid: int):
        kb = InlineKeyboardBuilder()
        # Кнопка для скачивания самим ботом
        kb.row(types.InlineKeyboardButton(text="Скачать файлом в Telegram", callback_data=f"dlraw_{bid}"))
        # Оставляем одну прямую ссылку на всякий случай (Nerinyan)
        kb.row(types.InlineKeyboardButton(text="Открыть в браузере (Nerinyan)", url=f"https://api.nerinyan.moe/d/{bid}"))
        return kb.as_markup()

    @staticmethod
    def search_pagination_kb(query: str, page: int, current_page_ids: list):
        kb = InlineKeyboardBuilder()
        
        # Кнопки скачивания для текущих карт на странице
        for i, bid in enumerate(current_page_ids, 1 + page*5):
            kb.row(types.InlineKeyboardButton(text=f"Скачать #{i}", callback_data=f"dlraw_{bid}"))
        
        # Кнопки навигации
        nav_btns = []
        short_query = query[:20]
        if page > 0:
            nav_btns.append(types.InlineKeyboardButton(text="Назад", callback_data=f"sr_{short_query}_{page-1}"))
        nav_btns.append(types.InlineKeyboardButton(text="Вперед", callback_data=f"sr_{short_query}_{page+1}"))
        kb.row(*nav_btns)
        
        return kb.as_markup()
    
    @staticmethod
    def recommendation_kb(username: str):
        kb = InlineKeyboardBuilder()

        kb.add(
            InlineKeyboardButton(
                text="Recommendations",
                callback_data=f"recommend:{username}"
            )
        )

        return kb.as_markup()

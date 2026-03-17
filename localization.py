class Localization:
    """Система локализации для бота"""

    _texts = {
        'ru': {
            'start': "Привет! Я бот для osu!droid. Используй /help для списка команд.",
            'help': "**Помощь по командам**\n\n",
            'loading': "Загружаю",
            'map_info': "информацию о карте",
            'map_not_found': "Карта не найдена в API droid.",
            'user_not_found': "Пользователь не найден.",
            'error_loading': "Ошибка при загрузке",
            'bind_success': "Аккаунт успешно привязан!",
            'unbind_success': "Аккаунт отвязан!",
            'lang_changed': "Язык изменен на русский.",
            'invalid_lang': "Неверный язык. Используйте /lang ru или /lang en",
            'no_username': "Введите никнейм или привяжите аккаунт через /bind.",
            'profile_error': "Ошибка получения профиля",
            'recent_error': "Ошибка при загрузке последних игр",
            'download_started': "Начинаю загрузку...",
            'download_complete': "Файл успешно скачан",
            'timeout_error': "Таймаут при скачивании",
            'mirror_error': "Ошибка зеркала",
            'invalid_data': "Неверные данные",
            'no_more_scores': "Больше нет последних игр.",
            'pagination_error': "Ошибка при загрузке страницы",
            'previous': "Предыдущий",
            'next': "Следующий",
            'page': "Страница",
            'bind_required': "Использование: /prpic <никнейм> или сначала привяжите аккаунт",
            'difficulty_required': "Для карты сета требуется указать конкретную сложность.\n\nПример: https://osu.ppy.sh/beatmapsets/{set_id}#osu/123456",
            'sr_usage': "Использование: /sr <запрос> [фильтры]\n\nФильтры:\nmode:osu/taiko/catch/mania\nstatus:ranked/qualified/loved/pending/wip/graveyard\ngenre:video/anime/rock/pop/other/novelty/hip/electronic/metal/classical/folk/jazz\nlang:english/chinese/french/german/italian/japanese/korean/spanish/swedish/russian/polish/instrumental\nexplicit:show/hide\nvideo:yes/no\nstoryboard:yes/no\nplayed:yes/no",
            'sr_searching': "Ищу карты по запросу: {query}...",
            'sr_unavailable': "Поиск по '{query}' временно недоступен. Попробуйте использовать:\n\n• Поиск на сайте [osu.ppy.sh](https://osu.ppy.sh/beatmapsets?q={query})\n• Команду /map с конкретным ID карты",
            'sr_no_results': "По запросу '{query}' карты не найдены. Попробуйте другой запрос или другие фильтры.",
            'sr_timeout': "Превышено время ожидания при поиске. Попробуйте позже.",
            'sr_error': "Ошибка при поиске по запросу '{query}'. Попробуйте:\n\n• Поиск на сайте [osu.ppy.sh](https://osu.ppy.sh/beatmapsets?q={query})\n• Использовать /map с конкретным ID карты"
        },
        'en': {
            'start': "Hello! I'm an osu!droid bot. Use /help for command list.",
            'help': "**Command Help**\n\n",
            'loading': "Loading",
            'map_info': "map information",
            'map_not_found': "Beatmap not found in droid API.",
            'user_not_found': "User not found.",
            'error_loading': "Error loading",
            'bind_success': "Account successfully bound!",
            'unbind_success': "Account unbound!",
            'lang_changed': "Language changed to English.",
            'invalid_lang': "Invalid language. Use /lang ru or /lang en",
            'no_username': "Enter username or bind account via /bind.",
            'profile_error': "Profile fetch error",
            'recent_error': "Error loading recent plays",
            'download_started': "Starting download...",
            'download_complete': "File downloaded successfully",
            'timeout_error': "Download timeout",
            'mirror_error': "Mirror error",
            'invalid_data': "Invalid data",
            'no_more_scores': "No more recent plays.",
            'pagination_error': "Page load error",
            'previous': "Previous",
            'next': "Next",
            'page': "Page",
            'bind_required': "Usage: /prpic <username> or bind account first",
            'difficulty_required': "Beatmapset requires specific difficulty.\n\nExample: https://osu.ppy.sh/beatmapsets/{set_id}#osu/123456",
            'sr_usage': "Usage: /sr <query> [filters]\n\nFilters:\nmode:osu/taiko/catch/mania\nstatus:ranked/qualified/loved/pending/wip/graveyard\ngenre:video/anime/rock/pop/other/novelty/hip/electronic/metal/classical/folk/jazz\nlang:english/chinese/french/german/italian/japanese/korean/spanish/swedish/russian/polish/instrumental\nexplicit:show/hide\nvideo:yes/no\nstoryboard:yes/no\nplayed:yes/no",
            'sr_searching': "Searching for maps with query: {query}...",
            'sr_unavailable': "Search for '{query}' temporarily unavailable. Try:\n\n• Search on [osu.ppy.sh](https://osu.ppy.sh/beatmapsets?q={query})\n• Use /map with specific beatmap ID",
            'sr_no_results': "No maps found for query '{query}'. Try different query or filters.",
            'sr_timeout': "Search timeout. Try again later.",
            'sr_error': "Error searching for '{query}'. Try:\n\n• Search on [osu.ppy.sh](https://osu.ppy.sh/beatmapsets?q={query})\n• Use /map with specific beatmap ID"
        }
    }

    @staticmethod
    def get_text(key: str, lang: str = 'en') -> str:
        """Получить текст по ключу для указанного языка"""
        if lang not in Localization._texts:
            lang = 'en'
        return Localization._texts[lang].get(key, f"[{key}]")

    @staticmethod
    def get_all_texts(lang: str = 'en') -> dict:
        """Получить все тексты для языка"""
        if lang not in Localization._texts:
            lang = 'en'
        return Localization._texts[lang]

import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import Counter
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO

class GraphicsGenerator:
    # Online resources URLs
    FLAGS_BASE_URL = "https://github.com/ppy/osu-resources/raw/master/osu.Game.Resources/Textures/Flags"
    ICONS_BASE_URL = "https://github.com/ppy/osu-resources/raw/master/osu.Game.Resources/Textures/Icons/BeatmapDetails"
    SKIN_BASE_URL = "https://github.com/ppy/osu-resources/raw/master/osu.Game.Resources/Skins/Legacy"
    GAMEPLAY_BASE_URL = "https://github.com/ppy/osu-resources/raw/master/osu.Game.Resources/Textures/Gameplay/osu"

    # ПУТЬ К ТВОЕМУ ШРИФТУ (оставляем локальный)
    FONT_PATH = r"C:\Users\user\Desktop\droidBot\assets\fonts\font.ttf"

    @staticmethod
    async def get_image(url):
        print(f"DEBUG: get_image called with URL: {url}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as resp:
                    print(f"DEBUG: Response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.read()
                        print(f"DEBUG: Downloaded {len(data)} bytes")
                        return Image.open(io.BytesIO(data)).convert("RGBA")  # <- PIL Image сразу
                    else:
                        print(f"DEBUG: Failed to download image, status: {resp.status}")
            except Exception as e:
                print(f"DEBUG: Exception in get_image: {e}")
        return None


    @staticmethod
    async def get_avatar_by_username(username: str, size: int = 128):
        # 1. Получаем UID
        u_id = await GraphicsGenerator.get_user_id_by_username(username)
        if not u_id:
            print("DEBUG: UID not found")
            return None

        # 2. Формируем URL
        url = f"https://osudroid.moe/user/avatar/{u_id}.png"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "image/png"}) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return io.BytesIO(data)  # для Telegram
                    else:
                        print("DEBUG: Avatar request failed", resp.status)
                        text = await resp.text()
                        print("DEBUG response:", text)
                        return None
        except Exception as e:
            print("DEBUG: Exception in get_avatar_by_username", e)
        return None

    @staticmethod
    async def get_user_id_by_username(username):
        """Получаем userId через API osudroid"""
        url = f"https://new.osudroid.moe/api2/frontend/profile-username/{username}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("UserId")  # <- главное поле
                    else:
                        print(f"DEBUG: Status not 200 for {username}: {resp.status}")
                        return None
            except Exception as e:
                print(f"DEBUG: Exception in get_user_id_by_username: {e}")
                return None

    @staticmethod
    def calculate_level_from_score(score):
        """Расчет уровня на основе общего счета"""
        try:
            score = float(score) if not isinstance(score, (int, float)) else score
            level = int(score // 100000000) + 1
            progress = (score % 100000000) / 100000000
            return level, progress
        except:
            return 1, 0.0

    @staticmethod
    def count_grades_from_top_plays(top_plays):
        """Считаем ранги SS, S, A из Top50Plays"""
        if not top_plays or not isinstance(top_plays, list):
            return {"SS": 0, "SH": 0, "S": 0, "A": 0}

        grades_counter = Counter()

        for play in top_plays:
            map_rank = play.get("MapRank", "").upper()
            if map_rank in ["SS", "SH", "S", "A"]:
                grades_counter[map_rank] += 1

        # Возвращаем словарь с дефолтными значениями
        return {
            "SS": grades_counter.get("SS", 0),
            "SH": grades_counter.get("SH", 0),
            "S": grades_counter.get("S", 0),
            "A": grades_counter.get("A", 0)
        }

    @staticmethod
    async def draw_beatmap_card(map_data, dpp_data):
        """
        map_data: данные от osu! v2 API
        dpp_data: данные от droidpp.osudroid.moe
        Glassmorphism design inspired by oki-public
        """
        W, H = 1000, 550

        # 1. Glassmorphism background
        card = Image.new('RGBA', (W, H), (42, 34, 46, 255))
        draw = ImageDraw.Draw(card)
        
        # Glass effect overlay
        glass_overlay = Image.new('RGBA', (W, H), (255, 255, 255, 20))
        card.paste(glass_overlay, (0, 0), glass_overlay)
        
        # Load and blur cover for background
        cover_url = map_data['beatmapset']['covers']['cover@2x']
        cover_img = await GraphicsGenerator.get_image(cover_url)
        if cover_img:
            cover_img = cover_img.resize((W, H), Image.LANCZOS)
            cover_img = cover_img.filter(ImageFilter.GaussianBlur(15))
            cover_img.putalpha(100)
            card.paste(cover_img, (0, 0), cover_img)

        draw = ImageDraw.Draw(card)

        # Шрифты
        f_title = ImageFont.truetype(GraphicsGenerator.FONT_PATH, 42)
        f_artist = ImageFont.truetype(GraphicsGenerator.FONT_PATH, 26)
        f_stats = ImageFont.truetype(GraphicsGenerator.FONT_PATH, 24)
        f_pp_val = ImageFont.truetype(GraphicsGenerator.FONT_PATH, 38)

        # 2. Заголовок и инфо о мапе
        title = map_data['beatmapset']['title']
        if len(title) > 35: title = title[:32] + "..."

        draw.text((40, 40), title, fill="#FFFFFF", font=f_title)
        draw.text((45, 95), f"by {map_data['beatmapset']['artist']}", fill="#CCCCCC", font=f_artist)
        draw.text((45, 130), f"Difficulty: [{map_data['version']}]", fill="#FFCC22", font=f_artist)

# 3. Визуальные статы (CS, AR, OD, HP)
        stats = [
            ("CS", map_data['cs'], "cs.png"),
            ("AR", map_data['ar'], "ar.png"),
            ("OD", map_data['accuracy'], "accuracy.png"),
            ("HP", map_data['drain'], "hp-drain.png")
        ]

        y_offset = 200
        bar_start_x = 135   # Увеличили, чтобы текст "OD: 8.5" не касался полоски
        max_bar_width = 160  # Сделали чуть короче для запаса места

        for name, val, icon_name in stats:
            # Рисуем текст (название стата)
            draw.text((45, y_offset), f"{name}: {val}", fill="white", font=f_stats)

            # Рисуем фоновую полоску (серую)
            draw.rounded_rectangle(
                [bar_start_x, y_offset + 10, bar_start_x + max_bar_width, y_offset + 22],
                radius=6, fill=(50, 50, 50)
            )

            # Рисуем активную полоску (голубую)
            progress = min(float(val) / 10.0, 1.0)
            draw.rounded_rectangle(
                [bar_start_x, y_offset + 10, bar_start_x + (progress * max_bar_width), y_offset + 22],
                radius=6, fill="#66CCFF"
            )

            y_offset += 55

# --- ФИНАЛЬНЫЙ БЛОК DROID PP С ПРАВЫМ ВЫРАВНИВАНИЕМ ---
        pp_box_x = 550
        box_width = 410 # Ширина черного бокса (1000 - 40 - 550)
        right_padding = 40 # Отступ от правого края бокса
        right_target = pp_box_x + box_width - right_padding

        # Рисуем подложку с дуговыми углами
        draw.rounded_rectangle([pp_box_x, 180, 960, 480], radius=35, fill=(0, 0, 0, 100))

        # Переменные по умолчанию
        droid_sr, pp_100 = 0.0, 0.0

        if dpp_data:
            try:
                # Извлекаем данные из вложенной структуры API
                difficulty = dpp_data.get('difficulty', {}).get('droid', {})
                performance = dpp_data.get('performance', {}).get('droid', {})
                droid_sr = float(difficulty.get('total', 0.0))
                pp_100 = float(performance.get('total', 0.0))
            except (TypeError, ValueError):
                pass

        # 1. Отрисовка Droid Difficulty (без звездочки)
        draw.text((pp_box_x + 30, 200), "Droid Difficulty", fill="#AAAAAA", font=f_artist)
        sr_text = f"{droid_sr:.2f}"
        draw.text((pp_box_x + 30, 235), sr_text, fill="#FFCC22", font=f_pp_val)

        # 2. Отрисовка Performance Points
        draw.text((pp_box_x + 30, 310), "Performance Points", fill="#AAAAAA", font=f_artist)

        pp_list = [
            ("100%", pp_100, "#FFFFFF"),
            ("98%", pp_100 * 0.94, "#DDDDDD"),
            ("95%", pp_100 * 0.85, "#AAAAAA")
        ]

        y_pp = 355
        for acc_label, val, color in pp_list:
            # Рисуем проценты (фиксированно слева)
            draw.text((pp_box_x + 30, y_pp), f"{acc_label}:", fill=color, font=f_stats)

            # Рисуем PP (ВЫРАВНИВАНИЕ ПО ПРАВОМУ КРАЮ)
            val_text = f"{val:.2f}pp"

            # Считаем ширину конкретно этого текста
            bbox = draw.textbbox((0, 0), val_text, font=f_stats)
            text_width = bbox[2] - bbox[0]

            # Начальная точка X = Цель справа - Ширина текста
            x_aligned = right_target - text_width

            draw.text((x_aligned, y_pp), val_text, fill=color, font=f_stats)
            y_pp += 40

        # 5. Нижняя панель (BPM, Length)
        bpm = map_data.get('bpm', 0)
        length = map_data.get('total_length', 0)
        m, s = divmod(length, 60)
        draw.text((45, H - 60), f"BPM: {bpm}  •  Length: {m:02d}:{s:02d}  •  Status: {map_data['status'].capitalize()}", fill="#888888", font=f_artist)

        # Сохранение в буфер
        buf = io.BytesIO()
        card.convert("RGB").save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf


    @staticmethod
    async def get_seasonal_backgrounds():
        """Получение сезонных фонов из официального osu! API"""
        try:
            url = "https://osu.ppy.sh/api/v2/seasonal-backgrounds"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("backgrounds", [])
                    else:
                        print(f"Failed to get seasonal backgrounds: {response.status}")
                        return []
        except Exception as e:
            print(f"Error getting seasonal backgrounds: {e}")
            return []

    @staticmethod
    async def create_profile_card(data, seasonal_bg_url=None):
        """Создание карточки профиля с glassmorphism дизайном и опциональным сезонным фоном"""
        W, H = 800, 420

        try:
            # Glassmorphism background
            base = Image.new('RGBA', (W, H), (42, 34, 46, 255))
            draw = ImageDraw.Draw(base)
            
            # Glass effect overlay
            glass_bg = Image.new('RGBA', (W, H), (255, 255, 255, 15))
            base.paste(glass_bg, (0, 0), glass_bg)

            # Сезонный фон (если указан)
            if seasonal_bg_url:
                try:
                    seasonal_img = await GraphicsGenerator.get_image(seasonal_bg_url)
                    if seasonal_img:
                        seasonal_img = seasonal_img.resize((W, H), Image.LANCZOS)
                        seasonal_img = seasonal_img.filter(ImageFilter.GaussianBlur(8))
                        seasonal_img.putalpha(120)
                        base.paste(seasonal_img, (0, 0), seasonal_img)
                except Exception as e:
                    print(f"Error loading seasonal background: {e}")

            def get_font(size):
                try:
                    return ImageFont.truetype(GraphicsGenerator.FONT_PATH, size)
                except:
                    return ImageFont.load_default()

            f_name = get_font(45)
            f_rank = get_font(40)
            f_sub = get_font(22)
            f_val = get_font(26)
            f_grades = get_font(24)
            f_large_grades = get_font(32)

            # --- АВАТАР ---
            username = data.get("Username", "")
            u_id = data.get("UserId") or await GraphicsGenerator.get_user_id_by_username(username)
            av_img = None

            if u_id:
                avatar_url = f"https://osudroid.moe/user/avatar/{u_id}.png"
                av_img = await GraphicsGenerator.get_image(avatar_url)  # PIL Image

            if av_img:
                # Аватар с закругленными углами (без фона)
                av = av_img.resize((170, 170))
                mask = Image.new("L", (170, 170), 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, 170, 170], radius=30, fill=255)
                base.paste(av, (30, 40), mask)
            
            # --- ИМЯ И РЕГИОН ---
            region_code = data.get("Region", "UN").upper()
            draw.text((220, 35), username or "Unknown", fill=(255, 255, 255), font=f_name)

            # Флаг
            flag_url = f"{GraphicsGenerator.FLAGS_BASE_URL}/{region_code}.png"
            flag_img = await GraphicsGenerator.get_image(flag_url)
            if flag_img:
                flag_resized = flag_img.resize((35, 23), Image.LANCZOS)
                base.paste(flag_resized, (220, 100), flag_resized)
            draw.text((265, 98), region_code, fill=(200, 200, 205), font=f_sub)

            # --- РАНГ ---
            g_rank = f"#{data.get('GlobalRank', 0):,}"
            c_rank = f"#{data.get('CountryRank', 0):,}"
            draw.text((220, 135), g_rank, fill=(255, 255, 255), font=f_rank)
            draw.text((220, 185), f"Country Rank: {c_rank}", fill=(255, 204, 34), font=f_sub)

            # --- РАНГИ SS/S/A ---
            top_plays = data.get("Top50Plays", [])
            grades = GraphicsGenerator.count_grades_from_top_plays(top_plays)
            grade_list = [("SS", grades.get("SS", 0) + grades.get("SH", 0)), ("S", grades.get("S", 0)), ("A", grades.get("A", 0))]

            start_x = 520
            spacing = 100
            grade_y = 50
            for i, (grade_text, count) in enumerate(grade_list):
                x = start_x + i * spacing
                # буква
                bbox = draw.textbbox((0, 0), grade_text, font=f_large_grades)
                letter_x = x + (60 - (bbox[2] - bbox[0])) // 2
                letter_y = grade_y
                draw.text((letter_x, letter_y), grade_text, fill=(255, 255, 255), font=f_large_grades)
                # количество под буквой
                count_str = str(count)
                count_bbox = draw.textbbox((0, 0), count_str, font=f_grades)
                count_x = x + (60 - (count_bbox[2] - count_bbox[0])) // 2
                count_y = letter_y + (bbox[3] - bbox[1]) + 10
                draw.text((count_x, count_y), count_str, fill=(220, 220, 230), font=f_grades)

            # --- УРОВЕНЬ ---
            total_score = data.get("OverallScore", 0)
            level, progress = GraphicsGenerator.calculate_level_from_score(total_score)
            bar_x1, bar_y1, bar_x2, bar_y2 = 250, 250, 750, 262
            draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=6, fill=(40, 40, 45))
            progress_width = int((bar_x2 - bar_x1) * progress)
            draw.rounded_rectangle([bar_x1, bar_y1, bar_x1 + progress_width, bar_y2], radius=6, fill=(255, 204, 34))
            level_text = f"Lvl {level} ({int(progress*100)}%)"
            bbox = draw.textbbox((0, 0), level_text, font=f_sub)
            draw.text((bar_x2 - (bbox[2]-bbox[0]) - 5, bar_y1 - (bbox[3]-bbox[1]) - 5), level_text, fill=(255, 255, 255), font=f_sub)

            # --- СТАТИСТИКА ---
            stats = [
                ("Performance", f"{data.get('OverallPP',0):.2f}pp", "number.png"),
                ("Accuracy", f"{data.get('OverallAccuracy',0)*100:.2f}%", "accuracy.png"),
                ("Playcount", f"{data.get('OverallPlaycount',0):,}", "circles.png"),
                ("Total Score", f"{data.get('OverallScore',0)/1_000_000_000:.2f}b", "size.png")
            ]

            box_w, box_h = 185, 100
            radius = 15
            alpha = 180  # прозрачность (0-255)

            for i, (label, val, icon_name) in enumerate(stats):
                x_pos = 20 + i * 195
                y_pos = 300

                # Создаем полупрозрачный бокс с закругленными углами
                overlay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rounded_rectangle([0, 0, box_w, box_h], radius=radius, fill=(0, 0, 0, alpha))
                base.paste(overlay, (x_pos, y_pos), overlay)

                # Текст
                draw.text((x_pos + 44, y_pos + 12), label, fill=(200, 200, 210), font=f_sub)
                draw.text((x_pos + 15, y_pos + 50), val, fill=(255, 255, 255), font=f_val)

                # Иконка (если есть)
                icon_loaded = False
                if icon_name == "number.png":
                    # Используем значок performance из gameplay/osu
                    icon_url = f"{GraphicsGenerator.GAMEPLAY_BASE_URL}/{icon_name}"
                else:
                    # Используем обычные иконки
                    icon_url = f"{GraphicsGenerator.ICONS_BASE_URL}/{icon_name}"
                
                icon_img = await GraphicsGenerator.get_image(icon_url)
                if icon_img:
                    icon_resized = icon_img.resize((24, 24), Image.LANCZOS)
                    base.paste(icon_resized, (x_pos + 15, y_pos + 10), icon_resized)
                    icon_loaded = True

                # Если иконка не загрузилась, оставляем символ-заглушку
                if not icon_loaded:
                    draw.text((x_pos + 15, y_pos + 12), "x", fill=(130, 130, 140), font=f_sub)


            # --- Сохраняем в буфер ---
            buf = io.BytesIO()
            base.convert("RGB").save(buf, format="PNG", optimize=True)
            buf.seek(0)
            return buf

        except Exception as e:
            print(f"Error creating profile card: {e}")
            import traceback; traceback.print_exc()
            return None
        
    @staticmethod
    async def draw_compare_card(user1_data, user2_data):
            # Создаем полотно 1200x600 (две карточки рядом)
            base = Image.new('RGBA', (1200, 600), (20, 20, 20, 255))
            # Логика отрисовки: 
            # 1. Рисуем левую часть для user1
            # 2. Рисуем правую часть для user2
            # 3. Посередине рисуем "VS"
            
            # Пример логики сравнения для текста:
            diff_pp = user1_data['pp'] - user2_data['pp']
            winner = user1_data['username'] if diff_pp > 0 else user2_data['username']
            
            # Возвращаем готовый буфер
            return buf
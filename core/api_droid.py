# Path: core/api_droid.py
import os
import json
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import aiohttp
import logging

# Create logger that will definitely write to console
logger = logging.getLogger("api_droid")

class DroidAPI:
    """Class for working with LDroid5 API - updated version from ldbot"""
    
    def __init__(self):
        self.api_base = 'https://osudroid.moe/api/'
        self.new_api_base = "https://new.osudroid.moe/api2/frontend"
        self.multiplayer_base = 'https://multi.osudroid.moe'
        self.api_version = "58"
        
        # Session data
        self.user_id: Optional[int] = None
        self.session_id: Optional[str] = None
        self.username: Optional[str] = None
        self.rank: Optional[int] = None
        self.score: Optional[int] = None
        self.pp: Optional[float] = None
        self.accuracy: Optional[float] = None
        self.avatar_url: Optional[str] = None
        
        self.is_logged_in = False

    # --- Compatibility with old code ---
    async def get_profile(self, username):
        """Compatible method for old code"""
        profile_data = await self.get_user_profile_by_username_new(username)
        if profile_data:
            # Convert to old format
            return {
                'UserId': profile_data.get('user_id'),
                'Username': profile_data.get('username'),
                'OverallPP': profile_data.get('pp'),
                'GlobalRank': profile_data.get('rank'),
                'OverallScore': profile_data.get('score'),
                'OverallAccuracy': profile_data.get('accuracy'),
                'OverallPlaycount': profile_data.get('playcount')
            }
        return None

    def _parse_osu_metadata(self, osu_content: bytes) -> dict:
        """Parse BPM and Length from .osu file"""
        try:
            content = osu_content.decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            bpm = 0
            length = 0
            in_timing_section = False
            
            for line in lines:
                line = line.strip()
                
                # Ищем метаданные в секции [General]
                if line == '[General]':
                    continue
                elif line == '[Editor]':
                    break  # Конец секции General
                    
                # Парсим AudioLeadIn (обычно содержит длину)
                if line.startswith('AudioLeadIn:'):
                    try:
                        length_ms = int(line.split(':')[1])
                        length = length_ms // 1000  # Конвертируем в секунды
                    except:
                        pass
                        
                # Парсим PreviewTime (может содержать информацию о треке)
                elif line.startswith('PreviewTime:'):
                    pass
                    
                # Ищем BPM в секции [TimingPoints]
                elif line == '[TimingPoints]':
                    in_timing_section = True
                    continue
                elif in_timing_section and line and not line.startswith('//') and ',' in line:
                    # Формат: offset,ms_per_beat,time_signature,sample_set,sample_set,volume,uninherited,effects
                    try:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            ms_per_beat = float(parts[1])
                            if ms_per_beat > 0:  # Не inherited timing point
                                bpm = 60000 / ms_per_beat  # Конвертируем в BPM
                                break  # Берем первый (основной) BPM
                    except:
                        pass
            
            # Если не нашли BPM, пробуем найти в других местах
            if bpm == 0:
                for line in lines:
                    line = line.strip()
                    # Ищем BPM в тегах или комментариях
                    if 'bpm' in line.lower() and ':' in line:
                        try:
                            bpm = float(line.split(':')[1].strip())
                            break
                        except:
                            pass
            
            return {'bpm': bpm, 'total_length': length}
        except Exception as e:
            logger.error(f"Ошибка парсинга .osu: {e}")
            return {'bpm': 0, 'total_length': 0}

    async def get_map_pp(self, beatmap_id: str):
        """
        Умный запрос к калькулятору.
        Сначала пробуем отправить ссылку. Если не выходит — скачиваем файл сами и шлем его.
        """
        calc_url = "https://droidpp.osudroid.moe/api/ppboard/calculatebeatmap"
        file_url = f"https://osu.ppy.sh/osu/{beatmap_id}"
        
        logger.info(f"Начинаю расчет DPP для карты {beatmap_id}...")

        async with aiohttp.ClientSession() as session:
            # 1. Сначала скачиваем сам .osu файл к себе в память
            osu_content = None
            try:
                async with session.get(file_url) as file_resp:
                    if file_resp.status == 200:
                        osu_content = await file_resp.read()
                    else:
                        logger.warning(f"Не удалось скачать .osu файл: {file_resp.status}")
            except Exception as e:
                logger.error(f"Ошибка скачивания .osu файла: {e}")

            # 2. Формируем запрос к калькулятору
            data = aiohttp.FormData()
            
            # Парсим метаданные из .osu файла
            osu_metadata = {}
            if osu_content:
                osu_metadata = self._parse_osu_metadata(osu_content)
                logger.info(f"Extracted from .osu: BPM={osu_metadata.get('bpm')}, Length={osu_metadata.get('total_length')}s")
            
            if osu_content:
                # Если скачали файл - отправляем его как файл! Это самый надежный способ.
                logger.info("Отправляю .osu файл напрямую...")
                data.add_field('beatmapfile', osu_content, filename=f'{beatmap_id}.osu')
            else:
                # Если не скачали - пробуем отправить ссылку (как раньше)
                logger.info("🔗 Отправляю ссылку (резервный метод)...")
                data.add_field('beatmaplink', file_url)

            # Доп. параметры
            data.add_field('accuracy', '100')
            
            # 3. Отправляем в DroidPP
            try:
                async with session.post(calc_url, data=data, timeout=30) as resp:
                    resp_text = await resp.text() # Читаем как текст для дебага
                    
                    if resp.status == 200:
                        try:
                            res_json = await resp.json()
                            # Добавляем метаданные в ответ
                            if 'beatmap' in res_json and osu_metadata:
                                res_json['beatmap'].update(osu_metadata)
                            
                            # ВОТ ЭТО ПОПАДЕТ В ЛОГИ:
                            logger.info(f"DPP SUCCESS: {res_json}") 
                            return res_json
                        except:
                            # Если вернулся 200, но не JSON (иногда бывает HTML ошибка)
                            logger.warning(f"DPP вернул 200, но это не JSON: {resp_text[:100]}")
                            return None
                    else:
                        logger.error(f"DPP API Error {resp.status}: {resp_text[:200]}")
                        return None
            except Exception as e:
                logger.exception(f"Критическая ошибка в get_map_pp: {e}")
                return None

    async def get_history_from_top50(self, username):
        data = await self.get_profile(username)
        if not data or "Top50Plays" not in data:
            return {}, 0
        
        plays = data["Top50Plays"]
        # Сортируем от старых к новым
        plays.sort(key=lambda x: x.get("PlayedDate", ""))
        
        history = {}
        cumulative_pp = 0
        
        for i, play in enumerate(plays):
            raw_date = play.get("PlayedDate")
            if not raw_date: continue
                
            try:
                dt = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                val_pp = play.get("PP") or play.get("pp") or 0
                
                # Вес скора: PP * 0.95^index
                cumulative_pp += val_pp * (0.95 ** i)
                # Сохраняем последнюю известную точку для этой даты
                history[dt] = cumulative_pp
            except:
                continue
                
        return history, data.get("OverallPP", 0)

    # --- Новые методы из ldbot ---
    async def login(self, username: str, password: str) -> bool:
        """Авторизация в LDroid5"""
        try:
            # Хеширование пароля
            password_hash = hashlib.md5(password.encode()).hexdigest()
            
            # Отладочная информация
            logger.info(f"Attempting login for username: {username}")
            logger.info(f"API version: {self.api_version}")
            logger.info(f"API URL: {self.api_base}login.php")
            
            # Подготовка данных запроса
            data = {
                'username': username,
                'password': password_hash,
                'version': self.api_version
            }
            
            # Отправка запроса
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_base}login.php", data=data, timeout=10) as response:
                    logger.info(f"Login response status: {response.status}")
                    response_text = await response.text()
                    logger.info(f"Login response text: '{response_text}'")
                    
                    if response.status == 200:
                        lines = response_text.strip().split('\n')
                        logger.info(f"Response lines: {lines}")
                        
                        if len(lines) >= 1 and lines[0] == "SUCCESS":
                            params = lines[1].split() if len(lines) > 1 else []
                            logger.info(f"Response params: {params}")
                            
                            if len(params) >= 6:
                                # Сохранение данных сессии
                                self.user_id = int(params[0])
                                self.session_id = params[1]
                                self.rank = int(params[2])
                                self.score = int(params[3])
                                self.pp = float(params[4])
                                self.accuracy = float(params[5])
                                self.username = params[6] if len(params) > 6 else username
                                self.avatar_url = params[7] if len(params) > 7 else f"{self.api_base.replace('/api/', '')}/user/avatar/{self.user_id}.png"
                                
                                self.is_logged_in = True
                                logger.info(f"Login successful for user: {self.username}")
                                return True
                            else:
                                logger.warning(f"Insufficient params in response: {len(params)}")
                                return False
                        else:
                            # Проверяем специфические ошибки
                            if "Please update your client" in response_text:
                                logger.warning("API requires client update - server temporarily unavailable")
                                return "API_UNAVAILABLE"
                            elif "Invalid" in response_text:
                                logger.warning("Invalid credentials or parameters")
                                return False
                            else:
                                logger.warning(f"Login failed - response not SUCCESS: '{lines[0] if lines else 'empty'}'")
                                return False
                    else:
                        logger.error(f"HTTP error: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def get_user_profile_by_username_new(self, username: str) -> Optional[Dict[str, Any]]:
        """Получение данных профиля по имени через новый API"""
        try:
            logger.info(f"Searching for user: {username} (New API)")
            
            # Используем новый эндпоинт
            url = f"{self.new_api_base}/profile-username/{username}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"New API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"New API response data: {data}")
                        
                        if data:
                            profile_data = {
                                'user_id': data.get('UserId', 0),
                                'username': data.get('Username', username),
                                'pp': data.get('OverallPP', 0.0),
                                'rank': data.get('GlobalRank', 0),
                                'score': data.get('OverallScore', 0),
                                'accuracy': data.get('OverallAccuracy', 0.0),
                                'avatar_url': f"{self.new_api_base}/avatar/userid/{data.get('UserId', 0)}",
                                'playcount': data.get('OverallPlaycount', 0),
                                'level': 1,  # В новом API нет поля level
                                'profile_url': f"https://osudroid.moe/game/profile.php?uid={data.get('UserId', 0)}",
                                'country': data.get('Region', ''),
                                'joined_at': data.get('Registered', ''),
                                'last_played': data.get('LastLogin', ''),
                                'total_score': data.get('OverallScore', 0),
                                'total_pp': data.get('OverallPP', 0.0),
                                'country_rank': data.get('CountryRank', 0),
                                'supporter': data.get('Supporter', 0),
                                'core_developer': data.get('CoreDeveloper', 0),
                                'developer': data.get('Developer', 0),
                                'contributor': data.get('Contributor', 0)
                            }
                            
                            logger.info(f"Successfully parsed profile for {username}")
                            return profile_data
                        else:
                            logger.warning("Empty response from new API")
                    else:
                        logger.warning(f"New API error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error getting user profile from new API: {e}")
        
        return None

    async def get_user_profile_by_id_new(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение данных профиля по ID через новый API"""
        try:
            logger.info(f"Getting profile for user ID: {user_id} (New API)")
            
            # Используем новый эндпоинт
            url = f"{self.new_api_base}/profile-uid/{user_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"New API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"New API response data: {data}")
                        
                        if data:
                            profile_data = {
                                'user_id': data.get('UserId', user_id),
                                'username': data.get('Username', f"User_{user_id}"),
                                'pp': data.get('OverallPP', 0.0),
                                'rank': data.get('GlobalRank', 0),
                                'score': data.get('OverallScore', 0),
                                'accuracy': data.get('OverallAccuracy', 0.0),
                                'avatar_url': f"{self.new_api_base}/avatar/userid/{user_id}",
                                'playcount': data.get('OverallPlaycount', 0),
                                'level': 1,  # В новом API нет поля level
                                'profile_url': f"https://osudroid.moe/game/profile.php?uid={user_id}",
                                'country': data.get('Region', ''),
                                'joined_at': data.get('Registered', ''),
                                'last_played': data.get('LastLogin', ''),
                                'total_score': data.get('OverallScore', 0),
                                'total_pp': data.get('OverallPP', 0.0),
                                'country_rank': data.get('CountryRank', 0),
                                'supporter': data.get('Supporter', 0),
                                'core_developer': data.get('CoreDeveloper', 0),
                                'developer': data.get('Developer', 0),
                                'contributor': data.get('Contributor', 0)
                            }
                            
                            logger.info(f"Successfully parsed profile for ID {user_id}")
                            return profile_data
                        else:
                            logger.warning("Empty response from new API")
                    else:
                        logger.warning(f"New API error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error getting user profile from new API: {e}")
        
        return None

    async def get_leaderboard_new(self, leaderboard_type: str = "pp", region: str = "global", page: int = 1, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Получение лидерборда через новый API"""
        try:
            logger.info(f"Getting leaderboard: {leaderboard_type}, {region}, page {page}, limit {limit}")
            
            url = f"{self.new_api_base}/leaderboard/{leaderboard_type}/{region}/{page}/{limit}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"Leaderboard response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict) and 'leaderboard' in data:
                            return data['leaderboard']
                        else:
                            logger.warning(f"Unexpected leaderboard format: {type(data)}")
                            return []
                    else:
                        logger.warning(f"Leaderboard error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
        
        return None

    async def get_online_stats_new(self) -> Optional[Dict[str, Any]]:
        """Получение онлайн статистики через новый API"""
        try:
            logger.info("Getting online stats (New API)")
            
            url = f"{self.new_api_base}/online-stats"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"Online stats response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Online stats data: {data}")
                        return data
                    else:
                        logger.warning(f"Online stats error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error getting online stats: {e}")
        
        return None

    def get_profile_url(self, user_id: Optional[int] = None) -> str:
        """Получить URL профиля"""
        uid = user_id or self.user_id
        return f"https://osudroid.moe/game/profile.php?uid={uid}"
    
    def get_avatar_url(self, user_id: Optional[int] = None) -> str:
        """Получить URL аватара"""
        uid = user_id or self.user_id
        return f"https://osudroid.moe/user/avatar/{uid}.png"
    
    def get_user_info(self) -> Dict[str, Any]:
        """Получение информации о текущем пользователе"""
        if not self.is_logged_in:
            return {}
            
        return {
            'user_id': self.user_id,
            'username': self.username,
            'rank': self.rank,
            'score': self.score,
            'pp': self.pp,
            'accuracy': self.accuracy,
            'avatar_url': self.avatar_url,
            'profile_url': self.get_profile_url()
        }
# Файл: core/downloader.py

import aiohttp
import logging # Импорт

# Получаем логгер для этого конкретного модуля
log = logging.getLogger("downloader")

async def download_from_mirrors(beatmapset_id: str, no_video: bool = True):
    suffix = "?noVideo=1" if no_video else ""
    mirrors = [
        f"https://api.nerinyan.moe/d/{beatmapset_id}{suffix}",
        f"https://osu.direct/api/d/{beatmapset_id}{suffix}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in mirrors:
            try:
                log.info(f"Trying mirror: {url}") # Логируем попытку
                async with session.get(url, timeout=60) as r:
                    if r.status == 200:
                        data = await r.read()
                        log.info(f"Successfully downloaded from {url}")
                        return data
                    else:
                        log.warning(f"Mirror returned {r.status}: {url}")
            except Exception as e:
                log.error(f"Connection error with {url}: {e}")
                continue
    
    log.error(f"All mirrors failed for SetID: {beatmapset_id}")
    return None
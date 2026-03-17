# core/api_osu.py
import aiohttp
from config import OSU_CLIENT_ID, OSU_CLIENT_SECRET
import logging

logger = logging.getLogger("api_osu")

class OsuAPI:
    BASE_URL = "https://osu.ppy.sh/api/v2"

    def __init__(self, client_id: int, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    async def auth(self):
        url = "https://osu.ppy.sh/oauth/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "public"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as resp:
                res = await resp.json()
                self.token = res.get("access_token")
                logger.info("OsuAPI token obtained")

    async def _request(self, method: str, endpoint: str, params=None):
        if not self.token:
            await self.auth()
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.BASE_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.error(f"OsuAPI request error {resp.status}: {await resp.text()}")
                return None

    async def search_advanced(self, params: dict):
        return await self._request("GET", "/beatmapsets/search", params=params)

    async def get_profile(self, username: str):
        return await self._request("GET", f"/users/{username}/osu")

    async def get_beatmap(self, beatmap_id: int):
        return await self._request("GET", f"/beatmaps/{beatmap_id}")

    async def get_beatmapset(self, set_id: int):
        return await self._request("GET", f"/beatmapsets/{set_id}")

    async def recommend_maps(self, target_sr: float, limit: int = 10):
        """Берем только карты с официального osu! API"""
        params = {
            "status": "ranked",
            "sort": "plays_desc",
            "stars": f"{target_sr-0.2:.2f}-{target_sr+0.2:.2f}",
            "nsfw": "false",
            "m": 0,   # стандартный режим osu!standard
            "limit": limit
        }
        data = await self.search_advanced(params)
        maps = []
        if not data:
            return maps

        for mset in data.get("beatmapsets", []):
            for bm in mset.get("beatmaps", []):
                maps.append({
                    "id": bm["id"],
                    "set_id": mset["id"],
                    "artist": mset.get("artist", "Unknown"),
                    "title": mset.get("title", "Unknown"),
                    "sr": bm.get("difficulty_rating", 0)
                })
        return maps

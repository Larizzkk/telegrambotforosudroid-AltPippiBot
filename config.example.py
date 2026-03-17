# Telegram Bot Configuration
# Copy this file to config.py and fill in your actual values

# Bot token from @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Database path
DB_PATH = "database/users.db"

# osu! API Configuration (optional - for fallback beatmap info)
OSU_API_KEY = "YOUR_OSU_API_KEY_HERE"
OSU_CLIENT_ID = YOUR_OSU_CLIENT_ID_HERE
OSU_CLIENT_SECRET = "YOUR_OSU_CLIENT_SECRET_HERE"
OSU_SESSION = "YOUR_OSU_SESSION_HERE"

# Download directory for beatmaps
DOWNLOAD_DIR = "downloads"

# Public API endpoints that can be used by everyone
# These are safe to expose in the repository
PUBLIC_APIS = {
    "osudroid_api": "https://osudroid.moe/api/",
    "new_osudroid_api": "https://new.osudroid.moe/api2/frontend",
    "osu_api": "https://osu.ppy.sh/api/v2",
    "beatmap_covers": "https://assets.ppy.sh/beatmaps/",
    "download_mirrors": [
        "https://api.nerinyan.moe/d/",
        "https://osu.direct/api/d/",
        "https://api.chimu.moe/v1/download/",
        "https://dl.sayobot.cn/beatmaps/download/full/"
    ]
}

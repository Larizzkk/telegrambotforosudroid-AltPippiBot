# AltPippi Telegram Bot for osu!droid

A comprehensive Telegram bot for osu!droid players with profile tracking, beatmap information, leaderboards, and more.

## Features

- **User Profiles**: Enhanced profile cards with real API stats, badges, and seasonal backgrounds
- **Recent Plays**: View recent scores with pagination using osudroid-api-wrapper
- **Beatmap Information**: Detailed beatmap stats with PP calculations and download links
- **Leaderboards**: Global and country leaderboards (PP/Score/Accuracy)
- **Seasonal Profiles**: Customizable seasonal backgrounds for profile cards
- **Beatmap Search**: Search and download beatmaps from multiple mirrors
- **Multi-language Support**: English and Russian localization
- **Account Binding**: Link your osu!droid account for quick access

## Commands

### Basic Commands
- `/start` - Start the bot
- `/help` - Show all available commands
- `/lang <ru/en>` - Change language

### Profile Commands
- `/u <username>` - Get enhanced user profile with real API stats
- `/bind <username>` - Bind your osu!droid account
- `/unbind` - Unbind your account
- `/prpic <username>` - Generate profile picture card with seasonal background
- `/seasonal` - Choose seasonal backgrounds for profile cards

### Beatmap Commands
- `/map <link or ID>` - Get detailed beatmap information
- `/recent <username>` - Show recent plays with pagination
- `/topplays <username>` - Show top 10 plays
- `/sr <query>` - Search beatmaps

### Leaderboard Commands
- `/leaderboard <type> <region>` - Show leaderboard
  - Types: `pp`, `score`, `accuracy`
  - Regions: `global`, `country`

### Utility Commands
- `/roll [min max]` - Random number generator
- `/yn` - Yes/No random generator
- `/compare <user1> <user2>` - Compare two users

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Larizzkk/telegrambotforosudroid-AltPippiBot.git
   cd telegrambotforosudroid-AltPippiBot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   ```bash
   cp config.example.py config.py
   # Edit config.py with your actual values
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## Configuration

Edit `config.py` with your settings:

- `BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
- `DB_PATH`: Path to SQLite database (default: `database/users.db`)
- `OSU_API_KEY`: Optional osu! API key for fallback beatmap info
- `OSU_CLIENT_ID` / `OSU_CLIENT_SECRET`: osu! OAuth credentials
- `DOWNLOAD_DIR`: Directory for beatmap downloads

## API Integration

The bot integrates with multiple public APIs:

### osu!droid APIs
- **Main API**: `https://osudroid.moe/api/`
- **New API**: `https://new.osudroid.moe/api2/frontend`

### osu! APIs (fallback)
- **API v2**: `https://osu.ppy.sh/api/v2`
- **Beatmap downloads**: Multiple mirrors for reliability

### Download Mirrors
- NeriNan: `https://api.nerinyan.moe/d/`
- osu.direct: `https://osu.direct/api/d/`
- Chimu: `https://api.chimu.moe/v1/download/`
- Sayobot: `https://dl.sayobot.cn/beatmaps/download/full/`

## Database Schema

The bot uses SQLite with the following tables:

### users
- `user_id`: Telegram user ID (PRIMARY KEY)
- `droid_name`: Bound osu!droid username
- `lang`: Preferred language (`en`/`ru`)
- `frame_color`: Profile frame color
- `gradient`: Profile gradient setting
- `seasonal_bg`: Seasonal background URL

### pp_history
- `id`: Record ID (PRIMARY KEY)
- `user_id`: Telegram user ID
- `pp_value`: PP amount
- `date`: Timestamp

## Dependencies

- `aiogram`: Telegram bot framework
- `aiohttp`: HTTP client for API requests
- `PIL`: Image processing for profile cards
- `sqlite3`: Database management
- `osudroid-api-wrapper`: osu!droid API integration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Security

- Sensitive data (API keys, tokens) are excluded via `.gitignore`
- Use `config.example.py` as a template for configuration
- Never commit actual `config.py` with real credentials

## License

This project is open source. Check the LICENSE file for details.

## Support

For issues and feature requests, please use the GitHub Issues page.

---

**Note**: This bot is designed for osu!droid players and uses the osu!droid API as primary data source.

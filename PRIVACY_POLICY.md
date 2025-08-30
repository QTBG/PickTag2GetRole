# Privacy Policy - PickTag2GetRole Bot

*Last updated: August 2025*

## What We Collect
- **Server Information**: Discord server ID where the bot is installed
- **User Information**: Discord user ID and username of members in the server
- **Tag Configuration**: The specific server tag you configure the bot to monitor
- **Role Configuration**: The role IDs you configure to be assigned/removed
- **Primary Guild Data**: User's primary server information (server ID, tag, and whether it's publicly displayed)

## How We Use Data
- Monitor if users have the configured server tag in their profile
- Automatically assign or remove the configured roles based on tag presence
- Store your configuration settings in a local SQLite database
- Respond to tag changes in real-time using Discord events

## We Do NOT
- Read or store message content
- Access private messages or DMs
- Share any data with third parties
- Store any personal information beyond Discord IDs
- Track user activity beyond tag presence
- Access any data outside of the configured server

## Data Storage
- All data is stored locally in SQLite database files
- Database location: `data/bot_data.db`
- Only configuration data is persisted (guild_id, tag_to_watch, role_ids, enabled status)
- User data is only processed in memory for tag checking

## Your Rights
- View your configuration with `/status` command
- Disable monitoring with `/toggle` command
- Remove all data by kicking the bot from your server (data is automatically deleted)
- Request manual data deletion via GitHub

## Data Retention
- Configuration data is kept as long as the bot remains in your server
- When the bot is removed, all server data is automatically deleted
- No user data is permanently stored

## Security
- Data is stored locally with file system permissions
- No external API calls except Discord's official API
- Open-source code allows full transparency

## Contact
Questions or concerns: https://github.com/QTBG/PickTag2GetRole
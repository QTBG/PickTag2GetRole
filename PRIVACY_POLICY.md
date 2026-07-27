# Privacy Policy - PickTag2GetRole Bot

*Last updated: July 2026*

## What We Collect
- **Server Information**: Discord server ID where the bot is installed
- **User Information**: Discord user IDs of server members (processed in memory only, never stored)
- **Tag Configuration**: The specific server tag you configure the bot to monitor
- **Role Configuration**: The role IDs you configure to be assigned/removed
- **Primary Guild Data**: User's primary server information (server ID, tag, and whether it's publicly displayed), processed in memory only
- **Aggregated Statistics**: One daily counter per server (number of members displaying the configured tag, total member count) — numbers only, no user IDs

## Discord Gateway Intents
The bot only subscribes to the minimum Discord gateway intents required to function:
- **Guilds**: server and role information
- **Server Members** (privileged): member list and member updates, used for role assignment and scans
- **Presences** (privileged): required to detect server tag (primary guild) changes in real time

The bot does **not** subscribe to message, reaction, typing, voice, or moderation events.

## How We Use Data
- Monitor if users have the configured server tag in their profile
- Automatically assign or remove the configured roles based on tag presence
- Store your configuration settings in a local SQLite database
- Respond to tag changes in real-time using Discord events
- Perform a verification at startup and once daily as backup

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
- Only configuration data (guild_id, tag_to_watch, role_ids, enabled status) and daily aggregated counters (tagged member count, total member count per server — no user IDs) are persisted
- Automatic local backups of this database are kept in `data/backups/` (rotated daily, 7 files by default)
- User data is only processed in memory for tag checking

## Your Rights
- View your configuration with `/status` command
- Disable monitoring with `/toggle` command
- Delete all stored data instantly with the `/reset` command
- Remove all data by kicking the bot from your server (data is automatically deleted)
- Request manual data deletion via GitHub

## Data Retention
- Configuration data is kept as long as the bot remains in your server
- Aggregated daily statistics are kept for at most 365 days
- When the bot is removed (or `/reset` is used), all server data — configuration and statistics — is automatically deleted
- Deleted data may persist in local daily backups for up to 7 days before rotation removes it
- No user data is permanently stored

## Security
- Data is stored locally with file system permissions
- No external API calls except Discord's official API
- Logs contain Discord IDs only (never usernames or message content) and are automatically rotated
- Open-source code allows full transparency

## Contact
Questions or concerns: https://github.com/QTBG/PickTag2GetRole
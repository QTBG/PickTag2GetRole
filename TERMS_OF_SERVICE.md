# Terms of Service - PickTag2GetRole

*Last updated: September 21, 2026*

## 1. Acceptance

By adding or using PickTag2GetRole in your Discord server, you agree to these terms. If you self-host the code, you are responsible for operating your instance and providing its users with accurate privacy information.

## 2. Service Description

PickTag2GetRole assigns or removes configured Discord roles according to a member's public server tag. Eligibility requires the tag's source server to be the server being monitored and its text to match the configured tag, ignoring case. A matching tag from another server does not qualify.

The bot uses member events and periodic scans to synchronize roles. It also provides server configuration commands and aggregate daily statistics. It does not monitor online status, games or messages.

## 3. Required Permissions and Intents

The invitation requests **Manage Roles**, with the OAuth2 scopes `bot` and `applications.commands`. The bot's highest role must be above the roles it manages. It does not require **Administrator**, **View Channels**, message history or message-sending permissions. Updating the bot does not automatically revoke permissions previously granted to an existing installation.

The Gateway intents are **Guilds** and **Server Members**. Server Members is the only privileged intent requested; it provides member lists and member updates, including public primary-guild changes. **Presence** and **Message Content** are not requested.

Server management commands require the caller's **Manage Roles** permission at runtime. Configured roles must also be below the caller's highest role, except for the server owner. `/botstats` is restricted to the bot owner.

## 4. Acceptable Use

- Use the bot for legitimate role management and comply with Discord's terms and policies.
- Do not exploit the bot, attempt unauthorized access, or use it to collect information unrelated to its role-management purpose.
- Configure only roles you are authorized to manage, maintain the required role hierarchy, and inform members how your server uses the bot.

## 5. Limitations

- Public tag visibility and the correct source server are required for role eligibility. Text-only matches and partial `#` matching are not supported.
- Role updates depend on Discord connectivity, API limits, member availability, permissions and role hierarchy. Immediate delivery is not guaranteed.
- A startup scan, a daily scan and `/scan` reconcile missed updates. Memory-saving configurations may rely more on these scans.
- An invalid configuration pauses monitoring until corrected. Changes to a valid configuration or migration from older text-only matching can change which members qualify and cause configured roles to be removed.
- `/toggle` and `/reset` stop processing for the configuration after any role operation already in progress completes. They do not remove roles already assigned in Discord.

## 6. Data Handling and Deletion

The [Privacy Policy](PRIVACY_POLICY.md) explains data use, required encryption, retention, member caching and deletion. `/reset` removes the server's configuration and statistics from the live database and managed local backups. A failed deletion must be retried or addressed with the operator. Removing the bot also triggers cleanup, with startup reconciliation if it left while offline.

Self-hosting operators must protect the token and encryption key, maintain access controls, and apply retention and deletion to any external backups or host snapshots they create. Losing the encryption key can make stored data unrecoverable.

## 7. No Warranty

The bot is provided "as is", without guarantees of uptime or functionality, subject to applicable law and the MIT license. Open-source availability does not constitute certification or approval by Discord.

## 8. Open Source

The code is provided under the [MIT License](LICENSE). You may self-host it under that license.

## 9. Changes

These terms or the bot's functionality may change. The current documents are available in the public repository and linked by `/help`.

## 10. Termination

The operator may stop providing the service for abuse or violations of Discord's terms. Server managers can remove the bot at any time.

## 11. Contact

Questions or requests: [GitHub issues](https://github.com/QTBG/PickTag2GetRole/issues). This is a public channel; do not post secrets or private member data. Contact the instance operator for a separately hosted deployment.

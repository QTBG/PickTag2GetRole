# Privacy Policy - PickTag2GetRole

*Last updated: September 21, 2026*

PickTag2GetRole assigns and removes Discord roles when members display the configured tag of the server where the bot is installed. This policy describes the data handled by this version of the bot. If you self-host it, you operate your own instance and are responsible for its hosting, access controls, external backups and privacy information.

## Data Received and Used

Discord provides server, role and member information to the bot. The Discord library keeps some of that information in memory to process member updates and manage roles. This can include Discord user and server IDs, member profiles, current roles, and public primary-guild information (source server ID, tag and whether the identity is displayed).

The role decision uses the public primary-guild information and current roles. The tag must belong to the server being monitored and match the configured text, ignoring case. The bot checks new members and member updates, runs a reconciliation at startup and daily, and supports a manual `/scan`.

The bot requests these Gateway intents:

- **Guilds**: server and role information.
- **Server Members** (privileged): member lists, joins and member updates, including changes to the public primary guild.

It does not request **Presence** or **Message Content**. It does not subscribe to message, reaction, typing or voice events, and does not use messages, games, activities, online status or connection histories for its functionality.

## Data Stored

The local SQLite database, `data/bot_data.db`, stores:

- Server configuration: server ID, configured tag, configured role IDs, monitoring state and configuration timestamps.
- Daily statistics: server ID, date, number of members displaying the matching tag, and total member count. These are aggregate counts, without user IDs or an individual tag history.
- A pending deletion marker identifying the server if cleanup must be retried. It is removed when cleanup succeeds.

Member profiles, user IDs, individual roles and individual tag decisions are processed in memory, not written to the application database. The application logs operational events and error categories without Discord IDs, names, tag text, role values or raw API payloads. Raw library logs and exception details are excluded from the application's log output, including at `DEBUG` level. Host, container or infrastructure logs are controlled by the hosting operator separately. Earlier releases could log Discord IDs; updating the application does not erase historical logs, which the operator must delete or expire separately.

Automatic database snapshots may be created in `data/backups/`. They contain the same categories of stored data as the live database.

## Purposes and Access

The data is used to synchronize configured roles, answer the bot's commands, show aggregate tag statistics, recover the database and diagnose operational failures.

Configuration and statistics are scoped to the current server. Management commands require Discord's **Manage Roles** permission, checked when the command runs. `/botstats` is restricted to the bot owner.

Discord receives the API requests needed to operate the bot. The operator and technical hosting providers may access the infrastructure used to run it. The bot does not sell data or send it to advertising, analytics or other external application services.

## Retention and Deletion

- Configuration is kept until `/reset` is completed or the bot's departure from the server is processed. At startup, the bot also removes data for servers it has left while offline.
- The statistics window contains at most 365 daily dates, including the current UTC date. Expired records are removed during startup and hourly maintenance while the bot is running, including from managed local backups.
- Managed local backups are limited by both age and count: files dated seven or more days before the current UTC date are removed during maintenance, and at most `BACKUP_KEEP` files are kept (default: 7). Older modification timestamps can cause earlier expiry. Hourly retention maintenance still runs when new backups are disabled. An offline process cannot perform maintenance; it resumes on startup.
- `/reset` and departure cleanup delete that server's configuration and statistics from the live database and all managed local backups. The bot reports a command failure if deletion cannot be completed. A scan that was running cannot recreate deleted records after a successful reset.
- Copies created outside `data/backups/`, such as host snapshots or manually exported databases, are outside the bot's control. The operator must apply deletion and retention to those copies as well, and avoid restoring deleted data.

## Controls and Requests

Members with **Manage Roles** can inspect the server's configuration with `/status`, view aggregate counts with `/stats`, stop monitoring with `/toggle`, and delete stored server data with `/reset`. Disabling monitoring or resetting waits for any role operation already in progress to finish and stops subsequent processing for that configuration. These commands leave roles already assigned in Discord in place.

Disabling monitoring is not an individual opt-out from Discord delivering member information. The Discord library can still receive and cache member data while the bot remains installed. There is no per-member opt-out command. Removing or hiding the public tag changes role eligibility but does not prevent Discord from delivering member updates. Removing the bot ends its access to the server.

For questions or a manual access or deletion request, open an issue in the [project's GitHub issue tracker](https://github.com/QTBG/PickTag2GetRole/issues). Issues are public: describe the request without posting tokens, encryption keys, private member data or database files. For a separately hosted instance, contact its operator as well.

## Security

`ENCRYPTION_KEY` is required. The bot refuses to start with a missing, malformed or incompatible key. Stored server IDs, tag text, role IDs and aggregate counts are encrypted with Fernet (AES-128-CBC and HMAC-SHA256). Server lookups use a keyed HMAC index instead of a plaintext Discord ID.

This is application-level field encryption. Table structure, dates, configuration timestamps, monitoring state, row counts and pseudonymous lookup indexes remain visible in the SQLite files. The database is not an entirely opaque encrypted file. The key must be protected separately from the data volume.

Existing database files and managed local backups are migrated before normal operation; incomplete migration prevents startup. Filesystem permissions and hosting security remain the operator's responsibility. Source code is available in the [public repository](https://github.com/QTBG/PickTag2GetRole).

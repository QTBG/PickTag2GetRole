# Terms of Service - PickTag2GetRole Bot

*Last updated: July 2026*

## 1. Acceptance
By adding PickTag2GetRole to your Discord server, you agree to these terms.

## 2. Service Description
PickTag2GetRole monitors Discord server tags (primary guild tags) and automatically assigns/removes roles based on tag presence.

## 3. Required Permissions and Intents

Discord permissions requested when inviting the bot:
- **Manage Roles** — to assign and remove the configured roles
- **View Channels** — to access the server

Discord gateway intents the bot subscribes to:
- **Guilds** — server and role information
- **Server Members** (privileged) — member list and member updates, used for role assignment and scans
- **Presences** (privileged) — required to detect server tag (primary guild) changes in real time

The bot requests no message-related permission or intent. See the [Privacy Policy](PRIVACY_POLICY.md) for how this data is used.

## 4. Acceptable Use
- Use the bot only for legitimate role management
- Do not attempt to exploit or abuse the bot
- Comply with Discord's Terms of Service
- Ensure proper role hierarchy (bot role must be higher than managed roles)

## 5. Limitations
- Bot can only manage roles lower than its own role
- Tag monitoring requires users to have their server identity publicly displayed
- Bot responds to changes in real-time via Discord events
- A safety verification of all members runs at startup and once daily
- If a server's configuration cannot match any member (for example a role mention entered in the tag field), monitoring is paused for that server and no role is modified until an administrator corrects it

## 6. Data Handling
See our [Privacy Policy](PRIVACY_POLICY.md) for detailed information.

## 7. No Warranty
The bot is provided "as is" without any guarantees of uptime or functionality.

## 8. Open Source
This is an open-source project under MIT License. You can self-host for full control.

## 9. Changes
We may update these terms or the bot functionality at any time.

## 10. Termination
We reserve the right to terminate service for abuse or Discord ToS violations.

## 11. Contact
Issues or questions: https://github.com/QTBG/PickTag2GetRole
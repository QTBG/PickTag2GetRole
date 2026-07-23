import discord
from discord import app_commands
from discord.ext import commands
import logging
import math
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

from database import STATS_RETENTION_DAYS
from i18n import t

logger = logging.getLogger('PickTag2GetRole.Commands')

ROLE_MENTION_RE = re.compile(r'<@&(\d+)>')
MAX_TAG_LENGTH = 32
MAX_ROLES = 15
SPARK_BLOCKS = '▁▂▃▄▅▆▇█'

def _get_rss_mb() -> float | None:
    """Mémoire résidente actuelle du process en Mo (Linux uniquement)"""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        pass
    return None

def _sparkline(values: list[int]) -> str:
    """Mini-graphe en blocs Unicode"""
    if not values:
        return ''
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK_BLOCKS[3] * len(values)
    return ''.join(SPARK_BLOCKS[round((v - lo) / (hi - lo) * 7)] for v in values)

class ConfigCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="config", description="Configure the bot to monitor a server tag")
    @app_commands.describe(
        tag="The server tag to monitor",
        roles="Roles to assign (mention roles separated by spaces)"
    )
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def config(self, interaction: discord.Interaction, tag: str, roles: str):
        """Configure the tag to monitor and roles to assign"""
        locale = interaction.locale
        tag = tag.strip()
        if not tag or len(tag) > MAX_TAG_LENGTH:
            await interaction.response.send_message(
                t(locale, 'config.invalid_tag', max=MAX_TAG_LENGTH),
                ephemeral=True
            )
            return

        guild = interaction.guild
        invoker = interaction.user
        is_owner = guild.owner_id == invoker.id

        # Parser les rôles mentionnés et vérifier la hiérarchie :
        # personne ne doit pouvoir faire distribuer par le bot un rôle
        # qu'il ne pourrait pas attribuer lui-même à la main.
        role_ids = []
        role_names = []
        rejected = []
        seen = set()

        for role_id_str in ROLE_MENTION_RE.findall(roles):
            role_id = int(role_id_str)
            if role_id in seen:
                continue
            seen.add(role_id)

            role = guild.get_role(role_id)
            if role is None:
                continue
            if role.is_default() or role.managed:
                rejected.append(f"{role.name} — {t(locale, 'config.reject_managed')}")
                continue
            if role >= guild.me.top_role:
                rejected.append(f"{role.name} — {t(locale, 'config.reject_above_bot')}")
                continue
            if not is_owner and role >= invoker.top_role:
                rejected.append(f"{role.name} — {t(locale, 'config.reject_above_you')}")
                continue
            role_ids.append(role_id)
            role_names.append(role.name)

        if len(role_ids) > MAX_ROLES:
            await interaction.response.send_message(
                t(locale, 'config.too_many_roles', count=len(role_ids), max=MAX_ROLES),
                ephemeral=True
            )
            return

        if not role_ids:
            message = t(locale, 'config.no_valid_roles')
            if rejected:
                message += "\n\n" + t(locale, 'config.rejected_header') + "\n" + \
                    "\n".join(f"• {r}" for r in rejected)
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Sauvegarder la configuration
        config = {
            'tag_to_watch': tag,
            'role_ids': role_ids,
            'enabled': True
        }

        await self.bot.set_guild_config(interaction.guild.id, config)

        # Réponse
        embed = discord.Embed(
            title=t(locale, 'config.updated_title'),
            color=discord.Color.green(),
            description=t(locale, 'config.updated_desc', tag=tag)
        )
        embed.add_field(
            name=t(locale, 'config.roles_field'),
            value="\n".join([f"• {name}" for name in role_names]),
            inline=False
        )
        if rejected:
            embed.add_field(
                name=t(locale, 'config.ignored_field'),
                value="\n".join([f"• {r}" for r in rejected]),
                inline=False
            )
        if not guild.me.guild_permissions.manage_roles:
            embed.add_field(
                name=t(locale, 'config.missing_perm_field'),
                value=t(locale, 'config.missing_perm_text'),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Charger le cache des membres pour la détection temps réel (après la réponse
        # pour ne pas la retarder sur les gros serveurs)
        tag_monitor = self.bot.get_cog('TagMonitor')
        if tag_monitor:
            await tag_monitor.ensure_chunked(guild)

    @app_commands.command(name="reset", description="Delete this server's configuration and stored data")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def reset(self, interaction: discord.Interaction):
        """Delete all stored data for this server"""
        locale = interaction.locale
        config = await self.bot.get_guild_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                t(locale, 'common.no_config'),
                ephemeral=True
            )
            return

        await self.bot.db.delete_guild_config(interaction.guild.id)
        async with self.bot.cache_lock:
            self.bot.config_cache.pop(interaction.guild.id, None)

        tag_monitor = self.bot.get_cog('TagMonitor')
        if tag_monitor:
            tag_monitor.member_cache.pop(interaction.guild.id, None)

        await interaction.response.send_message(t(locale, 'reset.done'), ephemeral=True)

    @app_commands.command(name="status", description="View the current bot configuration")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        """Display current configuration"""
        locale = interaction.locale
        config = await self.bot.get_guild_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                t(locale, 'status.no_config'),
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=t(locale, 'status.title'),
            color=discord.Color.blue()
        )

        embed.add_field(
            name=t(locale, 'status.monitored_tag'),
            value=config.get('tag_to_watch') or t(locale, 'status.not_set'),
            inline=False
        )

        role_ids = config.get('role_ids', [])
        if role_ids:
            role_names = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_names.append(role.name)
                else:
                    role_names.append(t(locale, 'status.deleted_role', id=role_id))

            embed.add_field(
                name=t(locale, 'status.assigned_roles'),
                value="\n".join([f"• {name}" for name in role_names]),
                inline=False
            )
        else:
            embed.add_field(
                name=t(locale, 'status.roles'),
                value=t(locale, 'status.no_roles'),
                inline=False
            )

        tag_monitor = self.bot.get_cog('TagMonitor')
        tagged_count = tag_monitor.get_tagged_count(interaction.guild.id) if tag_monitor else None
        if tagged_count is not None:
            embed.add_field(
                name=t(locale, 'status.members_with_tag'),
                value=t(locale, 'status.as_of_last_scan', count=tagged_count),
                inline=False
            )

        embed.add_field(
            name=t(locale, 'status.status'),
            value=t(locale, 'status.enabled') if config.get('enabled', False)
            else t(locale, 'status.disabled'),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="toggle", description="Enable or disable tag monitoring")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def toggle(self, interaction: discord.Interaction):
        """Enable/disable the bot for this server"""
        locale = interaction.locale
        config = await self.bot.get_guild_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                t(locale, 'toggle.no_config'),
                ephemeral=True
            )
            return

        # Inverser l'état
        config['enabled'] = not config.get('enabled', False)
        await self.bot.set_guild_config(interaction.guild.id, config)

        message_key = 'toggle.enabled_msg' if config['enabled'] else 'toggle.disabled_msg'
        await interaction.response.send_message(t(locale, message_key), ephemeral=True)

        if config['enabled']:
            tag_monitor = self.bot.get_cog('TagMonitor')
            if tag_monitor:
                await tag_monitor.ensure_chunked(interaction.guild)

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Display help for all commands"""
        locale = interaction.locale
        embed = discord.Embed(
            title=t(locale, 'help.title'),
            description=t(locale, 'help.desc'),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="/config `tag` `@role1 @role2...`",
            value=t(locale, 'help.config'),
            inline=False
        )
        embed.add_field(name="/status", value=t(locale, 'help.status'), inline=False)
        embed.add_field(name="/toggle", value=t(locale, 'help.toggle'), inline=False)
        embed.add_field(name="/scan", value=t(locale, 'help.scan'), inline=False)
        embed.add_field(name="/check `@member`", value=t(locale, 'help.check'), inline=False)
        embed.add_field(name="/stats", value=t(locale, 'help.stats'), inline=False)
        embed.add_field(name="/reset", value=t(locale, 'help.reset'), inline=False)
        embed.add_field(name="/help", value=t(locale, 'help.help'), inline=False)

        embed.set_footer(text=t(locale, 'help.footer'))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="scan", description="Manually scan all members now")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.guild_id)
    async def scan(self, interaction: discord.Interaction):
        """Force an immediate scan of all members"""
        locale = interaction.locale
        config = await self.bot.get_guild_config(interaction.guild.id)

        if not config or not config.get('enabled', False):
            await interaction.response.send_message(
                t(locale, 'scan.not_enabled'),
                ephemeral=True
            )
            return

        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])

        if not tag_to_watch or not role_ids:
            await interaction.response.send_message(
                t(locale, 'scan.incomplete'),
                ephemeral=True
            )
            return

        # Obtenir le cog TagMonitor
        tag_monitor = self.bot.get_cog('TagMonitor')
        if not tag_monitor:
            await interaction.response.send_message(
                t(locale, 'scan.module_missing'),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(f"Starting manual scan for guild {interaction.guild.id}")
        stats = await tag_monitor.scan_guild(interaction.guild, tag_to_watch, role_ids)

        if stats is None:
            await interaction.followup.send(t(locale, 'scan.in_progress'), ephemeral=True)
            return

        embed = discord.Embed(
            title=t(locale, 'scan.done_title'),
            color=discord.Color.green(),
            description=t(locale, 'scan.done_desc',
                          checked=stats['checked'], tagged=stats['tagged'],
                          updated=stats['updated'], tag=tag_to_watch)
        )

        logger.info(f"Manual scan completed for guild {interaction.guild.id}: "
                    f"{stats['checked']} scanned, {stats['tagged']} with tag, {stats['updated']} updated")

        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.HTTPException:
            # Le token d'interaction expire après 15 min : sur un très gros serveur,
            # le scan peut durer plus longtemps. Le résultat reste dans les logs.
            pass

    @app_commands.command(name="check", description="Check a specific member's tag status")
    @app_commands.describe(member="The member to check")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def check_member(self, interaction: discord.Interaction, member: discord.Member):
        """Check if a specific member has the configured tag"""
        locale = interaction.locale
        config = await self.bot.get_guild_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                t(locale, 'common.no_config'),
                ephemeral=True
            )
            return

        tag_to_watch = config.get('tag_to_watch') or t(locale, 'status.not_set')

        embed = discord.Embed(
            title=t(locale, 'check.title', name=member.name),
            color=discord.Color.blue()
        )

        embed.add_field(name=t(locale, 'check.looking_for'), value=tag_to_watch, inline=False)

        # Vérifier primary_guild
        if hasattr(member, 'primary_guild'):
            pg = member.primary_guild
            if pg:
                none_text = t(locale, 'check.none')
                embed.add_field(name="Primary Guild ID", value=pg.id or none_text, inline=True)
                embed.add_field(name="Primary Guild Tag", value=pg.tag or none_text, inline=True)
                embed.add_field(name=t(locale, 'check.identity'),
                                value=str(pg.identity_enabled), inline=True)

                # Vérifier si le tag correspond
                tag_monitor = self.bot.get_cog('TagMonitor')
                if tag_monitor and config.get('tag_to_watch'):
                    has_tag = tag_monitor._member_has_tag(member, config['tag_to_watch'])
                    embed.add_field(
                        name=t(locale, 'check.has_matching'),
                        value=t(locale, 'check.yes') if has_tag else t(locale, 'check.no'),
                        inline=False
                    )
            else:
                embed.add_field(name="Primary Guild", value=t(locale, 'check.none'), inline=False)
        else:
            embed.add_field(name=t(locale, 'check.error'),
                            value=t(locale, 'check.attr_missing'), inline=False)

        # Afficher les rôles actuels
        role_ids = config.get('role_ids', [])
        if role_ids:
            assigned_roles = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    assigned_roles.append(role.name)

            embed.add_field(
                name=t(locale, 'check.current_roles'),
                value=", ".join(assigned_roles) if assigned_roles else t(locale, 'check.none'),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="View tag statistics for this server")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def stats(self, interaction: discord.Interaction):
        """Evolution of tagged member counts for this server"""
        locale = interaction.locale
        rows = await self.bot.db.get_tag_stats(interaction.guild.id, days=30)

        if not rows:
            await interaction.response.send_message(t(locale, 'stats.no_data'), ephemeral=True)
            return

        latest = rows[-1]
        today = datetime.now(timezone.utc).date()

        def change_text(days_back: int) -> str:
            target = today - timedelta(days=days_back)
            baseline = None
            for row in rows:
                if date.fromisoformat(row['date']) <= target:
                    baseline = row
                else:
                    break
            if baseline is None or baseline['date'] == latest['date']:
                return t(locale, 'stats.no_baseline')
            diff = latest['tagged'] - baseline['tagged']
            sign = '+' if diff > 0 else ''
            return f"{sign}{diff} ({baseline['tagged']} → {latest['tagged']})"

        embed = discord.Embed(title=t(locale, 'stats.title'), color=discord.Color.blurple())
        embed.add_field(
            name=t(locale, 'stats.members'),
            value=f"{latest['tagged']} ({latest['date']})",
            inline=False
        )
        embed.add_field(name=t(locale, 'stats.change_7d'), value=change_text(7), inline=True)
        embed.add_field(name=t(locale, 'stats.change_30d'), value=change_text(30), inline=True)

        values = [row['tagged'] for row in rows[-14:]]
        if len(values) >= 2:
            embed.add_field(
                name=t(locale, 'stats.trend', days=len(values)),
                value=f"`{_sparkline(values)}` {min(values)}–{max(values)}",
                inline=False
            )

        embed.set_footer(text=t(locale, 'stats.footer', days=STATS_RETENTION_DAYS))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="botstats", description="Global bot statistics (bot owner only)")
    @app_commands.default_permissions(administrator=True)
    async def botstats(self, interaction: discord.Interaction):
        """Global statistics, restricted to the bot owner"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                t(interaction.locale, 'botstats.owner_only'),
                ephemeral=True
            )
            return

        guilds = self.bot.guilds
        total_members = sum(g.member_count or 0 for g in guilds)
        cached_members = sum(len(g.members) for g in guilds)
        enabled_count = len(self.bot.config_cache)

        tag_monitor = self.bot.get_cog('TagMonitor')
        tracked_tagged = sum(len(s) for s in tag_monitor.member_cache.values()) if tag_monitor else 0
        scanned_guilds = len(tag_monitor.member_cache) if tag_monitor else 0
        chunking = tag_monitor.chunking_enabled if tag_monitor else False

        uptime = timedelta(seconds=int(time.monotonic() - self.bot.start_time))
        latency = self.bot.latency
        latency_text = f"{round(latency * 1000)} ms" if math.isfinite(latency) else "n/a"

        rss_mb = _get_rss_mb()
        try:
            db_size_kb = os.path.getsize(self.bot.db.db_path) / 1024
            db_text = f"{db_size_kb:.0f} KB"
        except OSError:
            db_text = "n/a"

        embed = discord.Embed(
            title="📈 Bot statistics",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Servers", value=f"{len(guilds)}", inline=True)
        embed.add_field(name="Monitoring enabled", value=f"{enabled_count}", inline=True)
        embed.add_field(name="Members (total reach)", value=f"{total_members:,}", inline=True)
        embed.add_field(
            name="Tagged members tracked",
            value=f"{tracked_tagged:,} (across {scanned_guilds} scanned servers)",
            inline=False
        )
        embed.add_field(name="Cached members", value=f"{cached_members:,}", inline=True)
        embed.add_field(name="Chunking", value="enabled" if chunking else "disabled", inline=True)
        embed.add_field(name="Uptime", value=str(uptime), inline=True)
        embed.add_field(name="Latency", value=latency_text, inline=True)
        embed.add_field(name="Memory (RSS)", value=f"{rss_mb:.1f} MB" if rss_mb is not None else "n/a", inline=True)
        embed.add_field(name="Database size", value=db_text, inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigCommands(bot))

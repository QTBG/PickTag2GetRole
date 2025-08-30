import discord
from discord import app_commands
from discord.ext import commands
from typing import List

class ConfigCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config", description="Configure the bot to monitor a server tag")
    @app_commands.describe(
        tag="The server tag to monitor",
        roles="Roles to assign (mention roles separated by spaces)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def config(self, interaction: discord.Interaction, tag: str, roles: str):
        """Configure the tag to monitor and roles to assign"""
        # Vérifier les permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You must have the Manage Roles permission to use this command.",
                ephemeral=True
            )
            return
        
        # Parser les rôles mentionnés
        role_mentions = roles.split()
        role_ids = []
        role_names = []
        
        for mention in role_mentions:
            # Extraire l'ID du rôle depuis la mention
            if mention.startswith('<@&') and mention.endswith('>'):
                role_id = int(mention[3:-1])
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
                    role_names.append(role.name)
        
        if not role_ids:
            await interaction.response.send_message(
                "❌ No valid roles found. Please mention roles with @.",
                ephemeral=True
            )
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
            title="✅ Configuration updated",
            color=discord.Color.green(),
            description=f"The bot will now monitor the tag **{tag}**"
        )
        embed.add_field(
            name="Roles to assign",
            value="\n".join([f"• {name}" for name in role_names]),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="status", description="View the current bot configuration")
    @app_commands.default_permissions(manage_roles=True)
    async def status(self, interaction: discord.Interaction):
        """Display current configuration"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ No configuration found for this server. Use `/config` to configure the bot.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Current configuration",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Monitored tag",
            value=config.get('tag_to_watch', 'Not set'),
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
                    role_names.append(f"Deleted role (ID: {role_id})")
            
            embed.add_field(
                name="Assigned roles",
                value="\n".join([f"• {name}" for name in role_names]),
                inline=False
            )
        else:
            embed.add_field(name="Roles", value="No roles configured", inline=False)
        
        embed.add_field(
            name="Status",
            value="✅ Enabled" if config.get('enabled', False) else "❌ Disabled",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="toggle", description="Enable or disable tag monitoring")
    @app_commands.default_permissions(manage_roles=True)
    async def toggle(self, interaction: discord.Interaction):
        """Enable/disable the bot for this server"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ No configuration found. Use `/config` first.",
                ephemeral=True
            )
            return
        
        # Inverser l'état
        config['enabled'] = not config.get('enabled', False)
        await self.bot.set_guild_config(interaction.guild.id, config)
        
        status = "✅ enabled" if config['enabled'] else "❌ disabled"
        await interaction.response.send_message(
            f"Tag monitoring has been {status}.",
            ephemeral=True
        )
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Display help for all commands"""
        embed = discord.Embed(
            title="📚 PickTag2GetRole - Commands",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="/config `tag` `@role1 @role2...`",
            value="Configure the bot to monitor a specific server tag and assign roles to members who have it.",
            inline=False
        )
        
        embed.add_field(
            name="/status",
            value="View the current configuration (monitored tag, assigned roles, enabled/disabled status).",
            inline=False
        )
        
        embed.add_field(
            name="/toggle",
            value="Enable or disable tag monitoring for this server.",
            inline=False
        )
        
        embed.add_field(
            name="/scan",
            value="Manually scan all server members and update their roles based on the current configuration.",
            inline=False
        )
        
        embed.add_field(
            name="/help",
            value="Show this help message.",
            inline=False
        )
        
        embed.set_footer(text="Note: Most commands require the 'Manage Roles' permission.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="scan", description="Manually scan all members now")
    @app_commands.default_permissions(manage_roles=True)
    async def scan(self, interaction: discord.Interaction):
        """Force an immediate scan of all members"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config or not config.get('enabled', False):
            await interaction.response.send_message(
                "❌ The bot is not enabled for this server. Use `/toggle` to enable it.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            await interaction.followup.send(
                "❌ Incomplete configuration. Please reconfigure with `/config`.",
                ephemeral=True
            )
            return
        
        # Obtenir le cog TagMonitor
        tag_monitor = self.bot.get_cog('TagMonitor')
        if not tag_monitor:
            await interaction.followup.send(
                "❌ Monitoring module not loaded.",
                ephemeral=True
            )
            return
        
        # Scanner tous les membres
        members_updated = 0
        total_members = 0
        
        async for member in interaction.guild.fetch_members(limit=None):
            total_members += 1
            has_tag = tag_monitor._member_has_tag(member, tag_to_watch)
            
            # Vérifier si le membre doit avoir les rôles
            needs_update = False
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    has_role = role in member.roles
                    if has_tag and not has_role:
                        needs_update = True
                    elif not has_tag and has_role:
                        needs_update = True
            
            if needs_update:
                await tag_monitor._update_member_roles(member, has_tag, role_ids)
                members_updated += 1
        
        embed = discord.Embed(
            title="✅ Scan completed",
            color=discord.Color.green(),
            description=f"**{total_members}** members scanned\n**{members_updated}** members updated"
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigCommands(bot))
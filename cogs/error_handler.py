import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger('PickTag2GetRole.ErrorHandler')

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.on_error = self.on_app_command_error
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for application commands"""
        
        # If the interaction was already responded to, we can't send a normal response
        if interaction.response.is_done():
            send_func = interaction.followup.send
        else:
            send_func = interaction.response.send_message
        
        if isinstance(error, app_commands.TransformerError):
            # Handle member conversion errors
            if str(error.type) == "<class 'discord.member.Member'>":
                await send_func(
                    f"❌ Could not find member: **{error.value}**\n"
                    "Please make sure to:\n"
                    "• Use the member's mention (@username)\n"
                    "• Or select from the autocomplete suggestions\n"
                    "• The member must be in this server",
                    ephemeral=True
                )
                return
        
        elif isinstance(error, app_commands.CommandInvokeError):
            original_error = error.original
            
            if isinstance(original_error, AttributeError) and "'User' object has no attribute 'guild_permissions'" in str(original_error):
                await send_func(
                    "❌ This command can only be used in a server, not in DMs.",
                    ephemeral=True
                )
                return
            
            # Log the error
            logger.error(f"Command error in {interaction.command.name}: {original_error}", exc_info=original_error)
            
            await send_func(
                f"❌ An error occurred while executing the command: {type(original_error).__name__}\n"
                f"Please contact an administrator if this persists.",
                ephemeral=True
            )
        
        elif isinstance(error, app_commands.MissingPermissions):
            await send_func(
                f"❌ You don't have the required permissions to use this command.\n"
                f"Required: {', '.join(error.missing_permissions)}",
                ephemeral=True
            )
        
        elif isinstance(error, app_commands.BotMissingPermissions):
            await send_func(
                f"❌ I don't have the required permissions to execute this command.\n"
                f"Required: {', '.join(error.missing_permissions)}",
                ephemeral=True
            )
        
        else:
            # Log unexpected errors
            logger.error(f"Unexpected error in {interaction.command.name}: {error}", exc_info=error)
            
            await send_func(
                "❌ An unexpected error occurred. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
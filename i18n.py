"""Localisation des commandes et réponses du bot.

Deux mécanismes :
- COMMAND_LOCALIZATIONS + CommandTranslator : descriptions de commandes/paramètres,
  envoyées à Discord lors de la synchronisation (localisation native des slash commands).
- RESPONSES + t() : textes de réponse à l'exécution, choisis selon interaction.locale.

Tout est statique et en mémoire : aucune dépendance, coût CPU/RAM négligeable.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

logger = logging.getLogger('PickTag2GetRole.i18n')

DEFAULT_LOCALE = 'en'
SUPPORTED_LOCALES = {'en', 'fr', 'es', 'de', 'it', 'pt-BR'}


def normalize_locale(locale) -> str:
    """Ramener un discord.Locale (ou None) vers une clé de table supportée."""
    if locale is None:
        return DEFAULT_LOCALE
    code = str(locale)
    if code in SUPPORTED_LOCALES:
        return code
    base = code.split('-')[0].lower()
    if base in SUPPORTED_LOCALES:
        return base
    return DEFAULT_LOCALE


def t(locale, key: str, **kwargs) -> str:
    """Traduire une clé de réponse pour la locale donnée (repli sur l'anglais)."""
    entry = RESPONSES.get(key)
    if entry is None:
        logger.warning("Missing i18n key: %s", key)
        return key
    text = entry.get(normalize_locale(locale)) or entry[DEFAULT_LOCALE]
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return entry[DEFAULT_LOCALE].format(**kwargs)
    return text


class CommandTranslator(app_commands.Translator):
    """Traducteur des métadonnées de commandes (appelé par discord.py au sync)."""

    async def translate(self, string: app_commands.locale_str, locale: discord.Locale,
                        context) -> Optional[str]:
        code = normalize_locale(locale)
        if code == DEFAULT_LOCALE:
            return None
        return COMMAND_LOCALIZATIONS.get(string.message, {}).get(code)


# Descriptions des commandes et paramètres (clé = texte source anglais).
# Limite Discord : 100 caractères par description.
COMMAND_LOCALIZATIONS: dict[str, dict[str, str]] = {
    "Configure the bot to monitor a server tag": {
        'fr': "Configurer le bot pour surveiller un tag de serveur",
        'es': "Configurar el bot para supervisar una etiqueta del servidor",
        'de': "Den Bot einrichten, um einen Server-Tag zu überwachen",
        'it': "Configura il bot per monitorare un tag del server",
        'pt-BR': "Configurar o bot para monitorar uma tag do servidor",
    },
    "The server tag to monitor": {
        'fr': "Le tag de serveur à surveiller",
        'es': "La etiqueta del servidor a supervisar",
        'de': "Der zu überwachende Server-Tag",
        'it': "Il tag del server da monitorare",
        'pt-BR': "A tag do servidor a monitorar",
    },
    "Roles to assign (mention roles separated by spaces)": {
        'fr': "Rôles à attribuer (mentionnez les rôles séparés par des espaces)",
        'es': "Roles a asignar (menciona los roles separados por espacios)",
        'de': "Zu vergebende Rollen (Rollen durch Leerzeichen getrennt erwähnen)",
        'it': "Ruoli da assegnare (menziona i ruoli separati da spazi)",
        'pt-BR': "Cargos a atribuir (mencione os cargos separados por espaços)",
    },
    "View the current bot configuration": {
        'fr': "Afficher la configuration actuelle du bot",
        'es': "Ver la configuración actual del bot",
        'de': "Die aktuelle Bot-Konfiguration anzeigen",
        'it': "Mostra la configurazione attuale del bot",
        'pt-BR': "Ver a configuração atual do bot",
    },
    "Enable or disable tag monitoring": {
        'fr': "Activer ou désactiver la surveillance des tags",
        'es': "Activar o desactivar la supervisión de etiquetas",
        'de': "Tag-Überwachung aktivieren oder deaktivieren",
        'it': "Attiva o disattiva il monitoraggio dei tag",
        'pt-BR': "Ativar ou desativar o monitoramento de tags",
    },
    "Show all available commands": {
        'fr': "Afficher toutes les commandes disponibles",
        'es': "Mostrar todos los comandos disponibles",
        'de': "Alle verfügbaren Befehle anzeigen",
        'it': "Mostra tutti i comandi disponibili",
        'pt-BR': "Mostrar todos os comandos disponíveis",
    },
    "Manually scan all members now": {
        'fr': "Scanner manuellement tous les membres maintenant",
        'es': "Escanear manualmente a todos los miembros ahora",
        'de': "Alle Mitglieder jetzt manuell scannen",
        'it': "Scansiona manualmente tutti i membri adesso",
        'pt-BR': "Escanear manualmente todos os membros agora",
    },
    "Check a specific member's tag status": {
        'fr': "Vérifier le statut du tag d'un membre",
        'es': "Comprobar el estado de la etiqueta de un miembro",
        'de': "Tag-Status eines Mitglieds prüfen",
        'it': "Verifica lo stato del tag di un membro",
        'pt-BR': "Verificar o status da tag de um membro",
    },
    "The member to check": {
        'fr': "Le membre à vérifier",
        'es': "El miembro a comprobar",
        'de': "Das zu prüfende Mitglied",
        'it': "Il membro da verificare",
        'pt-BR': "O membro a verificar",
    },
    "Delete this server's configuration and stored data": {
        'fr': "Supprimer la configuration et les données stockées de ce serveur",
        'es': "Eliminar la configuración y los datos guardados de este servidor",
        'de': "Konfiguration und gespeicherte Daten dieses Servers löschen",
        'it': "Elimina la configurazione e i dati salvati di questo server",
        'pt-BR': "Excluir a configuração e os dados armazenados deste servidor",
    },
    "View tag statistics for this server": {
        'fr': "Afficher les statistiques du tag pour ce serveur",
        'es': "Ver las estadísticas de la etiqueta de este servidor",
        'de': "Tag-Statistiken für diesen Server anzeigen",
        'it': "Mostra le statistiche del tag per questo server",
        'pt-BR': "Ver as estatísticas da tag deste servidor",
    },
    "Global bot statistics (bot owner only)": {
        'fr': "Statistiques globales du bot (propriétaire uniquement)",
        'es': "Estadísticas globales del bot (solo propietario)",
        'de': "Globale Bot-Statistiken (nur Bot-Besitzer)",
        'it': "Statistiche globali del bot (solo proprietario)",
        'pt-BR': "Estatísticas globais do bot (somente o dono)",
    },
}


# Textes de réponse à l'exécution (clé -> locale -> texte). 'en' est obligatoire.
RESPONSES: dict[str, dict[str, str]] = {
    # ---- Erreurs générales (bot.py) ----
    'err.cooldown': {
        'en': "⏳ This command is on cooldown. Try again in {seconds}s.",
        'fr': "⏳ Cette commande est en cooldown. Réessayez dans {seconds}s.",
        'es': "⏳ Este comando está en enfriamiento. Inténtalo de nuevo en {seconds}s.",
        'de': "⏳ Dieser Befehl hat eine Abklingzeit. Versuche es in {seconds}s erneut.",
        'it': "⏳ Questo comando è in cooldown. Riprova tra {seconds}s.",
        'pt-BR': "⏳ Este comando está em cooldown. Tente novamente em {seconds}s.",
    },
    'err.guild_only': {
        'en': "❌ This command can only be used in a server, not in DMs.",
        'fr': "❌ Cette commande ne peut être utilisée que sur un serveur, pas en MP.",
        'es': "❌ Este comando solo puede usarse en un servidor, no en mensajes directos.",
        'de': "❌ Dieser Befehl kann nur auf einem Server verwendet werden, nicht in DMs.",
        'it': "❌ Questo comando può essere usato solo in un server, non nei DM.",
        'pt-BR': "❌ Este comando só pode ser usado em um servidor, não em DMs.",
    },
    'err.not_allowed': {
        'en': "❌ You are not allowed to use this command.",
        'fr': "❌ Vous n'êtes pas autorisé à utiliser cette commande.",
        'es': "❌ No tienes permiso para usar este comando.",
        'de': "❌ Du darfst diesen Befehl nicht verwenden.",
        'it': "❌ Non sei autorizzato a usare questo comando.",
        'pt-BR': "❌ Você não tem permissão para usar este comando.",
    },
    'err.generic': {
        'en': "❌ An error occurred while executing the command.",
        'fr': "❌ Une erreur est survenue lors de l'exécution de la commande.",
        'es': "❌ Ocurrió un error al ejecutar el comando.",
        'de': "❌ Beim Ausführen des Befehls ist ein Fehler aufgetreten.",
        'it': "❌ Si è verificato un errore durante l'esecuzione del comando.",
        'pt-BR': "❌ Ocorreu um erro ao executar o comando.",
    },
    'common.no_config': {
        'en': "❌ No configuration found for this server.",
        'fr': "❌ Aucune configuration trouvée pour ce serveur.",
        'es': "❌ No se encontró configuración para este servidor.",
        'de': "❌ Keine Konfiguration für diesen Server gefunden.",
        'it': "❌ Nessuna configurazione trovata per questo server.",
        'pt-BR': "❌ Nenhuma configuração encontrada para este servidor.",
    },

    # ---- /config ----
    'config.invalid_tag': {
        'en': "❌ Invalid tag. It must be between 1 and {max} characters.",
        'fr': "❌ Tag invalide. Il doit faire entre 1 et {max} caractères.",
        'es': "❌ Etiqueta no válida. Debe tener entre 1 y {max} caracteres.",
        'de': "❌ Ungültiger Tag. Er muss zwischen 1 und {max} Zeichen lang sein.",
        'it': "❌ Tag non valido. Deve essere lungo tra 1 e {max} caratteri.",
        'pt-BR': "❌ Tag inválida. Deve ter entre 1 e {max} caracteres.",
    },
    'config.tag_is_mention': {
        'en': "❌ That looks like a **role mention**, not a server tag.\n\n"
              "The `tag` field expects your server's short TAG — the 2-4 characters shown next to "
              "member names — while roles go in the `roles` field.\n\n"
              "Example: `/config tag:VIP roles:@VIP-Member`",
        'fr': "❌ Ceci ressemble à une **mention de rôle**, pas à un tag de serveur.\n\n"
              "Le champ `tag` attend le TAG court de votre serveur — les 2 à 4 caractères affichés "
              "à côté des pseudos — tandis que les rôles vont dans le champ `roles`.\n\n"
              "Exemple : `/config tag:VIP roles:@Membre-VIP`",
        'es': "❌ Eso parece una **mención de rol**, no una etiqueta de servidor.\n\n"
              "El campo `tag` espera la ETIQUETA corta de tu servidor — los 2-4 caracteres que "
              "aparecen junto a los nombres — mientras que los roles van en el campo `roles`.\n\n"
              "Ejemplo: `/config tag:VIP roles:@Miembro-VIP`",
        'de': "❌ Das sieht nach einer **Rollen-Erwähnung** aus, nicht nach einem Server-Tag.\n\n"
              "Das Feld `tag` erwartet den kurzen TAG deines Servers — die 2-4 Zeichen neben den "
              "Mitgliedsnamen — Rollen gehören ins Feld `roles`.\n\n"
              "Beispiel: `/config tag:VIP roles:@VIP-Mitglied`",
        'it': "❌ Sembra una **menzione di ruolo**, non un tag del server.\n\n"
              "Il campo `tag` richiede il TAG breve del tuo server — i 2-4 caratteri mostrati "
              "accanto ai nomi — mentre i ruoli vanno nel campo `roles`.\n\n"
              "Esempio: `/config tag:VIP roles:@Membro-VIP`",
        'pt-BR': "❌ Isso parece uma **menção de cargo**, não uma tag do servidor.\n\n"
                 "O campo `tag` espera a TAG curta do seu servidor — os 2-4 caracteres exibidos ao "
                 "lado dos nomes — enquanto os cargos vão no campo `roles`.\n\n"
                 "Exemplo: `/config tag:VIP roles:@Membro-VIP`",
    },
    'config.tag_long_warning_field': {
        'en': "⚠️ This tag looks too long",
        'fr': "⚠️ Ce tag semble trop long",
        'es': "⚠️ Esta etiqueta parece demasiado larga",
        'de': "⚠️ Dieser Tag wirkt zu lang",
        'it': "⚠️ Questo tag sembra troppo lungo",
        'pt-BR': "⚠️ Esta tag parece longa demais",
    },
    'config.tag_long_warning_text': {
        'en': "Discord server tags are at most {max} characters. Yours is {length}, so it may never "
              "match anyone. Double-check it with `/check @member`.",
        'fr': "Les tags de serveur Discord font au maximum {max} caractères. Le vôtre en fait {length}, "
              "il risque de ne jamais correspondre. Vérifiez-le avec `/check @membre`.",
        'es': "Las etiquetas de servidor de Discord tienen como máximo {max} caracteres. La tuya tiene "
              "{length}, así que puede que nunca coincida. Compruébalo con `/check @miembro`.",
        'de': "Discord-Server-Tags haben höchstens {max} Zeichen. Deiner hat {length} und passt "
              "möglicherweise nie. Prüfe ihn mit `/check @Mitglied`.",
        'it': "I tag del server Discord hanno al massimo {max} caratteri. Il tuo ne ha {length}, quindi "
              "potrebbe non corrispondere mai. Verificalo con `/check @membro`.",
        'pt-BR': "As tags de servidor do Discord têm no máximo {max} caracteres. A sua tem {length}, "
                 "então pode nunca corresponder. Confira com `/check @membro`.",
    },
    'status.invalid_tag_field': {
        'en': "🚫 Invalid tag — monitoring paused",
        'fr': "🚫 Tag invalide — surveillance en pause",
        'es': "🚫 Etiqueta no válida — supervisión en pausa",
        'de': "🚫 Ungültiger Tag — Überwachung pausiert",
        'it': "🚫 Tag non valido — monitoraggio in pausa",
        'pt-BR': "🚫 Tag inválida — monitoramento pausado",
    },
    'status.invalid_tag_text': {
        'en': "The configured tag is a mention, not a server tag, so it can never match. The bot is "
              "**not** touching any roles until you fix it with `/config`.",
        'fr': "Le tag configuré est une mention, pas un tag de serveur : il ne peut jamais correspondre. "
              "Le bot ne touche à **aucun** rôle tant que vous ne le corrigez pas avec `/config`.",
        'es': "La etiqueta configurada es una mención, no una etiqueta de servidor, así que nunca puede "
              "coincidir. El bot **no** toca ningún rol hasta que lo corrijas con `/config`.",
        'de': "Der konfigurierte Tag ist eine Erwähnung und kein Server-Tag, er kann also nie passen. "
              "Der Bot ändert **keine** Rollen, bis du das mit `/config` korrigierst.",
        'it': "Il tag configurato è una menzione, non un tag del server, quindi non può mai corrispondere. "
              "Il bot **non** tocca alcun ruolo finché non lo correggi con `/config`.",
        'pt-BR': "A tag configurada é uma menção, não uma tag de servidor, então nunca vai corresponder. "
                 "O bot **não** mexe em nenhum cargo até você corrigir com `/config`.",
    },
    'status.permission_field': {
        'en': "⚠️ Missing permissions",
        'fr': "⚠️ Permissions insuffisantes",
        'es': "⚠️ Permisos insuficientes",
        'de': "⚠️ Fehlende Berechtigungen",
        'it': "⚠️ Permessi insufficienti",
        'pt-BR': "⚠️ Permissões insuficientes",
    },
    'status.permission_text': {
        'en': "I couldn't update roles for {count} member(s) since the last scan. Move my role **above** "
              "the configured roles in Server Settings → Roles, and check I have **Manage Roles**.",
        'fr': "Je n'ai pas pu mettre à jour les rôles de {count} membre(s) depuis le dernier scan. Placez mon "
              "rôle **au-dessus** des rôles configurés dans Paramètres du serveur → Rôles, et vérifiez que "
              "j'ai la permission **Gérer les rôles**.",
        'es': "No pude actualizar los roles de {count} miembro(s) desde el último escaneo. Sube mi rol **por "
              "encima** de los roles configurados en Ajustes del servidor → Roles y comprueba que tengo "
              "**Gestionar roles**.",
        'de': "Ich konnte die Rollen von {count} Mitglied(ern) seit dem letzten Scan nicht ändern. Verschiebe "
              "meine Rolle in den Servereinstellungen → Rollen **über** die konfigurierten Rollen und prüfe "
              "die Berechtigung **Rollen verwalten**.",
        'it': "Non ho potuto aggiornare i ruoli di {count} membro/i dall'ultima scansione. Sposta il mio "
              "ruolo **sopra** i ruoli configurati in Impostazioni server → Ruoli e verifica che io abbia "
              "**Gestire i ruoli**.",
        'pt-BR': "Não consegui atualizar os cargos de {count} membro(s) desde o último escaneamento. Mova meu cargo "
                 "**acima** dos cargos configurados em Configurações do servidor → Cargos e confira se tenho "
                 "**Gerenciar cargos**.",
    },
    'config.too_many_roles': {
        'en': "❌ Too many roles ({count}). Maximum is {max}.",
        'fr': "❌ Trop de rôles ({count}). Le maximum est {max}.",
        'es': "❌ Demasiados roles ({count}). El máximo es {max}.",
        'de': "❌ Zu viele Rollen ({count}). Maximal erlaubt: {max}.",
        'it': "❌ Troppi ruoli ({count}). Il massimo è {max}.",
        'pt-BR': "❌ Muitos cargos ({count}). O máximo é {max}.",
    },
    'config.no_valid_roles': {
        'en': "❌ No valid roles found. Please mention roles with @.",
        'fr': "❌ Aucun rôle valide trouvé. Merci de mentionner les rôles avec @.",
        'es': "❌ No se encontraron roles válidos. Menciona los roles con @.",
        'de': "❌ Keine gültigen Rollen gefunden. Bitte erwähne Rollen mit @.",
        'it': "❌ Nessun ruolo valido trovato. Menziona i ruoli con @.",
        'pt-BR': "❌ Nenhum cargo válido encontrado. Mencione os cargos com @.",
    },
    'config.rejected_header': {
        'en': "Rejected roles:",
        'fr': "Rôles refusés :",
        'es': "Roles rechazados:",
        'de': "Abgelehnte Rollen:",
        'it': "Ruoli rifiutati:",
        'pt-BR': "Cargos recusados:",
    },
    'config.reject_managed': {
        'en': "cannot be assigned by a bot",
        'fr': "ne peut pas être attribué par un bot",
        'es': "no puede ser asignado por un bot",
        'de': "kann nicht von einem Bot vergeben werden",
        'it': "non può essere assegnato da un bot",
        'pt-BR': "não pode ser atribuído por um bot",
    },
    'config.reject_above_bot': {
        'en': "higher than or equal to my highest role — move my role above it in Server Settings → Roles",
        'fr': "supérieur ou égal à mon rôle le plus élevé — placez mon rôle au-dessus dans Paramètres du serveur → Rôles",
        'es': "superior o igual a mi rol más alto: sube mi rol por encima en Ajustes del servidor → Roles",
        'de': "höher oder gleich meiner höchsten Rolle — verschiebe meine Rolle in Servereinstellungen → Rollen nach oben",
        'it': "superiore o uguale al mio ruolo più alto — sposta il mio ruolo più in alto in Impostazioni server → Ruoli",
        'pt-BR': "superior ou igual ao meu cargo mais alto — mova meu cargo para cima em Configurações do servidor → Cargos",
    },
    'config.reject_above_you': {
        'en': "higher than or equal to your highest role",
        'fr': "supérieur ou égal à votre rôle le plus élevé",
        'es': "superior o igual a tu rol más alto",
        'de': "höher oder gleich deiner höchsten Rolle",
        'it': "superiore o uguale al tuo ruolo più alto",
        'pt-BR': "superior ou igual ao seu cargo mais alto",
    },
    'config.updated_title': {
        'en': "✅ Configuration updated",
        'fr': "✅ Configuration mise à jour",
        'es': "✅ Configuración actualizada",
        'de': "✅ Konfiguration aktualisiert",
        'it': "✅ Configurazione aggiornata",
        'pt-BR': "✅ Configuração atualizada",
    },
    'config.updated_desc': {
        'en': "The bot will now monitor the tag **{tag}**",
        'fr': "Le bot surveille désormais le tag **{tag}**",
        'es': "El bot ahora supervisará la etiqueta **{tag}**",
        'de': "Der Bot überwacht jetzt den Tag **{tag}**",
        'it': "Il bot ora monitorerà il tag **{tag}**",
        'pt-BR': "O bot agora vai monitorar a tag **{tag}**",
    },
    'config.roles_field': {
        'en': "Roles to assign",
        'fr': "Rôles à attribuer",
        'es': "Roles a asignar",
        'de': "Zu vergebende Rollen",
        'it': "Ruoli da assegnare",
        'pt-BR': "Cargos a atribuir",
    },
    'config.ignored_field': {
        'en': "⚠️ Ignored roles",
        'fr': "⚠️ Rôles ignorés",
        'es': "⚠️ Roles ignorados",
        'de': "⚠️ Ignorierte Rollen",
        'it': "⚠️ Ruoli ignorati",
        'pt-BR': "⚠️ Cargos ignorados",
    },
    'config.missing_perm_field': {
        'en': "⚠️ Missing permission",
        'fr': "⚠️ Permission manquante",
        'es': "⚠️ Permiso faltante",
        'de': "⚠️ Fehlende Berechtigung",
        'it': "⚠️ Permesso mancante",
        'pt-BR': "⚠️ Permissão ausente",
    },
    'config.missing_perm_text': {
        'en': "I don't have the **Manage Roles** permission, so I won't be able to assign anything.",
        'fr': "Je n'ai pas la permission **Gérer les rôles**, je ne pourrai donc rien attribuer.",
        'es': "No tengo el permiso **Gestionar roles**, así que no podré asignar nada.",
        'de': "Mir fehlt die Berechtigung **Rollen verwalten**, daher kann ich nichts vergeben.",
        'it': "Non ho il permesso **Gestire i ruoli**, quindi non potrò assegnare nulla.",
        'pt-BR': "Não tenho a permissão **Gerenciar cargos**, então não poderei atribuir nada.",
    },

    # ---- /reset ----
    'reset.done': {
        'en': "🗑️ Configuration deleted. The bot no longer stores any data for this server.\n"
              "Note: roles previously assigned by the bot are **not** removed.",
        'fr': "🗑️ Configuration supprimée. Le bot ne stocke plus aucune donnée pour ce serveur.\n"
              "Note : les rôles déjà attribués par le bot ne sont **pas** retirés.",
        'es': "🗑️ Configuración eliminada. El bot ya no almacena ningún dato de este servidor.\n"
              "Nota: los roles ya asignados por el bot **no** se retiran.",
        'de': "🗑️ Konfiguration gelöscht. Der Bot speichert keine Daten mehr für diesen Server.\n"
              "Hinweis: Bereits vergebene Rollen werden **nicht** entfernt.",
        'it': "🗑️ Configurazione eliminata. Il bot non conserva più alcun dato per questo server.\n"
              "Nota: i ruoli già assegnati dal bot **non** vengono rimossi.",
        'pt-BR': "🗑️ Configuração excluída. O bot não armazena mais nenhum dado deste servidor.\n"
                 "Obs.: os cargos já atribuídos pelo bot **não** são removidos.",
    },

    # ---- /status ----
    'status.no_config': {
        'en': "❌ No configuration found for this server. Use `/config` to configure the bot.",
        'fr': "❌ Aucune configuration trouvée pour ce serveur. Utilisez `/config` pour configurer le bot.",
        'es': "❌ No se encontró configuración para este servidor. Usa `/config` para configurar el bot.",
        'de': "❌ Keine Konfiguration für diesen Server gefunden. Verwende `/config`, um den Bot einzurichten.",
        'it': "❌ Nessuna configurazione trovata per questo server. Usa `/config` per configurare il bot.",
        'pt-BR': "❌ Nenhuma configuração encontrada para este servidor. Use `/config` para configurar o bot.",
    },
    'status.title': {
        'en': "📊 Current configuration",
        'fr': "📊 Configuration actuelle",
        'es': "📊 Configuración actual",
        'de': "📊 Aktuelle Konfiguration",
        'it': "📊 Configurazione attuale",
        'pt-BR': "📊 Configuração atual",
    },
    'status.monitored_tag': {
        'en': "Monitored tag",
        'fr': "Tag surveillé",
        'es': "Etiqueta supervisada",
        'de': "Überwachter Tag",
        'it': "Tag monitorato",
        'pt-BR': "Tag monitorada",
    },
    'status.not_set': {
        'en': "Not set",
        'fr': "Non défini",
        'es': "Sin definir",
        'de': "Nicht festgelegt",
        'it': "Non impostato",
        'pt-BR': "Não definida",
    },
    'status.deleted_role': {
        'en': "Deleted role (ID: {id})",
        'fr': "Rôle supprimé (ID : {id})",
        'es': "Rol eliminado (ID: {id})",
        'de': "Gelöschte Rolle (ID: {id})",
        'it': "Ruolo eliminato (ID: {id})",
        'pt-BR': "Cargo excluído (ID: {id})",
    },
    'status.assigned_roles': {
        'en': "Assigned roles",
        'fr': "Rôles attribués",
        'es': "Roles asignados",
        'de': "Vergebene Rollen",
        'it': "Ruoli assegnati",
        'pt-BR': "Cargos atribuídos",
    },
    'status.roles': {
        'en': "Roles",
        'fr': "Rôles",
        'es': "Roles",
        'de': "Rollen",
        'it': "Ruoli",
        'pt-BR': "Cargos",
    },
    'status.no_roles': {
        'en': "No roles configured",
        'fr': "Aucun rôle configuré",
        'es': "No hay roles configurados",
        'de': "Keine Rollen konfiguriert",
        'it': "Nessun ruolo configurato",
        'pt-BR': "Nenhum cargo configurado",
    },
    'status.members_with_tag': {
        'en': "Members with tag",
        'fr': "Membres avec le tag",
        'es': "Miembros con la etiqueta",
        'de': "Mitglieder mit Tag",
        'it': "Membri con il tag",
        'pt-BR': "Membros com a tag",
    },
    'status.as_of_last_scan': {
        'en': "{count} (as of last scan)",
        'fr': "{count} (au dernier scan)",
        'es': "{count} (según el último escaneo)",
        'de': "{count} (Stand: letzter Scan)",
        'it': "{count} (all'ultima scansione)",
        'pt-BR': "{count} (no último escaneamento)",
    },
    'status.status': {
        'en': "Status",
        'fr': "Statut",
        'es': "Estado",
        'de': "Status",
        'it': "Stato",
        'pt-BR': "Status",
    },
    'status.enabled': {
        'en': "✅ Enabled",
        'fr': "✅ Activé",
        'es': "✅ Activado",
        'de': "✅ Aktiviert",
        'it': "✅ Attivato",
        'pt-BR': "✅ Ativado",
    },
    'status.disabled': {
        'en': "❌ Disabled",
        'fr': "❌ Désactivé",
        'es': "❌ Desactivado",
        'de': "❌ Deaktiviert",
        'it': "❌ Disattivato",
        'pt-BR': "❌ Desativado",
    },

    # ---- /toggle ----
    'toggle.no_config': {
        'en': "❌ No configuration found. Use `/config` first.",
        'fr': "❌ Aucune configuration trouvée. Utilisez d'abord `/config`.",
        'es': "❌ No se encontró configuración. Usa `/config` primero.",
        'de': "❌ Keine Konfiguration gefunden. Verwende zuerst `/config`.",
        'it': "❌ Nessuna configurazione trovata. Usa prima `/config`.",
        'pt-BR': "❌ Nenhuma configuração encontrada. Use `/config` primeiro.",
    },
    'toggle.enabled_msg': {
        'en': "✅ Tag monitoring has been enabled.",
        'fr': "✅ La surveillance des tags a été activée.",
        'es': "✅ La supervisión de etiquetas ha sido activada.",
        'de': "✅ Die Tag-Überwachung wurde aktiviert.",
        'it': "✅ Il monitoraggio dei tag è stato attivato.",
        'pt-BR': "✅ O monitoramento de tags foi ativado.",
    },
    'toggle.disabled_msg': {
        'en': "❌ Tag monitoring has been disabled.",
        'fr': "❌ La surveillance des tags a été désactivée.",
        'es': "❌ La supervisión de etiquetas ha sido desactivada.",
        'de': "❌ Die Tag-Überwachung wurde deaktiviert.",
        'it': "❌ Il monitoraggio dei tag è stato disattivato.",
        'pt-BR': "❌ O monitoramento de tags foi desativado.",
    },

    # ---- /help ----
    'help.title': {
        'en': "📚 PickTag2GetRole - Commands",
        'fr': "📚 PickTag2GetRole - Commandes",
        'es': "📚 PickTag2GetRole - Comandos",
        'de': "📚 PickTag2GetRole - Befehle",
        'it': "📚 PickTag2GetRole - Comandi",
        'pt-BR': "📚 PickTag2GetRole - Comandos",
    },
    'help.desc': {
        'en': "Here are all available commands:",
        'fr': "Voici toutes les commandes disponibles :",
        'es': "Estos son todos los comandos disponibles:",
        'de': "Hier sind alle verfügbaren Befehle:",
        'it': "Ecco tutti i comandi disponibili:",
        'pt-BR': "Aqui estão todos os comandos disponíveis:",
    },
    'help.config': {
        'en': "Configure the bot to monitor a specific server tag and assign roles to members who have it.",
        'fr': "Configure le bot pour surveiller un tag de serveur et attribuer des rôles aux membres qui l'ont.",
        'es': "Configura el bot para supervisar una etiqueta del servidor y asignar roles a quienes la tienen.",
        'de': "Richtet den Bot ein, um einen Server-Tag zu überwachen und Mitgliedern mit Tag Rollen zu geben.",
        'it': "Configura il bot per monitorare un tag del server e assegnare ruoli ai membri che lo hanno.",
        'pt-BR': "Configura o bot para monitorar uma tag do servidor e atribuir cargos a quem a tiver.",
    },
    'help.status': {
        'en': "View the current configuration (monitored tag, assigned roles, enabled/disabled status).",
        'fr': "Affiche la configuration actuelle (tag surveillé, rôles attribués, statut activé/désactivé).",
        'es': "Muestra la configuración actual (etiqueta supervisada, roles asignados, estado).",
        'de': "Zeigt die aktuelle Konfiguration (überwachter Tag, vergebene Rollen, Status).",
        'it': "Mostra la configurazione attuale (tag monitorato, ruoli assegnati, stato).",
        'pt-BR': "Mostra a configuração atual (tag monitorada, cargos atribuídos, status).",
    },
    'help.toggle': {
        'en': "Enable or disable tag monitoring for this server.",
        'fr': "Active ou désactive la surveillance des tags pour ce serveur.",
        'es': "Activa o desactiva la supervisión de etiquetas en este servidor.",
        'de': "Aktiviert oder deaktiviert die Tag-Überwachung für diesen Server.",
        'it': "Attiva o disattiva il monitoraggio dei tag per questo server.",
        'pt-BR': "Ativa ou desativa o monitoramento de tags neste servidor.",
    },
    'help.scan': {
        'en': "Manually scan all server members and update their roles based on the current configuration.",
        'fr': "Scanne manuellement tous les membres du serveur et met à jour leurs rôles selon la configuration.",
        'es': "Escanea manualmente a todos los miembros y actualiza sus roles según la configuración actual.",
        'de': "Scannt alle Servermitglieder manuell und aktualisiert ihre Rollen gemäß der Konfiguration.",
        'it': "Scansiona manualmente tutti i membri del server e aggiorna i loro ruoli secondo la configurazione.",
        'pt-BR': "Escaneia manualmente todos os membros do servidor e atualiza seus cargos conforme a configuração.",
    },
    'help.check': {
        'en': "Check a specific member's tag status and see if they should have the configured roles.",
        'fr': "Vérifie le statut du tag d'un membre et s'il devrait avoir les rôles configurés.",
        'es': "Comprueba el estado de la etiqueta de un miembro y si debería tener los roles configurados.",
        'de': "Prüft den Tag-Status eines Mitglieds und ob es die konfigurierten Rollen haben sollte.",
        'it': "Verifica lo stato del tag di un membro e se dovrebbe avere i ruoli configurati.",
        'pt-BR': "Verifica o status da tag de um membro e se ele deveria ter os cargos configurados.",
    },
    'help.stats': {
        'en': "View the evolution of members with the tag over time.",
        'fr': "Affiche l'évolution du nombre de membres avec le tag dans le temps.",
        'es': "Muestra la evolución del número de miembros con la etiqueta a lo largo del tiempo.",
        'de': "Zeigt die Entwicklung der Mitglieder mit Tag im Zeitverlauf.",
        'it': "Mostra l'evoluzione dei membri con il tag nel tempo.",
        'pt-BR': "Mostra a evolução do número de membros com a tag ao longo do tempo.",
    },
    'help.reset': {
        'en': "Delete this server's configuration and all data stored by the bot.",
        'fr': "Supprime la configuration de ce serveur et toutes les données stockées par le bot.",
        'es': "Elimina la configuración de este servidor y todos los datos guardados por el bot.",
        'de': "Löscht die Konfiguration dieses Servers und alle vom Bot gespeicherten Daten.",
        'it': "Elimina la configurazione di questo server e tutti i dati salvati dal bot.",
        'pt-BR': "Exclui a configuração deste servidor e todos os dados armazenados pelo bot.",
    },
    'help.help': {
        'en': "Show this help message.",
        'fr': "Affiche ce message d'aide.",
        'es': "Muestra este mensaje de ayuda.",
        'de': "Zeigt diese Hilfenachricht an.",
        'it': "Mostra questo messaggio di aiuto.",
        'pt-BR': "Mostra esta mensagem de ajuda.",
    },
    'help.legal_field': {
        'en': "📜 Privacy & Terms",
        'fr': "📜 Confidentialité et conditions",
        'es': "📜 Privacidad y condiciones",
        'de': "📜 Datenschutz und Nutzungsbedingungen",
        'it': "📜 Privacy e termini",
        'pt-BR': "📜 Privacidade e termos",
    },
    'help.privacy_link': {
        'en': "Privacy Policy",
        'fr': "Politique de confidentialité",
        'es': "Política de privacidad",
        'de': "Datenschutzerklärung",
        'it': "Informativa sulla privacy",
        'pt-BR': "Política de privacidade",
    },
    'help.terms_link': {
        'en': "Terms of Service",
        'fr': "Conditions d'utilisation",
        'es': "Términos del servicio",
        'de': "Nutzungsbedingungen",
        'it': "Termini di servizio",
        'pt-BR': "Termos de serviço",
    },
    'help.footer': {
        'en': "Note: Most commands require the 'Manage Roles' permission.",
        'fr': "Note : la plupart des commandes nécessitent la permission « Gérer les rôles ».",
        'es': "Nota: la mayoría de los comandos requieren el permiso «Gestionar roles».",
        'de': "Hinweis: Die meisten Befehle erfordern die Berechtigung „Rollen verwalten“.",
        'it': "Nota: la maggior parte dei comandi richiede il permesso «Gestire i ruoli».",
        'pt-BR': "Obs.: a maioria dos comandos exige a permissão “Gerenciar cargos”.",
    },

    # ---- /scan ----
    'scan.not_enabled': {
        'en': "❌ The bot is not enabled for this server. Use `/toggle` to enable it.",
        'fr': "❌ Le bot n'est pas activé sur ce serveur. Utilisez `/toggle` pour l'activer.",
        'es': "❌ El bot no está activado en este servidor. Usa `/toggle` para activarlo.",
        'de': "❌ Der Bot ist auf diesem Server nicht aktiviert. Verwende `/toggle`, um ihn zu aktivieren.",
        'it': "❌ Il bot non è attivato su questo server. Usa `/toggle` per attivarlo.",
        'pt-BR': "❌ O bot não está ativado neste servidor. Use `/toggle` para ativá-lo.",
    },
    'scan.incomplete': {
        'en': "❌ Incomplete configuration. Please reconfigure with `/config`.",
        'fr': "❌ Configuration incomplète. Merci de reconfigurer avec `/config`.",
        'es': "❌ Configuración incompleta. Reconfigura con `/config`.",
        'de': "❌ Unvollständige Konfiguration. Bitte richte den Bot mit `/config` neu ein.",
        'it': "❌ Configurazione incompleta. Riconfigura con `/config`.",
        'pt-BR': "❌ Configuração incompleta. Reconfigure com `/config`.",
    },
    'scan.module_missing': {
        'en': "❌ Monitoring module not loaded.",
        'fr': "❌ Module de surveillance non chargé.",
        'es': "❌ Módulo de supervisión no cargado.",
        'de': "❌ Überwachungsmodul nicht geladen.",
        'it': "❌ Modulo di monitoraggio non caricato.",
        'pt-BR': "❌ Módulo de monitoramento não carregado.",
    },
    'scan.in_progress': {
        'en': "⏳ A scan is already in progress for this server. Please wait for it to finish.",
        'fr': "⏳ Un scan est déjà en cours pour ce serveur. Merci d'attendre qu'il se termine.",
        'es': "⏳ Ya hay un escaneo en curso para este servidor. Espera a que termine.",
        'de': "⏳ Für diesen Server läuft bereits ein Scan. Bitte warte, bis er abgeschlossen ist.",
        'it': "⏳ Una scansione è già in corso per questo server. Attendi che finisca.",
        'pt-BR': "⏳ Já existe um escaneamento em andamento para este servidor. Aguarde a conclusão.",
    },
    'scan.done_title': {
        'en': "✅ Scan completed",
        'fr': "✅ Scan terminé",
        'es': "✅ Escaneo completado",
        'de': "✅ Scan abgeschlossen",
        'it': "✅ Scansione completata",
        'pt-BR': "✅ Escaneamento concluído",
    },
    'scan.done_desc': {
        'en': "**{checked}** members scanned\n**{tagged}** members with tag '{tag}'\n**{updated}** members updated",
        'fr': "**{checked}** membres scannés\n**{tagged}** membres avec le tag '{tag}'\n**{updated}** membres mis à jour",
        'es': "**{checked}** miembros escaneados\n**{tagged}** miembros con la etiqueta '{tag}'\n**{updated}** miembros actualizados",
        'de': "**{checked}** Mitglieder gescannt\n**{tagged}** Mitglieder mit Tag '{tag}'\n**{updated}** Mitglieder aktualisiert",
        'it': "**{checked}** membri scansionati\n**{tagged}** membri con il tag '{tag}'\n**{updated}** membri aggiornati",
        'pt-BR': "**{checked}** membros escaneados\n**{tagged}** membros com a tag '{tag}'\n**{updated}** membros atualizados",
    },

    # ---- /check ----
    'check.title': {
        'en': "🔍 Tag check for {name}",
        'fr': "🔍 Vérification du tag de {name}",
        'es': "🔍 Comprobación de etiqueta de {name}",
        'de': "🔍 Tag-Prüfung für {name}",
        'it': "🔍 Verifica del tag di {name}",
        'pt-BR': "🔍 Verificação de tag de {name}",
    },
    'check.looking_for': {
        'en': "Looking for tag",
        'fr': "Tag recherché",
        'es': "Etiqueta buscada",
        'de': "Gesuchter Tag",
        'it': "Tag cercato",
        'pt-BR': "Tag procurada",
    },
    'check.identity': {
        'en': "Identity Enabled",
        'fr': "Identité affichée",
        'es': "Identidad visible",
        'de': "Identität sichtbar",
        'it': "Identità visibile",
        'pt-BR': "Identidade visível",
    },
    'check.has_matching': {
        'en': "Has matching tag?",
        'fr': "Tag correspondant ?",
        'es': "¿Etiqueta coincidente?",
        'de': "Passender Tag?",
        'it': "Tag corrispondente?",
        'pt-BR': "Tag correspondente?",
    },
    'check.yes': {
        'en': "✅ Yes",
        'fr': "✅ Oui",
        'es': "✅ Sí",
        'de': "✅ Ja",
        'it': "✅ Sì",
        'pt-BR': "✅ Sim",
    },
    'check.no': {
        'en': "❌ No",
        'fr': "❌ Non",
        'es': "❌ No",
        'de': "❌ Nein",
        'it': "❌ No",
        'pt-BR': "❌ Não",
    },
    'check.none': {
        'en': "None",
        'fr': "Aucun",
        'es': "Ninguno",
        'de': "Keine",
        'it': "Nessuno",
        'pt-BR': "Nenhum",
    },
    'check.attr_missing': {
        'en': "Primary guild attribute not found. Check discord.py version.",
        'fr': "Attribut primary_guild introuvable. Vérifiez la version de discord.py.",
        'es': "No se encontró el atributo primary_guild. Comprueba la versión de discord.py.",
        'de': "Attribut primary_guild nicht gefunden. Prüfe die discord.py-Version.",
        'it': "Attributo primary_guild non trovato. Controlla la versione di discord.py.",
        'pt-BR': "Atributo primary_guild não encontrado. Verifique a versão do discord.py.",
    },
    'check.current_roles': {
        'en': "Currently has configured roles",
        'fr': "Rôles configurés actuellement possédés",
        'es': "Roles configurados que ya tiene",
        'de': "Bereits vorhandene konfigurierte Rollen",
        'it': "Ruoli configurati già posseduti",
        'pt-BR': "Cargos configurados que já possui",
    },
    'check.error': {
        'en': "Error",
        'fr': "Erreur",
        'es': "Error",
        'de': "Fehler",
        'it': "Errore",
        'pt-BR': "Erro",
    },

    # ---- /stats ----
    'stats.title': {
        'en': "📈 Tag statistics",
        'fr': "📈 Statistiques du tag",
        'es': "📈 Estadísticas de la etiqueta",
        'de': "📈 Tag-Statistiken",
        'it': "📈 Statistiche del tag",
        'pt-BR': "📈 Estatísticas da tag",
    },
    'stats.no_data': {
        'en': "❌ No statistics yet. They are recorded after each scan (daily or `/scan`).",
        'fr': "❌ Pas encore de statistiques. Elles sont enregistrées après chaque scan (quotidien ou `/scan`).",
        'es': "❌ Aún no hay estadísticas. Se registran después de cada escaneo (diario o `/scan`).",
        'de': "❌ Noch keine Statistiken. Sie werden nach jedem Scan erfasst (täglich oder `/scan`).",
        'it': "❌ Ancora nessuna statistica. Vengono registrate dopo ogni scansione (giornaliera o `/scan`).",
        'pt-BR': "❌ Ainda não há estatísticas. Elas são registradas após cada escaneamento (diário ou `/scan`).",
    },
    'stats.members': {
        'en': "Members with tag",
        'fr': "Membres avec le tag",
        'es': "Miembros con la etiqueta",
        'de': "Mitglieder mit Tag",
        'it': "Membri con il tag",
        'pt-BR': "Membros com a tag",
    },
    'stats.change_7d': {
        'en': "7-day change",
        'fr': "Évolution sur 7 jours",
        'es': "Cambio en 7 días",
        'de': "Veränderung (7 Tage)",
        'it': "Variazione a 7 giorni",
        'pt-BR': "Variação em 7 dias",
    },
    'stats.change_30d': {
        'en': "30-day change",
        'fr': "Évolution sur 30 jours",
        'es': "Cambio en 30 días",
        'de': "Veränderung (30 Tage)",
        'it': "Variazione a 30 giorni",
        'pt-BR': "Variação em 30 dias",
    },
    'stats.no_baseline': {
        'en': "no data",
        'fr': "pas de données",
        'es': "sin datos",
        'de': "keine Daten",
        'it': "nessun dato",
        'pt-BR': "sem dados",
    },
    'stats.trend': {
        'en': "Last {days} days",
        'fr': "{days} derniers jours",
        'es': "Últimos {days} días",
        'de': "Letzte {days} Tage",
        'it': "Ultimi {days} giorni",
        'pt-BR': "Últimos {days} dias",
    },
    'stats.footer': {
        'en': "Recorded once per day after each scan. History kept for {days} days.",
        'fr': "Enregistré une fois par jour après chaque scan. Historique conservé {days} jours.",
        'es': "Se registra una vez al día tras cada escaneo. Historial conservado {days} días.",
        'de': "Einmal täglich nach jedem Scan erfasst. Verlauf wird {days} Tage aufbewahrt.",
        'it': "Registrato una volta al giorno dopo ogni scansione. Cronologia conservata per {days} giorni.",
        'pt-BR': "Registrado uma vez por dia após cada escaneamento. Histórico mantido por {days} dias.",
    },

    # ---- /botstats ----
    'botstats.owner_only': {
        'en': "❌ This command is restricted to the bot owner.",
        'fr': "❌ Cette commande est réservée au propriétaire du bot.",
        'es': "❌ Este comando está reservado al propietario del bot.",
        'de': "❌ Dieser Befehl ist dem Bot-Besitzer vorbehalten.",
        'it': "❌ Questo comando è riservato al proprietario del bot.",
        'pt-BR': "❌ Este comando é restrito ao dono do bot.",
    },
}

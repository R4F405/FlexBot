import discord # type: ignore
from discord.ext import commands # type: ignore
import datetime
import json
import os
import asyncio

class Reports(commands.Cog):
    """
    Sistema de reportes para el servidor.
    Permite a los usuarios reportar problemas o a otros usuarios.
    """

    def __init__(self, bot):
        self.bot = bot
        self.reports_file = 'data/reports.json'
        self.pending_actions = {}  # Para almacenar acciones pendientes
        self.load_reports()

    def load_reports(self):
        """Cargar reportes existentes o crear archivo si no existe"""
        if not os.path.exists('data'):
            os.makedirs('data')
        
        if os.path.exists(self.reports_file):
            with open(self.reports_file, 'r') as f:
                self.reports = json.load(f)
        else:
            self.reports = {}
            self.save_reports()

    def save_reports(self):
        """Guardar reportes en el archivo"""
        with open(self.reports_file, 'w') as f:
            json.dump(self.reports, f, indent=4)

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        """
        Reporta a un usuario por comportamiento inadecuado.

        Parámetros:
        -----------
        member: discord.Member
            El usuario a reportar
        reason: str
            La razón del reporte

        Ejemplo:
        --------
        !flex report @usuario Spam en el canal general
        """
        # Evitar auto-reportes
        if member.id == ctx.author.id:
            await ctx.send("No puedes reportarte a ti mismo.")
            return

        # Evitar reportar al bot
        if member.id == self.bot.user.id:
            await ctx.send("No puedes reportar al bot.")
            return

        # Crear reporte
        report_data = {
            "reported_user": member.id,
            "reported_by": ctx.author.id,
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "pendiente",
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id
        }

        # Guardar reporte
        server_id = str(ctx.guild.id)
        if server_id not in self.reports:
            self.reports[server_id] = []
        
        self.reports[server_id].append(report_data)
        self.save_reports()

        # Enviar confirmación al usuario
        await ctx.message.delete()  # Eliminar el mensaje del reporte
        confirm = await ctx.send(f"{ctx.author.mention}, tu reporte ha sido enviado y será revisado por el equipo de moderación.", delete_after=10)

        # Buscar o crear canal de reportes
        reports_channel = discord.utils.get(ctx.guild.channels, name="reportes")
        if not reports_channel:
            # Crear categoría si no existe
            category = discord.utils.get(ctx.guild.categories, name="Moderación")
            if not category:
                category = await ctx.guild.create_category("Moderación")

            # Crear canal de reportes con permisos restringidos
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True),
                ctx.guild.get_role(ctx.guild.id): discord.PermissionOverwrite(read_messages=False)
            }
            
            # Dar acceso a roles con permiso de moderación
            for role in ctx.guild.roles:
                if role.permissions.manage_messages:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)

            reports_channel = await ctx.guild.create_text_channel(
                'reportes',
                category=category,
                overwrites=overwrites,
                topic="Canal para reportes de usuarios"
            )

        # Crear embed para el reporte
        embed = discord.Embed(
            title="Nuevo Reporte",
            description=f"Se ha reportado a un usuario",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.add_field(name="Usuario Reportado", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Reportado por", value=f"{ctx.author.mention} ({ctx.author.id})", inline=False)
        embed.add_field(name="Razón", value=reason, inline=False)
        embed.add_field(name="Canal", value=f"{ctx.channel.mention}", inline=False)
        
        # Añadir explicación de las reacciones
        embed.add_field(
            name="Acciones Disponibles",
            value=(
                "Reacciona con:\n"
                "✅ - Marcar reporte como resuelto\n"
                "❌ - Descartar reporte\n"
                "🔨 - Mostrar opciones de moderación (silenciar/expulsar/banear)"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"ID del Reporte: {len(self.reports[server_id])}")

        # Añadir botones de acción
        report_msg = await reports_channel.send(embed=embed)
        await report_msg.add_reaction("✅")
        await report_msg.add_reaction("❌")
        await report_msg.add_reaction("🔨")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def reports(self, ctx, status: str = "pendiente"):
        """
        Muestra los reportes según su estado.

        Parámetros:
        -----------
        status: str, opcional
            Estado de los reportes a mostrar: "pendiente", "resuelto" o "todos"

        Ejemplo:
        --------
        !flex reports pendiente
        !flex reports resuelto
        !flex reports todos
        """
        server_id = str(ctx.guild.id)
        if server_id not in self.reports or not self.reports[server_id]:
            await ctx.send("No hay reportes registrados en este servidor.")
            return

        reports_list = self.reports[server_id]
        if status != "todos":
            reports_list = [r for r in reports_list if r["status"] == status]

        if not reports_list:
            await ctx.send(f"No hay reportes {status}s.")
            return

        # Crear embed con la lista de reportes
        embed = discord.Embed(
            title=f"Reportes {status.title()}s",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )

        for i, report in enumerate(reports_list[-10:], 1):  # Mostrar solo los últimos 10 reportes
            reported_user = ctx.guild.get_member(report["reported_user"])
            reporter = ctx.guild.get_member(report["reported_by"])
            
            if reported_user and reporter:
                embed.add_field(
                    name=f"Reporte #{i}",
                    value=f"**Usuario:** {reported_user.mention}\n"
                          f"**Reportado por:** {reporter.mention}\n"
                          f"**Razón:** {report['reason']}\n"
                          f"**Estado:** {report['status']}\n"
                          f"**Fecha:** {datetime.datetime.fromisoformat(report['timestamp']).strftime('%d/%m/%Y %H:%M')}",
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Manejar reacciones en los reportes"""
        if payload.member.bot:
            return

        # Verificar si es un canal de reportes
        channel = self.bot.get_channel(payload.channel_id)
        if not channel or channel.name != "reportes":
            return

        # Verificar si el usuario tiene permisos
        if not payload.member.guild_permissions.manage_messages:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message.embeds:
            return

        emoji = str(payload.emoji)
        
        # Verificar si es una acción de moderación pendiente
        if message.id in self.pending_actions:
            await self.handle_mod_action(emoji, message, payload.member, channel)
            return

        if emoji not in ["✅", "❌", "🔨"]:
            return

        # Obtener ID del reporte del footer
        report_id = int(message.embeds[0].footer.text.split(": ")[1]) - 1
        server_id = str(payload.guild_id)

        if emoji == "✅":  # Marcar como resuelto
            self.reports[server_id][report_id]["status"] = "resuelto"
            await message.edit(embed=discord.Embed(
                title="Reporte Resuelto",
                description="Este reporte ha sido marcado como resuelto.",
                color=discord.Color.green()
            ))

        elif emoji == "❌":  # Descartar reporte
            self.reports[server_id][report_id]["status"] = "descartado"
            await message.edit(embed=discord.Embed(
                title="Reporte Descartado",
                description="Este reporte ha sido descartado.",
                color=discord.Color.red()
            ))

        elif emoji == "🔨":  # Mostrar opciones de moderación
            reported_user_id = int(message.embeds[0].fields[0].value.split("(")[1].strip(")"))
            reported_user = payload.member.guild.get_member(reported_user_id)
            
            if reported_user:
                action_embed = discord.Embed(
                    title="Acciones de Moderación",
                    description=f"Selecciona una acción para {reported_user.mention}:",
                    color=discord.Color.blue()
                )
                
                action_embed.add_field(
                    name="Acciones Disponibles",
                    value=(
                        "Reacciona con:\n"
                        "🔇 - **Silenciar Usuario**\n"
                        "     • Impide que el usuario escriba en los canales\n"
                        "👢 - **Expulsar Usuario**\n"
                        "     • Expulsa al usuario del servidor (puede volver a entrar)\n"
                        "🔨 - **Banear Usuario**\n"
                        "     • Banea permanentemente al usuario del servidor"
                    ),
                    inline=False
                )
                
                action_embed.set_footer(text=f"Usuario: {reported_user.id}")
                
                action_msg = await channel.send(embed=action_embed)
                self.pending_actions[action_msg.id] = reported_user.id
                await action_msg.add_reaction("🔇")
                await action_msg.add_reaction("👢")
                await action_msg.add_reaction("🔨")

        self.save_reports()

    async def handle_mod_action(self, emoji, message, moderator, channel):
        """Manejar las acciones de moderación"""
        if emoji not in ["🔇", "👢", "🔨"]:
            return

        user_id = self.pending_actions.get(message.id)
        if not user_id:
            return

        guild = channel.guild
        target_user = guild.get_member(user_id)
        if not target_user:
            await channel.send("No se pudo encontrar al usuario. Es posible que haya abandonado el servidor.")
            return

        # Preguntar por la razón
        await channel.send(f"{moderator.mention} Por favor, escribe la razón para esta acción (tienes 30 segundos):")

        try:
            reason_msg = await self.bot.wait_for(
                'message',
                timeout=30.0,
                check=lambda m: m.author == moderator and m.channel == channel
            )
            reason = reason_msg.content
        except asyncio.TimeoutError:
            await channel.send("Tiempo agotado. Acción cancelada.")
            del self.pending_actions[message.id]
            return

        try:
            if emoji == "🔇":  # Silenciar
                # Buscar o crear rol "Silenciado"
                muted_role = discord.utils.get(guild.roles, name="Silenciado")
                if not muted_role:
                    # Crear rol con permisos restringidos
                    muted_role = await guild.create_role(name="Silenciado", reason="Rol para usuarios silenciados")
                    for channel in guild.channels:
                        await channel.set_permissions(muted_role, send_messages=False, add_reactions=False)

                await target_user.add_roles(muted_role, reason=reason)
                action_type = "silenciado"

            elif emoji == "👢":  # Expulsar
                await target_user.kick(reason=reason)
                action_type = "expulsado"

            elif emoji == "🔨":  # Banear
                await target_user.ban(reason=reason, delete_message_days=1)
                action_type = "baneado"

            # Enviar confirmación
            confirm_embed = discord.Embed(
                title="Acción de Moderación Ejecutada",
                description=f"Usuario {action_type} exitosamente",
                color=discord.Color.green()
            )
            confirm_embed.add_field(name="Usuario", value=f"{target_user} ({target_user.id})", inline=False)
            confirm_embed.add_field(name="Moderador", value=moderator.mention, inline=False)
            confirm_embed.add_field(name="Razón", value=reason, inline=False)
            
            await channel.send(embed=confirm_embed)

        except discord.Forbidden:
            await channel.send("No tengo los permisos necesarios para realizar esta acción.")
        except Exception as e:
            await channel.send(f"Ocurrió un error al ejecutar la acción: {str(e)}")
        
        del self.pending_actions[message.id]

async def setup(bot):
    await bot.add_cog(Reports(bot)) 
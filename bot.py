import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from collections import deque
import re
import os

# ==================================================
# CONFIGURACIÓN
# ==================================================

TOKEN = os.getenv("TOKEN")

STAFF_ROLE_ID = 1504977810479906908
OWNER_ROLE_ID = 1504977810479906908
ADMIN_ROLE_ID = 1504986891106259115
MOD_ROLE_ID = 1504987741245538515
MIDDLEMAN_ROLE_ID = 1505072146911727616
TICKET_CATEGORY_ID = 1505042121520975972
MM_CATEGORY_ID = 1505042121520975972

GUILD_ID = 1504970892533436426
MY_GUILD = discord.Object(id=GUILD_ID)
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ==================================================
# CONTADOR TICKETS
# ==================================================

ticket_counter = 1
mm_counter = 1

# ==================================================
# BOTONES TICKET
# ==================================================

class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

    # =========================================
    # RECLAMAR
    # =========================================

    @discord.ui.button(
        label="Reclamar Ticket",
        style=discord.ButtonStyle.green,
        custom_id="claim_ticket"
    )

    async def reclamar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button
    ):

        staff_role = interaction.guild.get_role(
            STAFF_ROLE_ID
        )

        if staff_role not in interaction.user.roles:

            return await interaction.response.send_message(

                "❌ No eres staff.",

                ephemeral=True
            )

        # DESACTIVAR BOTÓN

        button.disabled = True

        button.label = (
            f"Reclamado por "
            f"{interaction.user.name}"
        )

        embed = discord.Embed(
            title="📌 Ticket Reclamado",
            description=(
                f"{interaction.user.mention} "
                f"reclamó este ticket."
            ),
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(
            view=self
        )

        await interaction.followup.send(
            embed=embed
        )

    # =========================================
    # CERRAR
    # =========================================

    @discord.ui.button(
        label="Cerrar Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )

    async def cerrar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button
    ):

        staff_role = interaction.guild.get_role(
            STAFF_ROLE_ID
        )

        if staff_role not in interaction.user.roles:

            return await interaction.response.send_message(

                "❌ No eres staff.",

                ephemeral=True
            )

        await interaction.response.send_message(
            "🔒 Cerrando ticket..."
        )

        await interaction.channel.delete()
        
        
class MMPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🧑‍💼 Middleman",
        style=discord.ButtonStyle.red,
        custom_id="create_mm_ticket"
    )

    async def crear_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        global mm_counter

        guild = interaction.guild

        categoria = guild.get_channel(
            MM_CATEGORY_ID
        )

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    read_messages=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
        }

        staff_role = guild.get_role(
            STAFF_ROLE_ID
        )

        if staff_role:

            overwrites[staff_role] = (
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
            )

        canal = await guild.create_text_channel(

            name=f"mm-{mm_counter}",

            category=categoria,

            overwrites=overwrites
        )

        mm_counter += 1

        embed = discord.Embed(
            title="🧑‍💼 Ticket Middleman",
            description=(
                f"{interaction.user.mention} "
                f"bienvenido a tu ticket."
            ),
            color=discord.Color.red()
        )

        middleman_role = guild.get_role(
            MIDDLEMAN_ROLE_ID
        )

         await canal.send(
            f"{middleman_role.mention}\n"
            f"{interaction.user.mention}",
                embed=embed,
                view=TicketView()
        )

        await interaction.response.send_message(

            f"✅ Ticket creado: {canal.mention}",

            ephemeral=True
        )


# ==================================================
# VARIABLES
# ==================================================

subasta_activa = None
cola_subastas = deque()

cooldowns_subasta = {}

# ==================================================
# VIEW CONFIRMAR SUBASTA
# ==================================================

class ConfirmarSubastaView(discord.ui.View):

    def __init__(self, subasta=None):
        super().__init__(timeout=None)
        self.subasta = subasta

    @discord.ui.button(
        emoji="👍",
        style=discord.ButtonStyle.green,
        custom_id="confirmar_subasta"
    )
    async def confirmar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # Protección si el bot reinició
        if self.subasta is None:

            return await interaction.response.send_message(
                "❌ Esta subasta ya no está disponible.",
                ephemeral=True
            )

        subasta = self.subasta

        # Ya confirmada
        if subasta.confirmada:

            return await interaction.response.send_message(
                "❌ Esta subasta ya fue confirmada.",
                ephemeral=True
            )

        # =========================================
        # OWNER PUEDE CONFIRMAR 4 VECES
        # =========================================

        es_owner = any(
            role.id == OWNER_ROLE_ID
            for role in interaction.user.roles
        )

        if not es_owner:

            # Usuario normal solo confirma 1 vez
            if interaction.user.id in subasta.confirmados:

                return await interaction.response.send_message(
                    "❌ Ya confirmaste esta subasta.",
                    ephemeral=True
                )

            subasta.confirmados.add(
                interaction.user.id
            )

        else:

            # Owner puede confirmar 4 veces
            subasta.confirmados.add(
                f"{interaction.user.id}_{len(subasta.confirmados)}"
            )

        # Actualizar panel
        try:

            await subasta.mensaje.edit(
                embed=crear_embed(subasta),
                view=self
            )

        except:
            pass

        await interaction.response.send_message(
            (
                f"✅ Confirmaste la subasta "
                f"({len(subasta.confirmados)}/4)"
            ),
            ephemeral=True
        )

        # Llegó a 4 confirmaciones
        if (
            len(subasta.confirmados)
            >= subasta.confirmaciones_requeridas
        ):

            subasta.confirmada = True

            # Iniciar tiempo
            subasta.fin = (
                datetime.utcnow()
                + subasta.duracion
            )

            # Desactivar botón
            button.disabled = True

            try:

                await subasta.mensaje.edit(
                    embed=crear_embed(subasta),
                    view=self
                )

            except:
                pass

            await subasta.canal.send(
                "✅ La subasta fue confirmada. "
                "¡Comienza ahora!"
            )
            
# ==================================================
# CLASE SUBASTA
# ==================================================

class Subasta:

    def __init__(
        self,
        owner,
        imagen,
        minimo,
        duracion,
        canal
    ):

        self.owner = owner
        self.imagen = imagen
        self.mejor_oferta = minimo
        self.mejor_postor = None
        self.duracion = duracion

        # El tiempo NO inicia aún
        self.fin = None

        self.canal = canal
        self.mensaje = None
        self.finalizada = False

        # NUEVO SISTEMA
        self.confirmados = set()
        self.confirmaciones_requeridas = 4
        self.confirmada = False

        self.creada_en = datetime.utcnow()

# ==================================================
# FORMATO DINERO
# ==================================================

def formatear_dinero(numero):

    return f"{numero:,}".replace(",", ".")

# ==================================================
# TIEMPO
# ==================================================

def convertir_tiempo(texto):

    texto = texto.lower()

    # SEGUNDOS
    match_seg = re.match(
        r"^(\d+)s$",
        texto
    )

    if match_seg:

        segundos = int(
            match_seg.group(1)
        )

        if segundos < 1 or segundos > 300:
            return None

        return timedelta(
            seconds=segundos
        )

    # MINUTOS
    match_min = re.match(
        r"^(\d+)m$",
        texto
    )

    if match_min:

        minutos = int(
            match_min.group(1)
        )

        if minutos < 1 or minutos > 5:
            return None

        return timedelta(
            minutes=minutos
        )

    return None
# ==================================================
# TIEMPO RESTANTE
# ==================================================

def tiempo_restante(fin):

    restante = fin - datetime.utcnow()

    segundos = int(
        restante.total_seconds()
    )

    if segundos < 0:
        segundos = 0

    minutos = segundos // 60
    segundos = segundos % 60

    return f"{minutos:02}:{segundos:02}"

# ==================================================
# EMBED SUBASTA
# ==================================================

def crear_embed(subasta):

    if subasta.mejor_postor:

        postor = (
            subasta.mejor_postor.mention
        )

    else:

        postor = "Nadie"

    embed = discord.Embed(
        title="🔨 SUBASTA ACTIVA",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="👤 Vendedor",
        value=subasta.owner.mention,
        inline=False
    )

    embed.add_field(
        name="💰 Mayor Oferta",
        value=f"${formatear_dinero(subasta.mejor_oferta)}",
        inline=False
    )

    embed.add_field(
        name="🏆 Mayor Postor",
        value=postor,
        inline=False
    )

    # =========================================
    # SUBASTA EN ESPERA DE CONFIRMACIÓN
    # =========================================

    if not subasta.confirmada:

        segundos_restantes = max(
            0,
            90 - int(
                (
                    datetime.utcnow()
                    - subasta.creada_en
                ).total_seconds()
            )
        )

        minutos = (
            segundos_restantes // 60
        )

        segundos = (
            segundos_restantes % 60
        )

        embed.add_field(
            name="👍 Confirmaciones",
            value=(
                f"{len(subasta.confirmados)}"
                f"/4"
            ),
            inline=False
        )

        embed.add_field(
            name="⏳ Tiempo para confirmar",
            value=(
                f"{minutos:02}:"
                f"{segundos:02}"
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "Se necesitan "
                "4 confirmaciones"
            )
        )

    # =========================================
    # SUBASTA CONFIRMADA
    # =========================================

    else:

        embed.add_field(
            name="⏳ Tiempo",
            value=tiempo_restante(
                subasta.fin
            ),
            inline=False
        )

        embed.set_footer(
            text="Usa /pujar para ofertar"
        )

    embed.set_image(
        url=subasta.imagen
    )

    return embed
# ==================================================
# EMBED PUJA
# ==================================================

def embed_puja(usuario, cantidad):

    embed = discord.Embed(
        title="💸 NUEVA PUJA",
        color=discord.Color.green()
    )

    embed.add_field(
        name="👤 Usuario",
        value=usuario.mention,
        inline=False
    )

    embed.add_field(
        name="💰 Oferta",
        value=f"${formatear_dinero(cantidad)}",
        inline=False
    )

    embed.set_thumbnail(
        url=usuario.display_avatar.url
    )

    return embed

# ==================================================
# EMBED FINALIZADA
# ==================================================

def embed_finalizada(subasta):

    if subasta.mejor_postor:

        ganador = (
            subasta.mejor_postor.mention
        )

        avatar = (
            subasta.mejor_postor.display_avatar.url
        )

    else:

        ganador = "Nadie"
        avatar = None

    embed = discord.Embed(
        title="🏁 SUBASTA FINALIZADA",
        color=discord.Color.red()
    )

    embed.add_field(
        name="👑 Ganador",
        value=ganador,
        inline=False
    )

    embed.add_field(
        name="💰 Oferta Final",
        value=f"${formatear_dinero(subasta.mejor_oferta)}",
        inline=False
    )

    if avatar:

        embed.set_thumbnail(
            url=avatar
        )

    embed.set_image(
        url=subasta.imagen
    )

    return embed

# ==================================================
# INICIAR SIGUIENTE SUBASTA
# ==================================================

async def iniciar_siguiente_subasta():

    global subasta_activa

    if len(cola_subastas) == 0:

        subasta_activa = None
        return

    subasta = cola_subastas.popleft()

    mensaje = await subasta.canal.send(
        embed=crear_embed(subasta),
        view=ConfirmarSubastaView(
            subasta
        )
    )

    subasta.mensaje = mensaje

    subasta_activa = subasta

# ==================================================
# FINALIZAR SUBASTA
# ==================================================

async def finalizar_subasta(subasta):

    global ticket_counter

    subasta.finalizada = True

    try:

        await subasta.mensaje.edit(
            embed=embed_finalizada(
                subasta
            )
        )

    except Exception as e:

        print(
            f"Error editando mensaje: {e}"
        )

    if subasta.mejor_postor is None:

        await subasta.canal.send(
            "❌ La subasta terminó sin ofertas."
        )

        await iniciar_siguiente_subasta()

        return

    try:

        await subasta.canal.send(
            embed=embed_finalizada(
                subasta
            )
        )

    except Exception as e:

        print(
            f"Error enviando ganador: {e}"
        )

    # =========================================
    # CREAR TICKET
    # =========================================

    try:

        guild = subasta.canal.guild

        categoria = guild.get_channel(
            TICKET_CATEGORY_ID
        )

        if categoria is None:

            print(
                "ERROR: categoría no encontrada"
            )

            return

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    read_messages=False
                ),

            subasta.owner:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                ),

            subasta.mejor_postor:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
        }

        staff_role = guild.get_role(
            STAFF_ROLE_ID
        )

        if staff_role:

            overwrites[staff_role] = (
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
            )

        ticket = await guild.create_text_channel(

            name=f"ticket-{ticket_counter}",

            category=categoria,

            overwrites=overwrites
        )

        ticket_counter += 1

        # =========================================
        # ETIQUETA AUTOMÁTICA MIDDLEMAN
        # =========================================

        middleman_role = guild.get_role(
            MIDDLEMAN_ROLE_ID
        )

        await ticket.send(

            f"{middleman_role.mention}\n"
            f"🎉 Bienvenidos "
            f"{subasta.owner.mention} "
            f"y "
            f"{subasta.mejor_postor.mention}"

        )

        await ticket.send(
            embed=embed_finalizada(
                subasta
            ),
            view=TicketView()
        )

        print(
            "✅ Ticket creado correctamente"
        )

    except Exception as e:

        print(
            f"ERROR CREANDO TICKET: {e}"
        )

    await iniciar_siguiente_subasta()

# ==================================================
# BOT LISTO
# ==================================================

@bot.event
async def on_ready():

    bot.add_view(TicketView())
    bot.add_view(MMPanelView())
    bot.add_view(
    ConfirmarSubastaView(None)
)

    try:

        guild = discord.Object(id=1504970892533436426)

        # BORRAR TODOS LOS COMANDOS GLOBALES
        bot.tree.clear_commands(guild=None)

        # SINCRONIZAR BORRADO GLOBAL
        await bot.tree.sync()

        # SINCRONIZAR SOLO LOS DEL SERVIDOR
        synced = await bot.tree.sync(guild=guild)

        print(f"✅ Sync completado: {len(synced)}")

    except Exception as e:
        print(e)

    # =========================================
    # SINCRONIZAR CONTADORES
    # =========================================

    global ticket_counter, mm_counter

    guild_real = bot.guilds[0]

    ticket_counter = len([
        c for c in guild_real.channels
        if c.name.startswith("ticket-")
    ]) + 1

    mm_counter = len([
        c for c in guild_real.channels
        if c.name.startswith("mm-")
    ]) + 1

    # =========================================

    if not actualizar_contador.is_running():
        actualizar_contador.start()

    if not revisar_subasta.is_running():
        revisar_subasta.start()

    print(f"✅ Bot conectado como {bot.user}")


# ==================================================
# SUBASTA
# ==================================================

@bot.tree.command(
    name="subasta",
    description="Crear subasta",
    guild=MY_GUILD
)

@app_commands.describe(
    imagen="Sube imagen",
    monto_minimo="Monto mínimo",
    tiempo="Ejemplo: 1m, 5m"
)

async def subasta(

    interaction: discord.Interaction,

    imagen: discord.Attachment,

    monto_minimo: int,

    tiempo: str
):

    global subasta_activa

    ahora = datetime.utcnow()

    # =========================================
    # VERIFICAR SI ES OWNER
    # =========================================

    es_owner = any(
        role.id == OWNER_ROLE_ID
        for role in interaction.user.roles
    )

    # =========================================
    # COOLDOWN (EXCEPTO OWNER)
    # =========================================

    if not es_owner:

        if interaction.user.id in cooldowns_subasta:

            tiempo_restante_cd = (
                cooldowns_subasta[
                    interaction.user.id
                ] - ahora
            ).total_seconds()

            if tiempo_restante_cd > 0:

                minutos = int(
                    tiempo_restante_cd // 60
                )

                segundos = int(
                    tiempo_restante_cd % 60
                )

                return await interaction.response.send_message(

                    f"❌ Debes esperar "
                    f"{minutos}m {segundos}s "
                    f"para crear otra subasta.",

                    ephemeral=True
                )

    # =========================================
    # VALIDAR MONTO
    # =========================================

    if monto_minimo < 1:

        return await interaction.response.send_message(
            "❌ El monto mínimo debe ser mayor a 0.",
            ephemeral=True
        )

    # =========================================
    # VALIDAR TIEMPO
    # =========================================

    duracion = convertir_tiempo(
        tiempo
    )

    if duracion is None:

        return await interaction.response.send_message(
            "❌ Usa tiempos como 1m o 5m.",
            ephemeral=True
        )

    # =========================================
    # CREAR SUBASTA
    # =========================================

    nueva_subasta = Subasta(
        interaction.user,
        imagen.url,
        monto_minimo,
        duracion,
        interaction.channel
    )

    # Cooldown solo para no-owner
    if not es_owner:

        cooldowns_subasta[
            interaction.user.id
        ] = (
            datetime.utcnow()
            + timedelta(minutes=5)
        )

    # =========================================
    # INICIAR O ENCOLAR
    # =========================================

    if subasta_activa is None:

        mensaje = await interaction.channel.send(
            embed=crear_embed(
                nueva_subasta
            ),
            view=ConfirmarSubastaView(
                nueva_subasta
            )
        )

        nueva_subasta.mensaje = mensaje

        subasta_activa = nueva_subasta

        await interaction.response.send_message(
            "✅ Subasta creada. Esperando 4 confirmaciones.",
            ephemeral=True
        )

    else:

        cola_subastas.append(
            nueva_subasta
        )

        await interaction.response.send_message(

            f"📋 Subasta agregada a la cola.\n"
            f"Posición: {len(cola_subastas)}",

            ephemeral=True
        )
# ==================================================
# PUJAR
# ==================================================

@bot.tree.command(
    name="pujar",
    description="Pujar",
    guild=MY_GUILD
)

async def pujar(
    interaction: discord.Interaction,
    cantidad: int
):

    global subasta_activa

    if subasta_activa is None:

        return await interaction.response.send_message(
            "❌ No hay subasta activa.",
            ephemeral=True
        )

    subasta = subasta_activa

    # =========================================
    # SUBASTA NO CONFIRMADA
    # =========================================

    if not subasta.confirmada:

        return await interaction.response.send_message(
            (
                "❌ La subasta aún no ha sido "
                "confirmada por 4 usuarios."
            ),
            ephemeral=True
        )

    # =========================================
    # NO PUJARSE A SI MISMO
    # =========================================

    es_owner_servidor = (
        interaction.user.id ==
        interaction.guild.owner_id
    )

    # =========================================
    # NO PUJARSE A SI MISMO
    # EXCEPTO OWNER DEL SERVIDOR
    # =========================================

    es_owner_servidor = (
        interaction.user.id ==
        interaction.guild.owner_id
    )

    if (
        interaction.user == subasta.owner
        and not es_owner_servidor
    ):

        return await interaction.response.send_message(

            "❌ No puedes pujar en tu propia subasta.",

            ephemeral=True
        )

    # =========================================
    # INCREMENTO MÍNIMO DE 100
    # =========================================

    incremento_minimo = 100

    oferta_minima = (
        subasta.mejor_oferta
        + incremento_minimo
    )

    if cantidad < oferta_minima:

        return await interaction.response.send_message(

            f"❌ La puja mínima es "
            f"${formatear_dinero(oferta_minima)}",

            ephemeral=True
        )

    subasta.mejor_oferta = cantidad
    subasta.mejor_postor = interaction.user

    try:

        await subasta.mensaje.edit(
            embed=crear_embed(subasta)
        )

    except:
        pass

    await subasta.canal.send(
        embed=embed_puja(
            interaction.user,
            cantidad
        )
    )

    await interaction.response.send_message(

        f"✅ Pujaste "
        f"${formatear_dinero(cantidad)}",

        ephemeral=True
    )

# ==================================================
# ENDSUB
# ==================================================

@bot.tree.command(
    name="endsub",
    description="Finalizar subasta",
    guild=MY_GUILD
)

async def endsub(
    interaction: discord.Interaction
):

    global subasta_activa

    # =========================================
    # PERMISOS
    # OWNER / ADMIN / MOD
    # =========================================

    roles_permitidos = {
        OWNER_ROLE_ID,
        ADMIN_ROLE_ID,
        MOD_ROLE_ID
    }

    tiene_permiso = any(
        role.id in roles_permitidos
        for role in interaction.user.roles
    )

    if not tiene_permiso:

        return await interaction.response.send_message(
            "❌ No tienes permisos para usar este comando.",
            ephemeral=True
        )

    if subasta_activa is None:

        return await interaction.response.send_message(
            "❌ No hay subasta activa.",
            ephemeral=True
        )

    subasta = subasta_activa

    subasta_activa = None

    await finalizar_subasta(
        subasta
    )

    await interaction.response.send_message(
        "✅ Subasta finalizada.",
        ephemeral=True
    )

# ==================================================
# CONTADOR
# ==================================================

@tasks.loop(seconds=1)

async def actualizar_contador():

    global subasta_activa

    if subasta_activa is None:
        return

    if subasta_activa.finalizada:
        return

    # =========================================
    # SOLO ACTUALIZAR SI ESTÁ CONFIRMADA
    # =========================================

    if not subasta_activa.confirmada:
        return

    try:

        await subasta_activa.mensaje.edit(
            embed=crear_embed(
                subasta_activa
            )
        )

    except:
        pass

# ==================================================
# REVISAR TIEMPO
# ==================================================

@tasks.loop(seconds=1)

async def revisar_subasta():

    global subasta_activa

    if subasta_activa is None:
        return

    subasta = subasta_activa

    # =========================================
    # SUBASTA NO CONFIRMADA
    # =========================================

    if not subasta.confirmada:

        tiempo_espera = (
            datetime.utcnow()
            - subasta.creada_en
        ).total_seconds()

        # Actualizar embed
        try:

            await subasta.mensaje.edit(
                embed=crear_embed(
                    subasta
                )
            )

        except:
            pass

        # 90 SEGUNDOS
        if tiempo_espera >= 90:

            subasta.finalizada = True

            embed = discord.Embed(
                title="❌ SUBASTA CANCELADA",
                description=(
                    "La subasta fue cancelada\n"
                    "porque no consiguió\n"
                    "4 confirmaciones a tiempo."
                ),
                color=discord.Color.red()
            )

            embed.set_image(
                url=subasta.imagen
            )

            try:

                await subasta.mensaje.edit(
                    embed=embed,
                    view=None
                )

            except:
                pass

            await subasta.canal.send(
                "❌ La subasta terminó "
                "sin confirmaciones."
            )

            subasta_activa = None

            await iniciar_siguiente_subasta()

        return

    # =========================================
    # SUBASTA CONFIRMADA
    # =========================================

    if datetime.utcnow() >= subasta.fin:

        subasta_activa = None

        await finalizar_subasta(
            subasta
        )
# ==================================================
# PANEL MM
# ==================================================

@bot.tree.command(
    name="panelmm",
    description="Enviar panel middleman",
    guild=MY_GUILD
)

async def panelmm(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="✨ ¡Bienvenido al Middleman! ✨",
        description=(
            "📩 Si deseas un intermediario,\n"
            "presiona el botón de abajo.\n\n"
            "Te responderemos a la brevedad."
        ),
        color=discord.Color.gold()
    )

    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1466777456076914788/1505085081621102632/IMG_8404.png?ex=6a095736&is=6a0805b6&hm=4aee8067405d1061c988dd69e7f9d250741e1747f48d1d3ae86fb71351ef6814&"
    )

    await interaction.channel.send(
        embed=embed,
        view=MMPanelView()
    )

    await interaction.response.send_message(
        "✅ Panel enviado.",
        ephemeral=True
    )

# ==================================================
# ADD USER TICKET
# ==================================================

@bot.tree.command(
    name="add",
    description="Agregar usuario al ticket",
    guild=MY_GUILD
)

async def add(
    interaction: discord.Interaction,
    usuario: discord.Member
):

    # =========================================
    # PERMISOS
    # OWNER / ADMIN / MOD / MIDDLEMAN
    # =========================================

    roles_permitidos = {
        OWNER_ROLE_ID,
        ADMIN_ROLE_ID,
        MOD_ROLE_ID,
        MIDDLEMAN_ROLE_ID
    }

    tiene_permiso = any(
        role.id in roles_permitidos
        for role in interaction.user.roles
    )

    if not tiene_permiso:

        return await interaction.response.send_message(
            "❌ No tienes permisos para usar este comando.",
            ephemeral=True
        )

    await interaction.channel.set_permissions(
        usuario,
        read_messages=True,
        send_messages=True
    )

    await interaction.response.send_message(
        f"✅ {usuario.mention} fue agregado al ticket."
    )
    
# ==================================================
# INICIAR BOT
# ==================================================

bot.run(TOKEN)

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
TICKET_CATEGORY_ID = 1505042121520975972
MM_CATEGORY_ID = 1505042121520975972
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

        await canal.send(
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
        self.fin = (
            datetime.utcnow() + duracion
        )
        self.canal = canal
        self.mensaje = None
        self.finalizada = False

# ==================================================
# FORMATO DINERO
# ==================================================

def formatear_dinero(numero):

    return f"{numero:,}".replace(",", ".")

# ==================================================
# TIEMPO
# ==================================================

def convertir_tiempo(texto):

    match = re.match(
        r"^(\d+)m$",
        texto.lower()
    )

    if not match:
        return None

    minutos = int(
        match.group(1)
    )

    if minutos < 1:
        return None

    return timedelta(minutes=minutos)

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

    embed.add_field(
        name="⏳ Tiempo",
        value=tiempo_restante(
            subasta.fin
        ),
        inline=False
    )

    embed.set_image(
        url=subasta.imagen
    )

    embed.set_footer(
        text="Usa /pujar para ofertar"
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

    subasta.fin = (
        datetime.utcnow()
        + subasta.duracion
    )

    mensaje = await subasta.canal.send(
        embed=crear_embed(subasta)
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

        await ticket.send(

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

    bot.add_view(MMPanelView())
    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Comandos sincronizados: "
            f"{len(synced)}"
        )

    except Exception as e:

        print(e)

    if not actualizar_contador.is_running():
        actualizar_contador.start()

    if not revisar_subasta.is_running():
        revisar_subasta.start()

    print(
        f"✅ Bot conectado como "
        f"{bot.user}"
    )

# ==================================================
# SUBASTA
# ==================================================

@bot.tree.command(
    name="subasta",
    description="Crear subasta"
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

    if monto_minimo < 1:

        return await interaction.response.send_message(
            "❌ El monto mínimo debe ser mayor a 0.",
            ephemeral=True
        )

    duracion = convertir_tiempo(
        tiempo
    )

    if duracion is None:

        return await interaction.response.send_message(
            "❌ Usa tiempos como 1m o 5m.",
            ephemeral=True
        )

    nueva_subasta = Subasta(
        interaction.user,
        imagen.url,
        monto_minimo,
        duracion,
        interaction.channel
    )

    if subasta_activa is None:

        mensaje = await interaction.channel.send(
            embed=crear_embed(
                nueva_subasta
            )
        )

        nueva_subasta.mensaje = mensaje

        subasta_activa = nueva_subasta

        await interaction.response.send_message(
            "✅ Subasta iniciada.",
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
    description="Pujar"
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
    description="Finalizar subasta"
)

async def endsub(
    interaction: discord.Interaction
):

    global subasta_activa

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

    if datetime.utcnow() >= subasta_activa.fin:

        subasta = subasta_activa

        subasta_activa = None

        await finalizar_subasta(
            subasta
        )

# ==================================================
# INICIAR BOT
# ==================================================

bot.run(TOKEN)

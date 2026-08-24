import discord
from discord import app_commands
from discord.ext import commands
import random
import aiohttp
import asyncio
import time

intents = discord.Intents.default()
intents.members = True  # Fondamentale per leggere i membri e i ruoli
bot = commands.Bot(command_prefix="!", intents=intents)

# Database in memoria
conti = {}
utenti_in_servizio = {}
shift_records = {}  # {user_id: {"total_seconds": int, "start_time": float or None, "is_paused": bool}}

@bot.event
async def on_ready():
    print(f'Bot Master RP & Staff connesso come {bot.user}!')
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizzati {len(synced)} comandi totali con successo!")
    except Exception as e:
        print(e)

# Funzione per il saldo della banca
def get_saldo(user_id):
    if user_id not in conti:
        conti[user_id] = 1000 
    return conti[user_id]

# Funzione per recuperare l'avatar di Roblox
async def get_roblox_avatar(username: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                users = data.get("data", [])
                if not users:
                    return None
                user_id = users[0].get("id")
            
            thumbnail_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false"
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    return None
                thumb_data = await resp.json()
                thumb_list = thumb_data.get("data", [])
                if not thumb_list:
                    return None
                return thumb_list[0].get("imageUrl")
    except Exception:
        return None


# ==========================================
# 1. COMANDI BANCA & ECONOMIA
# ==========================================

@bot.tree.command(name="saldo", description="Controlla il tuo conto in banca o di un altro utente")
async def saldo(interaction: discord.Interaction, utente: discord.Member = None):
    target = utente or interaction.user
    denaro = get_saldo(target.id)
    embed = discord.Embed(title=f"🏦 Conto Corrente di {target.name}", description=f"Disponibilità: **${denaro:,}**", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="paga", description="Invia soldi dal tuo conto a un altro giocatore")
async def paga(interaction: discord.Interaction, destinatario: discord.Member, importo: int):
    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere superiore a 0!", ephemeral=True)
        return
    mittente_id = interaction.user.id
    dest_id = destinatario.id
    if mittente_id == dest_id:
        await interaction.response.send_message("❌ Non puoi mandare soldi a te stesso!", ephemeral=True)
        return
    saldo_mittente = get_saldo(mittente_id)
    if saldo_mittente < importo:
        await interaction.response.send_message(f"❌ Non hai abbastanza soldi! Saldo: ${saldo_mittente:,}", ephemeral=True)
        return
    conti[mittente_id] -= importo
    conti[dest_id] = get_saldo(dest_id) + importo
    embed = discord.Embed(title="💸 Bonifico Riuscito", description=f"Hai inviato **${importo:,}** a {destinatario.mention}!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="banca_admin", description="Gestisci i soldi di un utente (Solo Admin)")
@app_commands.default_permissions(administrator=True)
async def banca_admin(interaction: discord.Interaction, azione: str, utente: discord.Member, importo: int):
    azione = azione.lower()
    if azione not in ["aggiungi", "rimuovi"] or importo <= 0:
        await interaction.response.send_message("❌ Usa 'aggiungi' o 'rimuovi' con un importo valido!", ephemeral=True)
        return
    user_id = utente.id
    current = get_saldo(user_id)
    if azione == "aggiungi":
        conti[user_id] = current + importo
        testo = f"Aggiunti **${importo:,}** a {utente.mention}."
    else:
        conti[user_id] = max(0, current - importo)
        testo = f"Rimossi **${importo:,}** a {utente.mention}."
    embed = discord.Embed(title="🏛️ Gestione Banca Admin", description=testo + f"\nNuovo saldo: **${conti[user_id]:,}**", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stipendio", description="Riscuoti il tuo stipendio di servizio")
@app_commands.checks.cooldown(1, 43200) # 12 ore
async def stipendio(interaction: discord.Interaction):
    user_id = interaction.user.id
    premio = 3000
    conti[user_id] = get_saldo(user_id) + premio
    embed = discord.Embed(title="💼 Stipendio Riscosso!", description=f"Hai ritirato il tuo stipendio di **${premio:,}**!", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@stipendio.error
async def stipendio_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        ore = int(error.retry_after // 3600)
        minuti = int((error.retry_after % 3600) // 60)
        await interaction.response.send_message(f"⏳ Aspetta ancora **{ore} ore e {minuti} minuti** per riscuotere lo stipendio.", ephemeral=True)

@bot.tree.command(name="classifica", description="Mostra i 5 utenti più ricchi del server")
async def classifica(interaction: discord.Interaction):
    if not conti:
        await interaction.response.send_message("❌ Nessun conto attivo!", ephemeral=True)
        return
    classifica_ordinata = sorted(conti.items(), key=lambda item: item[1], reverse=True)[:5]
    embed = discord.Embed(title="🏆 Classifica Banca - I più ricchi", color=discord.Color.gold())
    testo = ""
    for pos, (uid, soldi) in enumerate(classifica_ordinata, 1):
        utente = interaction.guild.get_member(uid)
        nome = utente.name if utente else f"Utente ({uid})"
        medaglia = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"#{pos}"
        testo += f"{medaglia} **{nome}** — **${soldi:,}**\n"
    embed.description = testo
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lavora", description="Fai un lavoretto veloce per guadagnare soldi")
@app_commands.checks.cooldown(1, 1800) # 30 minuti
async def lavora(interaction: discord.Interaction):
    user_id = interaction.user.id
    guadagno = random.randint(200, 800)
    conti[user_id] = get_saldo(user_id) + guadagno
    lavori = ["riparato un'auto", "scaricato merci all'emporio", "fatto consegne rapide", "turno extra come guardia"]
    embed = discord.Embed(title="🛠️ Lavoro Completato", description=f"Hai {random.choice(lavori)}!\nGuadagno: **${guadagno:,}**", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@lavora.error
async def lavora_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minuti = int(error.retry_after // 60)
        await interaction.response.send_message(f"☕ Riposati un attimo, potrai lavorare tra **{minuti} minuti**.", ephemeral=True)


# ==========================================
# 2. COMANDI FAZIONI & ROLEPLAY
# ==========================================

@bot.tree.command(name="servizio_on", description="Entra in servizio per una fazione")
@app_commands.choices(fazione=[
    app_commands.Choice(name="Polizia", value="Polizia 🚓"),
    app_commands.Choice(name="EMS (Medici)", value="EMS 🚑"),
    app_commands.Choice(name="Vigili del Fuoco", value="Vigili del Fuoco 🚒")
])
async def servizio_on(interaction: discord.Interaction, fazione: app_commands.Choice[str]):
    user_id = interaction.user.id
    utenti_in_servizio[user_id] = {"name": interaction.user.display_name, "faction": fazione.value}
    embed = discord.Embed(title="🟢 ENTRATA IN SERVIZIO", description=f"{interaction.user.mention} è ora **IN SERVIZIO** per: **{fazione.value}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="servizio_off", description="Termina il servizio attivo")
async def servizio_off(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in utenti_in_servizio:
        fac = utenti_in_servizio[user_id]["faction"]
        del utenti_in_servizio[user_id]
        embed = discord.Embed(title="🔴 FINE SERVIZIO", description=f"{interaction.user.mention} ha terminato il turno ({fac}).", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Non sei in servizio!", ephemeral=True)

@bot.tree.command(name="stato_fazioni", description="Mostra il personale operativo in città")
async def stato_fazioni(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 STATO DEL PERSONALE IN CITTÀ", color=discord.Color.blue())
    if not utenti_in_servizio:
        embed.description = "Nessuna unità operativa in servizio."
    else:
        fazioni_dict = {}
        for data in utenti_in_servizio.values():
            fac = data["faction"]
            if fac not in fazioni_dict: fazioni_dict[fac] = []
            fazioni_dict[fac].append(data["name"])
        for fac, membri in fazioni_dict.items():
            embed.add_field(name=f"{fac} ({len(membri)})", value="\n".join([f"• {m}" for m in membri]), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sos", description="Invia un segnale d'emergenza critico")
async def sos(interaction: discord.Interaction, posizione: str, descrizione: str):
    embed = discord.Embed(title="🚨 SEGNALE SOS / EMERGENZA 🚨", description="Richiesto soccorso immediato!", color=discord.Color.dark_red())
    embed.add_field(name="📍 Posizione", value=posizione, inline=False)
    embed.add_field(name="📌 Dettagli", value=descrizione, inline=False)
    embed.set_footer(text=f"Segnale di: {interaction.user.name}")
    await interaction.response.send_message(content="🚨 **ALLERTA EMERGENZA!**", embed=embed)


# ==========================================
# 3. COMANDI STAFF & SHIFT SYSTEM
# ==========================================

@bot.tree.command(name="ssu", description="Avvia il server di Emergency Hamburg RP")
@app_commands.default_permissions(administrator=True)
async def ssu(interaction: discord.Interaction):
    embed = discord.Embed(title="🚨 SERVER START UP (SSU) 🚨", description="Il server di **Emergency Hamburg RP** è **APERTO E ONLINE!**@everyone @here 🚓🚒🚑", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ssd", description="Chiude il server di Emergency Hamburg RP")
@app_commands.default_permissions(administrator=True)
async def ssd(interaction: discord.Interaction):
    embed = discord.Embed(title="🛑 SERVER SHUT DOWN (SSD) 🛑", description="Il server di **Emergency Hamburg RP** è ora **CHIUSO**.@here 🚪💤", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

class BanModal(discord.ui.Modal, title="Registra Ban"):
    roblox_username = discord.ui.TextInput(label="Username Roblox", placeholder="Es. MarioRossi_99", required=True)
    durata = discord.ui.TextInput(label="Durata del Ban", placeholder="Es. 3 giorni / Permanenti", required=True)
    motivo = discord.ui.TextInput(label="Motivo del Ban", placeholder="Es. FailRP grave", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        avatar_url = await get_roblox_avatar(self.roblox_username.value)
        embed = discord.Embed(title="🔨 REGISTRAZIONE BAN", color=discord.Color.red())
        embed.add_field(name="👤 Username Roblox", value=self.roblox_username.value, inline=False)
        embed.add_field(name="⏳ Durata", value=self.durata.value, inline=False)
        embed.add_field(name="📌 Motivo", value=self.motivo.value, inline=False)
        if avatar_url: embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"Staffer: {interaction.user.name}")
        await interaction.followup.send(embed=embed)

class WarnModal(discord.ui.Modal, title="Registra Warn"):
    roblox_username = discord.ui.TextInput(label="Username Roblox", placeholder="Es. MarioRossi_99", required=True)
    durata = discord.ui.TextInput(label="Scadenza Warn", placeholder="Es. 7 giorni", required=True)
    motivo = discord.ui.TextInput(label="Motivo del Warn", placeholder="Es. Guida pericolosa", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        avatar_url = await get_roblox_avatar(self.roblox_username.value)
        embed = discord.Embed(title="⚠️ REGISTRAZIONE WARN", color=discord.Color.orange())
        embed.add_field(name="👤 Username Roblox", value=self.roblox_username.value, inline=False)
        embed.add_field(name="⏳ Durata", value=self.durata.value, inline=False)
        embed.add_field(name="📌 Motivo", value=self.motivo.value, inline=False)
        if avatar_url: embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"Staffer: {interaction.user.name}")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="logga_ban", description="Logga un ban con skin Roblox")
@app_commands.default_permissions(administrator=True)
async def logga_ban(interaction: discord.Interaction):
    await interaction.response.send_modal(BanModal())

@bot.tree.command(name="logga_warn", description="Logga un warn con skin Roblox")
@app_commands.default_permissions(administrator=True)
async def logga_warn(interaction: discord.Interaction):
    await interaction.response.send_modal(WarnModal())


# --- GESTIONE SHIFT STAFF ---
class ShiftView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Inizia shift", style=discord.ButtonStyle.success, emoji="🟢", custom_id="shift_inizia_btn")
    async def inizia_shift(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        now = time.time()
        if uid not in shift_records:
            shift_records[uid] = {"total_seconds": 0, "start_time": now, "is_paused": False}
        else:
            data = shift_records[uid]
            if data["start_time"] is not None and not data["is_paused"]:
                await interaction.response.send_message("❌ Hai già uno shift attivo!", ephemeral=True)
                return
            data["start_time"] = now
            data["is_paused"] = False

        await interaction.response.send_message("🟢 **Shift iniziato con successo!** Buon lavoro.", ephemeral=True)

    @discord.ui.button(label="Pausa shift", style=discord.ButtonStyle.secondary, emoji="⏸️", custom_id="shift_pausa_btn")
    async def pausa_shift(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in shift_records or shift_records[uid]["start_time"] is None or shift_records[uid]["is_paused"]:
            await interaction.response.send_message("❌ Non sei attualmente in un turno attivo da mettere in pausa!", ephemeral=True)
            return
        
        data = shift_records[uid]
        elapsed = time.time() - data["start_time"]
        data["total_seconds"] += int(elapsed)
        data["start_time"] = None
        data["is_paused"] = True

        await interaction.response.send_message("⏸️ **Shift messo in pausa.** Clicca su 'Inizia shift' per riprendere quando vuoi.", ephemeral=True)

    @discord.ui.button(label="Finisci shift", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="shift_finisci_btn")
    async def finisci_shift(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in shift_records or (shift_records[uid]["start_time"] is None and shift_records[uid]["total_seconds"] == 0):
            await interaction.response.send_message("❌ Non hai alcuno shift attivo o registrato!", ephemeral=True)
            return
        
        data = shift_records[uid]
        if data["start_time"] is not None and not data["is_paused"]:
            elapsed = time.time() - data["start_time"]
            data["total_seconds"] += int(elapsed)
            data["start_time"] = None
        
        total_sec = data["total_seconds"]
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60

        await interaction.response.send_message(f"🔴 **Shift terminato.** Tempo totale registrato finora: **{hours}h {minutes}m {seconds}s**", ephemeral=True)
        data["start_time"] = None
        data["is_paused"] = False

    @discord.ui.button(label="Guarda tempo shift", style=discord.ButtonStyle.primary, emoji="⏱️", custom_id="shift_tempo_btn")
    async def guarda_tempo(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in shift_records:
            await interaction.response.send_message("⏱️ Non hai ancora registrato alcun tempo di shift.", ephemeral=True)
            return
        
        data = shift_records[uid]
        current_total = data["total_seconds"]
        if data["start_time"] is not None and not data["is_paused"]:
            current_total += int(time.time() - data["start_time"])
        
        hours = current_total // 3600
        minutes = (current_total % 3600) // 60
        seconds = current_total % 60

        status = "🟢 In servizio" if (data["start_time"] is not None and not data["is_paused"]) else ("⏸️ In pausa" if data["is_paused"] else "🔴 Off duty")
        
        await interaction.response.send_message(f"⏱️ **Il tuo report shift:**\n• Stato: {status}\n• Tempo totale accumulato: **{hours}h {minutes}m {seconds}s**", ephemeral=True)

@bot.tree.command(name="shift-staff", description="Invia il pannello di controllo per gli shift dello staff (Solo Admin)")
@app_commands.default_permissions(administrator=True)
async def shift_staff(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⏱️ Pannello Gestione Shift Staff",
        description="Usa i pulsanti sottostanti per gestire il tuo turno di servizio:\n\n• **Inizia shift**: Avvia o riprende il conteggio.\n• **Pausa shift**: Mette in pausa il turno.\n• **Finisci shift**: Conclude la sessione di lavoro.\n• **Guarda tempo shift**: Controlla il tuo orario attuale.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Emergency Hamburg RP - Sistema Shift Staff")
    await interaction.channel.send(embed=embed, view=ShiftView())
    await interaction.response.send_message("✅ Pannello shift creato con successo in questo canale!", ephemeral=True)

@bot.tree.command(name="leadboard-shift", description="Mostra la classifica delle ore di shift dello staff")
async def leadboard_shift(interaction: discord.Interaction):
    if not shift_records:
        await interaction.response.send_message("❌ Nessun dato sui turni registrato finora.", ephemeral=True)
        return
    
    current_time = time.time()
    leaderboard_data = []
    for uid, data in shift_records.items():
        tot = data["total_seconds"]
        if data["start_time"] is not None and not data["is_paused"]:
            tot += int(current_time - data["start_time"])
        if tot > 0:
            leaderboard_data.append((uid, tot))
    
    if not leaderboard_data:
        await interaction.response.send_message("❌ Nessun tempo di shift attivo trovato.", ephemeral=True)
        return

    # Ordina in ordine decrescente in base ai secondi totali
    leaderboard_data.sort(key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(title="📊 Classifica Shift Staff", color=discord.Color.gold())
    description = ""
    for pos, (uid, tot_sec) in enumerate(leaderboard_data[:10], 1): # Mostra i primi 10
        mention = f"<@{uid}>"
        hours = tot_sec // 3600
        minutes = (tot_sec % 3600) // 60
        medaglia = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"#{pos}"
        description += f"{medaglia} {mention} — **{hours} ore e {minutes} minuti**\n"
    
    embed.description = description
    await interaction.response.send_message(embed=embed)


# ==========================================
# 4. SISTEMA TICKET (Con menu a tendina e chiusura)
# ==========================================

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Chiudi Ticket", style=discord.ButtonStyle.danger, custom_id="chiudi_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚠️ Il ticket verrà eliminato tra 3 secondi...", ephemeral=False)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            await interaction.followup.send("❌ Non ho i permessi per eliminare questo canale! Controlla 'Gestisci Canali'.", ephemeral=True)
        except Exception as e:
            print(f"Errore: {e}")

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Richiesta Fondazione", description="Crea una richiesta per fondare una fazione o attività", emoji="🏛️"),
            discord.SelectOption(label="Richiesta Amministrazione", description="Candidati o contatta la direzione del server", emoji="🛡️"),
            discord.SelectOption(label="Partnership / Collaborazione", description="Proponi una collaborazione o partnership", emoji="🤝"),
            discord.SelectOption(label="Assistenza Generale", description="Domande generali sul server o sul Discord", emoji="❓"),
            discord.SelectOption(label="Assistenza In-Game", description="Problemi, bug o supporto dentro Emergency Hamburg", emoji="🎮"),
            discord.SelectOption(label="Altro", description="Qualsiasi altra tipologia di richiesta", emoji="📌")
        ]
        super().__init__(placeholder="seleziona la categoria del ticket...", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        categoria_scelta = self.values[0]

        existing_channel = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing_channel:
            await interaction.response.send_message(f"❌ Hai già un ticket aperto: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        categoria = interaction.channel.category
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=categoria,
            overwrites=overwrites,
            topic=f"Ticket [{categoria_scelta}] aperto da {user.name} (ID: {user.id})"
        )

        staff_role = discord.utils.get(guild.roles, name="Staff")
        staff_mention = staff_role.mention if staff_role else "@Staff"

        embed = discord.Embed(
            title=f"🎟️ Ticket: {categoria_scelta}",
            description=f"Benvenuto {user.mention}!\nHai aperto un ticket per la categoria: **{categoria_scelta}**.\n\nEsponi pure tutti i dettagli della tua richiesta. Lo staff ti risponderà il prima possibile.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Clicca sul bottone qui sotto per chiudere il ticket quando avrai risolto.")

        await ticket_channel.send(content=f"{user.mention} {staff_mention}", embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Il tuo ticket è stato creato con successo: {ticket_channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.tree.command(name="setup_ticket", description="Invia il pannello avanzato dei ticket (Solo Admin)")
@app_commands.default_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Centro Assistenza & Supporto Ufficiale",
        description="Hai bisogno di aiuto, vuoi inviare una richiesta o candidarti?\n\n**Seleziona dal menu a tendina qui sotto la categoria** più adatta alla tua esigenza per aprire un canale privato con lo staff.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Emergency Hamburg RP - Sistema Ticket Avanzato")
    
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Pannello dei ticket avanzato creato con successo in questo canale!", ephemeral=True)


# ==========================================
# AVVIO DEL BOT
# ==========================================
bot.run(os.getenv('DISCORD_TOKEN'))
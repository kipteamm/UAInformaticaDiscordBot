from datetime import datetime
from discord import app_commands

import database
import requests
import discord
import secret


GUILD_ID = 1385668310573781102
ROLE_ID = 1385668379767210096


def send_email(receiver: str, code: str):
    data = {
        "access_code": secret.WEBHOOK_ACCESS,
        "email": receiver,
        "code": code
    }

    response = requests.post(secret.WEBHOOK_URL, json=data)
    if not response.ok:
        raise Exception(f"Failed to send email: {response.text}")


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


class EmailModal(discord.ui.Modal, title="Vul je e-mailadres in"):
    email_input = discord.ui.TextInput(label="...@student.uantwerpen.be e-mailadres", placeholder="john.doe@student.uantwerpen.be")

    async def on_submit(self, interaction: discord.Interaction):
        email = self.email_input.value
        if not "@" in email:
            await interaction.response.send_message("❌ Incorrect e-mailadres.", ephemeral=False)
            return
        
        suffix = email.split("@")[1]
        if suffix != "student.uantwerpen.be":
            await interaction.response.send_message("❌ U kunt enkel UAntwerpen studenten emails gebruiken.", ephemeral=True)
            return
        
        if database.email_exists(email):
            await interaction.response.send_message("❌ Dit email adres is al gekoppeld aan een account. Contacteer <@675316333780533268> indien dit een misverstand zou zijn.", ephemeral=True)
            return

        if database.is_pending(interaction.user.id) and not database.can_retry(interaction.user.id):
            await interaction.response.send_message("❌ U kunt niet meer opnieuw proberen, contacteer <@675316333780533268>.")
            return

        try:
            await interaction.response.send_message(
                "🔄 Bezig met verzenden van verificatie-e-mail...",
                ephemeral=True
            )

            code = database.create_entry(interaction.user.id, email)
            send_email(email, code)
            await interaction.edit_original_response(content=f"✅ Een verificatie-e-mail is verstuurd naar **{email}**! Het kan maximaal **5 minuten** duren voordat deze aankomt. Controleer ook zeker je **spam/junk** folder.")

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Kon verificatie-e-mail niet verzenden, contacteer <@675316333780533268> met deze error: `{e}`.", ephemeral=True)


class CodeModal(discord.ui.Modal, title="Voer je code in"):
    code_input = discord.ui.TextInput(label="Verificatiecode verkregen per email.", placeholder="ABC123", min_length=6, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip()

        if len(code) != 6 or not code.isalnum():
            await interaction.response.send_message("❌ Incorrecte code.", ephemeral=True)
            return

        success, _message = database.verify_code(interaction.user.id, code)
        if success:
            guild = client.get_guild(GUILD_ID)
            if not guild:
                print("Guild not found.")
                return

            role = guild.get_role(ROLE_ID)
            if not role:
                print("Role not found.")
                return

            member = await guild.fetch_member(interaction.user.id)
            if not member:
                print("Member not found.")
                return

            await member.add_roles(role)

        await interaction.response.send_message(_message, ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Stuur code", style=discord.ButtonStyle.success, custom_id="send_code")
    async def send_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmailModal())

    @discord.ui.button(label="Verifieer account", style=discord.ButtonStyle.secondary, custom_id="verify_account")
    async def verify_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeModal())


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == ".embed":
        if not message.author.guild_permissions.administrator:
            return

        embed = discord.Embed(
            title="Verifieer je account",
            description=(
                "Welkom bij de Informatica Discord server!\n\n"
                "Om toegang te krijgen, vragen we je vriendelijk om je UAntwerpen studenten e-mailadres te gebruiken.\n"
                "1. Klik op **Stuur code** om een verificatiecode te ontvangen per e-mail van `informatica.uantwerpen@gmail.com`.\n"
                "2. Klik vervolgens op **Verifieer account** en vul je code in.\n\n"
                "_Wanneer je je account verifieert, stem je ermee in dat moderatoren het aan jouw account gekoppelde e-mailadres kunnen opvragen in geval van misbruik of het overtreden van regels. Moderatoren mogen dit uitsluitend doen met een geldige reden. Medestudenten zullen in geen enkel geval toegang krijgen tot deze gegevens._\n"
                "-# Bij klachten, problemen of vragen, contacteer <@675316333780533268>." # <@&1291026286063386624>
            ),
            color=0x003a5f
        )
        await message.channel.send(embed=embed, view=VerificationView())


@tree.command(name="whois", description="Toon informatie over een gebruiker")
@app_commands.describe(user="De gebruiker waarvan je info wil zien")
@app_commands.checks.has_role(1291026286063386624)
async def whois(interaction: discord.Interaction, user: discord.Member):
    data = database.get_email(user.id)
    if not data:
        return await interaction.response.send_message("Gebruiker is niet geverifieerd", ephemeral=True)

    embed = discord.Embed(
        title=f"Info over {user}",
        description=(
            f"<@{user.id}> `{user.id}`\n"
            f"**Username:** `{user.global_name}`\n"
            f"**Nickname:** `{user.display_name}`\n"
            f"**Discord lid sinds:** <t:{round(user.created_at.timestamp())}:f>\n"
            f"**Server lid sinds:** <t:{round(user.joined_at.timestamp())}:f>\n"
            f"**Geverifieerd op:** <t:{round(data[2]) if data else None}:f>\n"
            f"**Verificatie pogingen** `{data[1] + 1 if data else None}`\n"
            f"**Email:** ||`{data[0] if data else None}`||"
        ),
        color=0x003a5f
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            "Je hebt niet de juiste permissions om dit commando te gebruiken!", 
            ephemeral=True
        )


@client.event
async def on_member_remove(member):
    database.remove_entry(member.id)


@client.event
async def on_ready():
    client.add_view(VerificationView())
    # await tree.sync()
    await tree.sync(guild=discord.Object(id=1385668310573781102))
    print(f"Logged in as {client.user}!")


client.run(secret.DISCORD_TOKEN)

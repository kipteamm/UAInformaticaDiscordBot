import database
import requests
import discord
import secret


GUILD_ID = 1385668310573781102
ROLE_ID = 1385668379767210096


def send_html_email(receiver: str, code: str):
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


class EmailModal(discord.ui.Modal, title="Vul je e-mailadres in"):
    email_input = discord.ui.TextInput(label="UAntwerpen e-mailadres", placeholder="john.doe@student.uantwerpen.be")

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
            code = database.create_entry(interaction.user.id, email)
            send_html_email(email, code)
            await interaction.response.send_message(f"✅ Een verificatie-e-mail is verstuurd naar **{email}**! Het kan maximaal **5 minuten** duren voordat deze aankomt. Controleer ook zeker je **spam/junk** folder.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Kon verificatie-e-mail niet verzenden, contacteer <@675316333780533268> met deze error: `{e}`.", ephemeral=True)


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
            await message.channel.send("❌ Je hebt geen toestemming om dit commando te gebruiken.")
            return

        embed = discord.Embed(
            title="Verifieer je account",
            description=(
                "Welkom bij de Informatica Discord server!\n\n"
                "Om toegang te krijgen, vragen we je vriendelijk om je UAntwerpen studenten e-mailadres te gebruiken.\n"
                "1. Klik op **Stuur code** om een verificatiecode te ontvangen per e-mail.\n"
                "2. Klik vervolgens op **Verifieer account** en vul je code in.\n\n"
                "-# Indien u problemen ondervindt, of in het geval dat de bot offline is, contacteer <@675316333780533268>." # <@&1291026286063386624>
            ),
            color=0x003a5f
        )
        await message.channel.send(embed=embed, view=VerificationView())


@client.event
async def on_member_remove(member):
    database.remove_entry(member.id)


@client.event
async def on_ready():
    client.add_view(VerificationView())
    print(f"Logged in as {client.user}!")


client.run(secret.DISCORD_TOKEN)

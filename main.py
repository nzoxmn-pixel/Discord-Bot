import discord
from discord.ext import commands
import os
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 3단계: 로블록스 아이디를 입력받는 모달(팝업창) 클래스
class RobloxVerifyModal(discord.ui.Modal, title="로블록스 계정 인증"):
    roblox_username = discord.ui.TextInput(
        label="로블록스 닉네임",
        placeholder="사용 중인 로블록스 정확한 닉네임을 입력하세요",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        username = self.roblox_username.value.strip()
        
        # 안내 메시지 (API 조회 중 대기)
        await interaction.response.defer(ephemeral=True)

        # 로블록스 API로 계정 존재 여부 확인
        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username]}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ 로블록스 API 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", ephemeral=True)
                    return
                
                data = await resp.json()
                
                # 유저가 존재하지 않는 경우
                if not data.get("data") or len(data["data"]) == 0:
                    await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다. 닉네임을 다시 확인해 주세요.", ephemeral=True)
                    return

                # 계정이 존재하는 경우 -> 'Verified' 역할 부여
                roblox_id = data["data"][0]["id"]
                display_name = data["data"][0]["displayName"]
                
                role = discord.utils.get(interaction.guild.roles, name="Verified")
                if not role:
                    await interaction.followup.send("❌ 서버에 'Verified' 역할이 설정되어 있지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
                    return

                # 이미 역할이 있는지 확인
                if role in interaction.user.roles:
                    await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (연동된 계정: **{display_name}**)", ephemeral=True)
                    return

                try:
                    await interaction.user.add_roles(role)
                    await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**(ID: {roblox_id})와 연동되어 **Verified** 역할이 지급되었습니다. 이제 다른 채널을 이용하실 수 있습니다!", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ 역할을 부여하는 중에 권한 오류가 발생했습니다. 봇의 역할 위치가 'Verified' 역할보다 위에 있는지 확인해 주세요.", ephemeral=True)

# 2단계: 인증 버튼 클래스
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.green, custom_id="verify_button_modal")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼을 누르면 모달 창 띄우기
        await interaction.response.send_modal(RobloxVerifyModal())

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    bot.add_view(VerifyView())
    await bot.change_presence(activity=discord.Game(name="!인증패널 입력하기"))

# 1단계: 관리자가 #인증 채널에서 패널을 생성하는 명령어
@bot.command(name='인증패널')
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    if ctx.channel.name != "인증":
        await ctx.send("❌ 이 명령어는 **#인증** 채널에서만 사용할 수 있습니다.", delete_after=5)
        return

    embed = discord.Embed(
        title="🛡️ 로블록스 디스코드 연동 인증",
        description="서버를 이용하려면 아래의 **[로블록스 인증하기]** 버튼을 누르고 본인의 로블록스 닉네임을 입력해 주세요!",
        color=0x00ff00
    )
    
    await ctx.send(embed=embed, view=VerifyView())

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

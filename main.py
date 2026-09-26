import discord
from discord.ext import commands
import os
import aiohttp
import traceback

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

class RobloxVerifyModal(discord.ui.Modal, title="로블록스 계정 인증"):
    roblox_username = discord.ui.TextInput(
        label="로블록스 닉네임",
        placeholder="사용 중인 로블록스 정확한 닉네임을 입력하세요",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        username = self.roblox_username.value.strip()
        print(f"[디버깅] 유저가 입력한 닉네임: {username}")
        
        try:
            # 1. 디스코드 응답 지연 처리
            await interaction.response.defer(ephemeral=True)
            print("[디버깅] interaction.response.defer 성공")

            # 2. 로블록스 API 호출
            url = "https://users.roblox.com/v1/usernames/users"
            payload = {"usernames": [username]}
            print(f"[디버깅] 로블록스 API 요청 보냄: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    print(f"[디버깅] 로블록스 API 응답 코드: {resp.status}")
                    if resp.status != 200:
                        await interaction.followup.send("❌ 로블록스 API 서버와 통신 중 오류가 발생했습니다.", ephemeral=True)
                        return
                    
                    data = await resp.json()
                    print(f"[디버깅] API 응답 데이터: {data}")
                    
                    if not data.get("data") or len(data["data"]) == 0:
                        await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다.", ephemeral=True)
                        return

                    roblox_id = data["data"][0]["id"]
                    display_name = data["data"][0]["displayName"]
                    
                    role = discord.utils.get(interaction.guild.roles, name="Verified")
                    if not role:
                        await interaction.followup.send("❌ 서버에 'Verified' 역할이 없습니다. 관리자에게 문의하세요.", ephemeral=True)
                        return

                    if role in interaction.user.roles:
                        await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (연동된 계정: **{display_name}**)", ephemeral=True)
                        return

                    await interaction.user.add_roles(role)
                    print(f"[디버깅] {interaction.user.name} 님에게 Verified 역할 부여 완료!")
                    await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**과(와) 연동되었습니다.", ephemeral=True)

        except Exception as e:
            print(f"[에러 발생!] {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ 처리 중 에러가 발생했습니다: {e}", ephemeral=True)
            except:
                pass

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.green, custom_id="verify_button_modal")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("[디버깅] 인증하기 버튼 클릭됨, 모달창 띄우기 시도")
        await interaction.response.send_modal(RobloxVerifyModal())

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    bot.add_view(VerifyView())
    await bot.change_presence(activity=discord.Game(name="!인증패널 입력하기"))

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

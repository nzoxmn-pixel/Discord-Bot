import discord
from discord.ext import commands
import os
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 1. 로블록스 아이디를 입력받는 모달(팝업 창)
class RobloxVerifyModal(discord.ui.Modal, title="로블록스 계정 인증"):
    roblox_username = discord.ui.TextInput(
        label="로블록스 닉네임",
        placeholder="사용 중인 로블록스 정확한 닉네임을 입력하세요",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        username = self.roblox_username.value.strip()
        
        # 디스코드 응답 시간 제한(3초) 방지용 선응답
        await interaction.response.defer(ephemeral=True)

        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username]}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("❌ 로블록스 API 서버와 통신 중 오류가 발생했습니다.", ephemeral=True)
                        return
                    
                    data = await resp.json()
                    
                    if not data.get("data") or len(data["data"]) == 0:
                        await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다. 닉네임을 다시 확인해 주세요.", ephemeral=True)
                        return

                    roblox_id = data["data"][0]["id"]
                    display_name = data["data"][0]["displayName"]
                    
                    role = discord.utils.get(interaction.guild.roles, name="Verified")
                    if not role:
                        await interaction.followup.send("❌ 서버에 'Verified' 역할이 설정되어 있지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
                        return

                    if role in interaction.user.roles:
                        await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (연동된 계정: **{display_name}**)", ephemeral=True)
                        return

                    await interaction.user.add_roles(role)
                    await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**(ID: {roblox_id})와 연동되어 **Verified** 역할이 지급되었습니다.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ 처리 중 오류가 발생했습니다: {e}", ephemeral=True)

# 2. 버튼 뷰 클래스
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.green, custom_id="persistent_roblox_verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobloxVerifyModal())

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    if not any(isinstance(view, VerifyView) for view in bot.persistent_views):
        bot.add_view(VerifyView())
    await bot.change_presence(activity=discord.Game(name="!인증패널 입력하기"))

# 3. 인증 패널 생성 명령어
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

# 4. 메시지 청소 명령어 (!청소 [개수])
@bot.command(name='청소', aliases=['clear', '삭제'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    # 명령어 자체 메시지 포함해서 지정한 개수만큼 삭제 (+1은 명령어 메시지)
    deleted = await ctx.channel.purge(limit=amount + 1)
    
    # 안내 메시지를 잠깐 띄웠다가 3초 뒤에 삭제
    msg = await ctx.send(f"🧹 총 **{len(deleted) - 1}개**의 메시지를 깔끔하게 청소했습니다!", delete_after=3)

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

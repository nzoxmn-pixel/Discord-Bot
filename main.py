import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 인증 버튼을 포함하는 뷰 클래스
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 시간 제한 없이 버튼이 계속 유지되도록 설정

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 서버에 있는 'Verified' 역할을 찾습니다.
        role = discord.utils.get(interaction.guild.roles, name="Verified")
        
        if not role:
            await interaction.response.send_message("❌ 서버에 'Verified' 역할이 없습니다! 관리자에게 문의하세요.", ephemeral=True)
            return

        # 이미 인증된 경우
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ 이미 인증이 완료된 계정입니다!", ephemeral=True)
            return

        # 역할 부여
        await interaction.user.add_roles(role)
        await interaction.response.send_message("🎉 인증이 완료되었습니다! 이제 서버의 다른 채널들을 이용하실 수 있습니다.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    # 봇이 켜질 때 버튼 상호작용이 끊기지 않도록 뷰 등록
    bot.add_view(VerifyView())
    await bot.change_presence(activity=discord.Game(name="버튼을 눌러 인증하세요!"))

# 관리자가 #인증 채널에서 '!인증패널'이라고 치면 버튼 메시지를 생성해 주는 명령어
@bot.command(name='인증패널')
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    if ctx.channel.name != "인증":
        await ctx.send("❌ 이 명령어는 **#인증** 채널에서만 사용할 수 있습니다.", delete_after=5)
        return

    embed = discord.Embed(
        title="🛡️ 서버 이용 인증",
        description="아래의 **[인증하기]** 버튼을 누르면 서버를 정상적으로 이용하실 수 있습니다!",
        color=0x00ff00
    )
    
    # 버튼과 함께 메시지 전송
    await ctx.send(embed=embed, view=VerifyView())

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

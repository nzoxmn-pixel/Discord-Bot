import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    await bot.change_presence(activity=discord.Game(name="!인증 치고 로블록스 연동하기"))

@bot.command(name='인증')
async def verify(ctx):
    # 📌 여기에 '인증' 채널의 이름을 적어줍니다. (다른 채널이면 작동 안 함)
    if ctx.channel.name != "인증":
        await ctx.send("❌ 이 명령어는 **#인증** 채널에서만 사용할 수 있어요!", delete_after=5)
        return

    embed = discord.Embed(
        title="로블록스 디스코드 연동 인증",
        description="서버 이용을 위해 로블록스 계정을 연동해 주세요!",
        color=0x00ff00
    )
    embed.add_field(name="인증 방법", value="여기에 나중에 로블록스 인증 링크나 안내를 넣을 수 있어요.", inline=False)
    await ctx.send(embed=embed)

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

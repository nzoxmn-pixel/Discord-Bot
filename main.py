import discord
from discord.ext import commands, tasks
import os
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 기본 환율 설정
SERVER_CONFIG = {
    "rate": 1250  # 1만 원당 기본 1,250 로벅스
}

# 1. 로블록스 아이디 인증 모달
class RobloxVerifyModal(discord.ui.Modal, title="로블록스 계정 인증"):
    roblox_username = discord.ui.TextInput(
        label="로블록스 아이디",
        placeholder="사용 중인 로블록스 아이디를 입력하세요",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        username = self.roblox_username.value.strip()
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
                        await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다.", ephemeral=True)
                        return

                    user_info = data["data"][0]
                    roblox_id = user_info["id"]
                    display_name = user_info["displayName"]
                    name = user_info["name"]

                avatar_url = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
                params = {"userIds": roblox_id, "size": "150x150", "format": "Png", "isCircular": "false"}
                
                async with session.get(avatar_url, params=params) as avatar_resp:
                    avatar_data = await avatar_resp.json()
                    headshot_url = ""
                    if avatar_data.get("data") and len(avatar_data["data"]) > 0:
                        headshot_url = avatar_data["data"][0]["imageUrl"]

                role = discord.utils.get(interaction.guild.roles, name="Verified")
                if not role:
                    await interaction.followup.send("❌ 서버에 'Verified' 역할이 설정되어 있지 않습니다.", ephemeral=True)
                    return

                if role in interaction.user.roles:
                    await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (**{display_name}**)", ephemeral=True)
                    return

                await interaction.user.add_roles(role)
                await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**과 연동되었습니다.", ephemeral=True)

                target_channel = discord.utils.find(lambda c: "한국인-플레이어" in c.name, interaction.guild.text_channels)
                if target_channel:
                    embed = discord.Embed(
                        title="✨ 새로운 플레이어 인증 완료!",
                        description=f"디스코드 유저 {interaction.user.mention} 님의 연동 정보입니다.",
                        color=0x00ff00
                    )
                    embed.add_field(name="아이디", value=f"`{name}`", inline=True)
                    embed.add_field(name="표시 이름", value=f"`{display_name}`", inline=True)
                    if headshot_url:
                        embed.set_thumbnail(url=headshot_url)
                    await target_channel.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.green, custom_id="persistent_roblox_verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobloxVerifyModal())

# 2. 로벅스 계산기 팝업 입력 모달들
class CalcKrwModal(discord.ui.Modal, title="원화 ➔ 로벅스 계산"):
    krw_input = discord.ui.TextInput(label="원화 금액 (원)", placeholder="예: 10000", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            krw = int(self.krw_input.value.strip().replace(",", ""))
            rate = SERVER_CONFIG["rate"]
            robux = int(krw * (rate / 10000))
            await interaction.response.send_message(f"🧮 **{krw:,}원** ➔ 약 **+{robux:,} R$** (적용 환율: 1만 원당 {rate:,}룹)", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요!", ephemeral=True)

class CalcRobuxModal(discord.ui.Modal, title="로벅스 ➔ 원화 역계산"):
    robux_input = discord.ui.TextInput(label="로벅스 금액 (R$)", placeholder="예: 1300", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            robux = int(self.robux_input.value.strip().replace(",", ""))
            rate = SERVER_CONFIG["rate"]
            krw = int((robux / rate) * 10000)
            await interaction.response.send_message(f"💵 **{robux:,} R$** ➔ 필요 금액 약 **~ {krw:,}원** (적용 환율: 1만 원당 {rate:,}룹)", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요!", ephemeral=True)

class CalcFeeModal(discord.ui.Modal, title="마켓플레이스 수수료 계산"):
    fee_input = discord.ui.TextInput(label="판매 등록 로벅스 (R$)", placeholder="예: 1000", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.fee_input.value.strip().replace(",", ""))
            net = int(amount * 0.7)
            tax = amount - net
            await interaction.response.send_message(f"🏷️ 판매가: `{amount:,} R$` | 수수료(30%): `-{tax:,} R$` | **실제 수령액(70%): `+{net:,} R$`**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요!", ephemeral=True)

# 3. 버튼형 UI 뷰 클래스
class RobuxCalcView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🧮 원화로 계산", style=discord.ButtonStyle.success, custom_id="calc_krw_btn")
    async def btn_calc_krw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CalcKrwModal())

    @discord.ui.button(label="💵 로벅스로 역계산", style=discord.ButtonStyle.primary, custom_id="calc_robux_btn")
    async def btn_calc_robux(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CalcRobuxModal())

    @discord.ui.button(label="🏷️ 30% 수수료 계산", style=discord.ButtonStyle.secondary, custom_id="calc_fee_btn")
    async def btn_calc_fee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CalcFeeModal())

@tasks.loop(hours=1)
async def background_automation_task():
    for guild in bot.guilds:
        target_channel = discord.utils.find(lambda c: "공지" in c.name, guild.text_channels)
        if target_channel:
            pass

@background_automation_task.before_loop
async def before_background_automation_task():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'로그인 완료: {bot.user} (ID: {bot.user.id})')
    if not any(isinstance(view, VerifyView) for view in bot.persistent_views):
        bot.add_view(VerifyView())
    if not any(isinstance(view, RobuxCalcView) for view in bot.persistent_views):
        bot.add_view(RobuxCalcView())
    
    await bot.change_presence(activity=discord.Game(name="!계산패널 입력하기"))
    
    if not background_automation_task.is_running():
        background_automation_task.start()

# 인증 패널 생성 명령어
@bot.command(name='인증패널')
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    embed = discord.Embed(
        title="🛡️ 로블록스 디스코드 연동 인증",
        description="버튼을 눌러 본인의 로블록스 **아이디**를 입력해 주세요!",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=VerifyView())

# 로벅스 계산기 UI 패널 생성 명령어 (!계산패널)
@bot.command(name='계산패널', aliases=['로벅스패널'])
@commands.has_permissions(administrator=True)
async def robux_panel(ctx):
    await ctx.message.delete()
    current_rate = SERVER_CONFIG["rate"]
    
    embed = discord.Embed(
        title="💰 데스볼 로벅스 거래 계산기",
        description=f"버튼을 클릭하여 원하는 계산을 편리하게 진행하세요!\n\n📌 **현재 적용 환율:** 10,000원당 **`{current_rate:,} R$`**",
        color=0xF1C40F
    )
    embed.set_footer(text="※ 본 계산기는 서버 거래 편의를 위해 제공됩니다.")
    await ctx.send(embed=embed, view=RobuxCalcView())

# 관리자 환율 설정 명령어 (!환율 [금액])
@bot.command(name='환율', aliases=['세팅'])
@commands.has_permissions(administrator=True)
async def set_robux_rate(ctx, new_rate: int):
    if new_rate <= 0:
        await ctx.send("❌ 환율은 0보다 커야 합니다!", delete_after=5)
        return
    
    SERVER_CONFIG["rate"] = new_rate
    embed = discord.Embed(
        title="⚙️ 거래 환율 변경 완료",
        description=f"이제부터 모든 계산에 **10,000원당 `{new_rate:,} R$`** 환율이 적용됩니다!",
        color=0xE67E22
    )
    await ctx.send(embed=embed)

# 관리자용 공지 명령어
@bot.command(name='공지', aliases=['notice'])
@commands.has_permissions(administrator=True)
async def notice_command(ctx, *, text: str):
    await ctx.message.delete()
    embed = discord.Embed(title="📢 서버 공지사항", description=text, color=0x5865F2)
    await ctx.send(embed=embed)

# 청소 명령어
@bot.command(name='청소', aliases=['clear'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 30):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: not m.author.bot)
    await ctx.send(f"🧹 일반 유저 메시지 **{len(deleted)}개** 청소 완료!", delete_after=3)

@bot.command(name='봇청소', aliases=['botclear'])
@commands.has_permissions(manage_messages=True)
async def clear_bot_messages(ctx, amount: int = 30):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot)
    await ctx.send(f"🤖 봇 메시지 **{len(deleted)}개** 청소 완료!", delete_after=3)

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

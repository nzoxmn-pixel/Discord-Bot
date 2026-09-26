import discord
from discord.ext import commands, tasks
import os
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 기본 환율 설정 (1만 원당 기본 로벅스, 관리자가 바꿀 수 있음)
SERVER_CONFIG = {
    "rate": 1250  # 기본값: 1만 원당 1,250 로벅스
}

# 1. 로블록스 아이디를 입력받는 모달(팝업 창)
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
                        await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다. 아이디를 다시 확인해 주세요.", ephemeral=True)
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
                    await interaction.followup.send("❌ 서버에 'Verified' 역할이 설정되어 있지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
                    return

                if role in interaction.user.roles:
                    await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (연동된 계정: **{display_name}**)", ephemeral=True)
                    return

                await interaction.user.add_roles(role)
                await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**(ID: {roblox_id})와 연동되어 **Verified** 역할이 지급되었습니다.", ephemeral=True)

                target_channel = discord.utils.find(lambda c: "한국인-플레이어" in c.name, interaction.guild.text_channels)
                if target_channel:
                    embed = discord.Embed(
                        title="✨ 새로운 플레이어 인증 완료!",
                        description=f"디스코드 유저 {interaction.user.mention} 님의 로블록스 계정 연동 정보입니다.",
                        color=0x00ff00
                    )
                    embed.add_field(name="아이디 (Username)", value=f"`{name}`", inline=True)
                    embed.add_field(name="표시 이름 (Display Name)", value=f"`{display_name}`", inline=True)
                    embed.add_field(name="로블록스 ID", value=f"`{roblox_id}`", inline=False)
                    
                    if headshot_url:
                        embed.set_thumbnail(url=headshot_url)
                    
                    embed.set_footer(text=f"디스코드 ID: {interaction.user.id}")
                    await target_channel.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ 처리 중 오류가 발생했습니다: {e}", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.green, custom_id="persistent_roblox_verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobloxVerifyModal())

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
    await bot.change_presence(activity=discord.Game(name="!인증패널 입력하기"))
    
    if not background_automation_task.is_running():
        background_automation_task.start()

# 3. 인증 패널 생성 명령어
@bot.command(name='인증패널')
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    if "인증" not in ctx.channel.name:
        await ctx.send("❌ 이 명령어는 **인증** 관련 채널에서만 사용할 수 있습니다.", delete_after=5)
        return

    embed = discord.Embed(
        title="🛡️ 로블록스 디스코드 연동 인증",
        description="서버를 이용하려면 아래의 **[로블록스 인증하기]** 버튼을 누르고 본인의 로블록스 **아이디**를 입력해 주세요!",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=VerifyView())

# 4. 맞춤형 로벅스 거래 & 환산 계산기
@bot.group(name='로벅스', aliases=['robux'], invoke_without_command=True)
async def robux_calculator(ctx):
    current_rate = SERVER_CONFIG["rate"]
    embed = discord.Embed(
        title="💰 맞춤형 로벅스 거래 계산기",
        description=f"현재 설정된 기준: **10,000원당 `{current_rate:,} R$`**",
        color=0xF1C40F
    )
    embed.add_field(
        name="🧮 원화 ➔ 로벅스 계산 (`!로벅스 계산 [원화금액]`)",
        value="예: `!로벅스 계산 10000` (입력한 돈으로 몇 룹을 받는지 계산)",
        inline=False
    )
    embed.add_field(
        name="💵 로벅스 ➔ 원화 계산 (`!로벅스 역계산 [로벅스]`)",
        value="예: `!로벅스 역계산 1300` (이만큼 사려면 얼마를 내야 하는지 계산)",
        inline=False
    )
    embed.add_field(
        name="🏷️ 마켓플레이스 30% 수수료 (`!로벅스 수수료 [금액]`)",
        value="예: `!로벅스 수수료 1000` (수수료 떼고 실제 들어오는 순수 로벅스 계산)",
        inline=False
    )
    embed.add_field(
        name="⚙️ 환율 설정 [관리자 전용] (`!로벅스 환율 [1만 원당 로벅스]`)",
        value="예: `!로벅스 환율 1200` (서버 전체 적용 환율 변경)",
        inline=False
    )
    await ctx.send(embed=embed)

@robux_calculator.command(name='계산', aliases=['환산', '구매'])
async def robux_calc(ctx, krw: int):
    rate = SERVER_CONFIG["rate"]
    # 1만 원당 rate 만큼 주므로, 1원당 (rate / 10000)
    calculated_robux = int(krw * (rate / 10000))
    
    embed = discord.Embed(
        title="🧮 원화 환산 결과",
        color=0x2ECC71
    )
    embed.add_field(name="지불할 금액", value=f"`{krw:,} 원`", inline=False)
    embed.add_field(name="적용 환율", value=f"10,000원 = `{rate:,} R$`", inline=False)
    embed.add_field(name="받게 되는 로벅스", value=f"약 `+ {calculated_robux:,} R$`", inline=False)
    await ctx.send(embed=embed)

@robux_calculator.command(name='역계산', aliases=['필요금액'])
async def robux_reverse_calc(ctx, robux: int):
    rate = SERVER_CONFIG["rate"]
    # 필요한 원화 = (로벅스 / rate) * 10000
    needed_krw = int((robux / rate) * 10000)
    
    embed = discord.Embed(
        title="💵 로벅스 기준 필요 금액",
        color=0x9B59B6
    )
    embed.add_field(name="원하는 로벅스", value=f"`{robux:,} R$`", inline=False)
    embed.add_field(name="적용 환율", value=f"10,000원 = `{rate:,} R$`", inline=False)
    embed.add_field(name="입금해야 할 금액", value=f"약 `~ {needed_krw:,} 원`", inline=False)
    await ctx.send(embed=embed)

@robux_calculator.command(name='수수료', aliases=['세금', 'fee'])
async def robux_fee(ctx, amount: int):
    net = int(amount * 0.7)
    tax = amount - net
    
    embed = discord.Embed(
        title="🏷️ 마켓플레이스 수수료 계산 결과",
        color=0x3498DB
    )
    embed.add_field(name="판매 등록 가격", value=f"`{amount:,} R$`", inline=False)
    embed.add_field(name="로블록스 수수료 (30%)", value=f"`-{tax:,} R$`", inline=True)
    embed.add_field(name="실제 들어오는 금액 (70%)", value=f"`+{net:,} R$`", inline=True)
    await ctx.send(embed=embed)

@robux_calculator.command(name='환율', aliases=['설정'])
@commands.has_permissions(administrator=True)
async def set_robux_rate(ctx, new_rate: int):
    if new_rate <= 0:
        await ctx.send("❌ 환율은 0보다 커야 합니다!", delete_after=5)
        return
    
    SERVER_CONFIG["rate"] = new_rate
    embed = discord.Embed(
        title="⚙️ 로벅스 거래 환율 변경 완료",
        description=f"이제부터 모든 계산에 **10,000원당 `{new_rate:,} R$`** 환율이 적용됩니다!",
        color=0xE67E22
    )
    await ctx.send(embed=embed)

# 5. 관리자용 공지 임베드 전송 명령어 (!공지 [내용])
@bot.command(name='공지', aliases=['notice', '공지사항'])
@commands.has_permissions(administrator=True)
async def notice_command(ctx, *, text: str):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="📢 서버 공지사항",
        description=text,
        color=0x5865F2
    )
    
    icon_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
    embed.set_footer(text=f"작성자: {ctx.author.display_name}", icon_url=icon_url)
    
    await ctx.send(embed=embed)

# 6. 일반 유저 채팅만 골라서 지우는 명령어 (!청소 [개수])
@bot.command(name='청소', aliases=['clear', '삭제'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 30):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: not m.author.bot)
    await ctx.send(f"🧹 일반 유저의 메시지 총 **{len(deleted)}개**를 청소했습니다!", delete_after=3)

# 7. 봇이 보낸 메시지만 골라서 지우는 명령어 친절하게 (!봇청소 [개수])
@bot.command(name='봇청소', aliases=['botclear'])
@commands.has_permissions(manage_messages=True)
async def clear_bot_messages(ctx, amount: int = 30):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot)
    await ctx.send(f"🤖 봇이 보낸 메시지 총 **{len(deleted)}개**를 청소했습니다!", delete_after=3)

token = os.getenv("TOKEN")
if token is None:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

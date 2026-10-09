import os
import discord
from discord.ext import commands
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_bank = {}

@bot.event
async def on_ready():
    bot.add_view(TradeCalcView())
    bot.add_view(VerifyView())
    print(f"로그인 완료: {bot.user}")

async def get_item_thumbnail(item_id: int):
    url = f"https://thumbnails.roblox.com/v1/assets?assetIds={item_id}&returnPolicy=PlaceHolder&size=420x420&format=Png&isCircular=false"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        return data["data"][0].get("imageUrl")
    except Exception:
        pass
    return None

async def fetch_item_embed(item_id: int):
    rolimons_url = "https://www.rolimons.com/itemapi/itemdetails"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(rolimons_url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception:
        return None
            
    item_str = str(item_id)
    if "items" not in data or item_str not in data["items"]:
        return None

    item_info = data["items"][item_str]
    item_name = item_info[0]
    rap = item_info[2]
    value = item_info[3]
    
    demand_dict = {-1: "알 수 없음", 0: "끔찍함", 1: "나쁨", 2: "보통", 3: "좋음", 4: "매우 높음"}
    trend_dict = {-2: "하락세(급감)", -1: "하락세", 0: "유지", 1: "상승세", 2: "상승세(급등)"}
    
    demand = demand_dict.get(item_info[5], "보통")
    trend = trend_dict.get(item_info[6], "유지")
    thumbnail_url = await get_item_thumbnail(item_id)

    embed = discord.Embed(
        title=f"🏷️ [{item_name}] 시세 정보",
        description=f"`🆔` **아이템 ID:** `{item_id}`",
        color=0x2B2D31
    )
    embed.add_field(name="✨ RAP (평균 거래가)", value=f"`{rap:,} R$`", inline=True)
    embed.add_field(name="💎 가치 (Value)", value=f"`{value:,} R$`", inline=True)
    embed.add_field(name="🔥 수요 (Demand)", value=f"`{demand}`", inline=True)
    embed.add_field(name="📈 트렌드", value=f"`{trend}`", inline=True)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed

# --- 모달 인터페이스 ---
class ItemModal(discord.ui.Modal, title="🔍 한정판 아이템 시세 조회"):
    item_id_input = discord.ui.TextInput(label="아이템 ID", placeholder="예: 10159600649", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            item_id = int(self.item_id_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요.", ephemeral=True)
        await interaction.response.defer(thinking=True)
        embed = await fetch_item_embed(item_id)
        if not embed:
            await interaction.followup.send("⚠️ 존재하지 않거나 한정판이 아닌 아이템 ID입니다.", ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

class KRWCalcModal(discord.ui.Modal, title="💵 원화 기준 환산"):
    krw_input = discord.ui.TextInput(label="원화 금액 (KRW)", placeholder="예: 10000", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try: krw = int(self.krw_input.value.strip())
        except ValueError: return await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        robux = int(krw / 10000 * 1250)
        embed = discord.Embed(title="💱 환산 결과", description=f"💵 **{krw:,}원**\n➡️ **{robux:,} R$**", color=0x57F287)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RobuxReverseModal(discord.ui.Modal, title="💰 로벅스 기준 역환산"):
    robux_input = discord.ui.TextInput(label="로벅스 금액 (R$)", placeholder="예: 1250", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try: robux = int(self.robux_input.value.strip())
        except ValueError: return await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        krw = int(robux / 1250 * 10000)
        embed = discord.Embed(title="💱 역환산 결과", description=f"💰 **{robux:,} R$**\n➡️ 약 **{krw:,}원**", color=0x57F287)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class FeeCalcModal(discord.ui.Modal, title="🏷️ 30% 수수료 계산기"):
    robux_input = discord.ui.TextInput(label="총 로벅스", placeholder="예: 1000", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try: amount = int(self.robux_input.value.strip())
        except ValueError: return await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        received = int(amount * 0.7)
        embed = discord.Embed(title="📊 수수료 정산 내역", color=0xFEE75C)
        embed.add_field(name="📦 입력 금액", value=f"`{amount:,} R$`", inline=False)
        embed.add_field(name="💸 수수료 (30%)", value=f"`{amount - received:,} R$`", inline=False)
        embed.add_field(name="✨ 실수령액 (70%)", value=f"`{received:,} R$`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BankActionModal(discord.ui.Modal):
    def __init__(self, action_type: str):
        self.action_type = action_type
        super().__init__(title="🏦 통장 입금" if action_type == "deposit" else "🏦 통장 출금")
        self.amount_input = discord.ui.TextInput(label="금액 (R$)", placeholder="예: 5000", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try: amount = int(self.amount_input.value.strip())
        except ValueError: return await interaction.response.send_message("❌ 숫자를 입력해주세요.", ephemeral=True)
        uid = interaction.user.id
        if uid not in user_bank: user_bank[uid] = 0
        if self.action_type == "deposit":
            user_bank[uid] += amount
            await interaction.response.send_message(f"📥 **{amount:,} R$**가 입금되었습니다.\n🔹 현재 잔액: `{user_bank[uid]:,} R$`", ephemeral=True)
        else:
            if user_bank[uid] < amount:
                await interaction.response.send_message(f"❌ 잔액이 부족합니다! (현재 잔액: `{user_bank[uid]:,} R$`)", ephemeral=True)
            else:
                user_bank[uid] -= amount
                await interaction.response.send_message(f"📤 **{amount:,} R$**가 출금되었습니다.\n🔹 현재 잔액: `{user_bank[uid]:,} R$`", ephemeral=True)

class RobloxVerifyModal(discord.ui.Modal, title="🛡️ 로블록스 계정 연동"):
    roblox_name = discord.ui.TextInput(label="로블록스 닉네임", placeholder="정확한 닉네임 입력", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.roblox_name.value.strip()
        role = discord.utils.get(interaction.guild.roles, name="인증됨")
        if not role:
            return await interaction.response.send_message("❌ 서버에 '인증됨' 역할이 없습니다.", ephemeral=True)
        try:
            try: await interaction.user.edit(nick=nickname)
            except: pass
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ 연동 완료! 닉네임이 **{nickname}**(으)로 변경되었습니다.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ 권한 오류가 발생했습니다.", ephemeral=True)

# --- 뷰 클래스 ---
class TradeCalcView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="시세 검색", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="calc_search", row=0)
    async def s(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(ItemModal())
    @discord.ui.button(label="원화 계산", style=discord.ButtonStyle.success, emoji="🟢", custom_id="calc_krw", row=0)
    async def k(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(KRWCalcModal())
    @discord.ui.button(label="로벅스 역계산", style=discord.ButtonStyle.secondary, emoji="💵", custom_id="calc_rev", row=0)
    async def r(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(RobuxReverseModal())
    @discord.ui.button(label="30% 수수료", style=discord.ButtonStyle.secondary, emoji="🏷️", custom_id="calc_fee", row=1)
    async def f(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(FeeCalcModal())
    @discord.ui.button(label="10% 공제 토글", style=discord.ButtonStyle.danger, emoji="✂️", custom_id="calc_toggle", row=1)
    async def t(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_message("🔄 출금 시 10% 공제 상태가 변경되었습니다.", ephemeral=True)
    @discord.ui.button(label="환율 설정", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="calc_rate", row=2)
    async def sr(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_message("⚙️ 환율 설정 시스템 (준비 중)", ephemeral=True)
    @discord.ui.button(label="가감액 설정", style=discord.ButtonStyle.secondary, emoji="⚖️", custom_id="calc_offset", row=2)
    async def so(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_message("⚖️ 가감액 설정 시스템 (준비 중)", ephemeral=True)
    @discord.ui.button(label="통장 입금", style=discord.ButtonStyle.success, emoji="📥", custom_id="calc_dep", row=3)
    async def dep(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(BankActionModal("deposit"))
    @discord.ui.button(label="통장 출금", style=discord.ButtonStyle.danger, emoji="📤", custom_id="calc_wit", row=3)
    async def wit(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(BankActionModal("withdraw"))

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="로블록스 계정 연동하기", style=discord.ButtonStyle.success, emoji="🔗", custom_id="verify_btn")
    async def v(self, i: discord.Interaction, b: discord.ui.Button): await i.response.send_modal(RobloxVerifyModal())

# --- 명령어 정의 ---
@bot.command(name="인증")
async def cmd_verify(ctx):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(title="🛡️ 로블록스 디스코드 연동 인증", description="아래 버튼을 눌러 본인의 닉네임을 입력하고 인증하세요!", color=0x57F287)
    await ctx.send(embed=embed, view=VerifyView())

@bot.command(name="로벅스")
async def cmd_robux(ctx):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(
        title="💰 로블록스 로벅스 거래 계산기",
        description="버튼을 클릭하여 원하는 계산을 편리하게 진행하세요!\n\n📌 **현재 적용 환율:** 10,000원당 `1,250 R$`\n➕ **추가/차감 가감액:** `+0 R$`\n🏦 **내 통장 잔액:** `0 R$`\n✂️ **출금 시 10% 공제:** 🔴 `꺼짐`",
        color=0xFEE75C
    )
    await ctx.send(embed=embed, view=TradeCalcView())

@bot.command(name="한정판")
async def cmd_limited(ctx, item_id: int = None):
    try: await ctx.message.delete()
    except: pass
    if item_id is None:
        embed = discord.Embed(title="🔍 한정판 시세 검색", description="`!한정판 [아이템ID]` 형식으로 입력하거나 아래 버튼을 누르세요.", color=0x3498DB)
        view = discord.ui.View()
        btn = discord.ui.Button(label="시세 검색하기", style=discord.ButtonStyle.primary, emoji="🔍")
        async def btn_cb(interaction: discord.Interaction):
            await interaction.response.send_modal(ItemModal())
        btn.callback = btn_cb
        view.add_item(btn)
        await ctx.send(embed=embed, view=view)
    else:
        embed = await fetch_item_embed(item_id)
        if not embed:
            await ctx.send("⚠️ 존재하지 않거나 한정판이 아닌 아이템 ID입니다.")
        else:
            await ctx.send(embed=embed)

@bot.command(name="청소")
@commands.has_permissions(manage_messages=True)
async def cmd_clear(ctx, amount: int = 10):
    try: await ctx.message.delete()
    except: pass
    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.channel.send(f"🧹 **{len(deleted)}개**의 메시지를 청소했습니다!")
    await msg.delete(delete_after=3)

@bot.command(name="봇청소")
@commands.has_permissions(manage_messages=True)
async def cmd_bot_clear(ctx, amount: int = 20):
    try: await ctx.message.delete()
    except: pass
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author == bot.user)
    msg = await ctx.channel.send(f"🧹 봇 메시지 **{len(deleted)}개**를 청소했습니다!")
    await msg.delete(delete_after=3)

token = os.getenv("TOKEN")
if not token:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

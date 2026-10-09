import os
import discord
from discord.ext import commands
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    bot.add_view(MainPanelView())
    print(f"로그인 완료: {bot.user} (봇이 정상 가동 중입니다)")

# --- 로블록스 시세 및 썸네일 함수 ---
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
        title=f"📊 아이템 시세 정보: {item_name}",
        description=f"🔗 **아이템 ID:** `{item_id}`",
        color=0x2b2d31
    )
    embed.add_field(name="✨ RAP (평균 거래가)", value=f"`{rap:,} R$`", inline=True)
    embed.add_field(name="💎 가치 (Value)", value=f"`{value:,} R$`", inline=True)
    embed.add_field(name="🔥 수요 (Demand)", value=f"`{demand}`", inline=True)
    embed.add_field(name="📈 트렌드", value=f"`{trend}`", inline=True)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed

# --- 모달(팝업 입력) 클래스들 ---
class ItemModal(discord.ui.Modal, title="로블록스 한정판 시세 조회"):
    item_id_input = discord.ui.TextInput(
        label="아이템 ID를 입력하세요",
        placeholder="예: 10159600649",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            item_id = int(self.item_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message("올바른 숫자(아이템 ID)를 입력해주세요.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        embed = await fetch_item_embed(item_id)
        
        if not embed:
            await interaction.followup.send("존재하지 않거나 한정판이 아닌 아이템 ID입니다.", ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

class RobuxCalcModal(discord.ui.Modal, title="로벅스 수수료 계산기"):
    robux_input = discord.ui.TextInput(
        label="계산할 로벅스 양을 입력하세요",
        placeholder="예: 1000",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.robux_input.value.strip())
        except ValueError:
            await interaction.response.send_message("올바른 숫자를 입력해주세요.", ephemeral=True)
            return

        received = int(amount * 0.7)
        embed = discord.Embed(
            title="🧮 로벅스 계산 결과",
            description=f"입력한 금액: **{amount:,} R$**",
            color=0x57F287
        )
        embed.add_field(name="💸 30% 수수료", value=f"`{amount - received:,} R$`", inline=False)
        embed.add_field(name="💰 실수령액 (70%)", value=f"`{received:,} R$`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RobloxVerifyModal(discord.ui.Modal, title="로블록스 계정 연동 인증"):
    roblox_name = discord.ui.TextInput(
        label="로블록스 닉네임을 입력하세요",
        placeholder="예: Zett",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.roblox_name.value.strip()
        role_name = "인증됨"  # 서버에 부여할 역할 이름 (서버 설정과 일치해야 함)
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        
        if not role:
            await interaction.response.send_message(f"서버에 '{role_name}' 역할이 없습니다. 관리자에게 문의하세요.", ephemeral=True)
            return

        try:
            # 닉네임 변경 기능 (선택사항, 권한이 없으면 제외될 수 있음)
            try:
                await interaction.user.edit(nick=nickname)
            except Exception:
                pass

            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ 성공적으로 인증되었습니다! (연동 닉네임: **{nickname}**)", ephemeral=True)
        except Exception:
            await interaction.response.send_message("인증 처리 중 오류가 발생했습니다. 봇의 권한(역할 순서 등)을 확인해주세요.", ephemeral=True)

# --- 버튼 패널 뷰 ---
class MainPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 시세 검색", style=discord.ButtonStyle.primary, custom_id="btn_search_price")
    async def btn_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ItemModal())

    @discord.ui.button(label="🧮 로벅스 계산", style=discord.ButtonStyle.success, custom_id="btn_calc_robux")
    async def btn_calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobuxCalcModal())

    @discord.ui.button(label="로블록스 인증하기", style=discord.ButtonStyle.success, custom_id="btn_roblox_verify")
    async def btn_verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobloxVerifyModal())

# --- 명령어 정의 ---
@bot.command(name="패널")
async def panel(ctx):
    embed = discord.Embed(
        title="🛡️ 로블록스 디스코드 연동 인증",
        description="서버를 이용하려면 아래의 **[로블록스 인증하기]** 버튼을 누르고 본인의 로블록스 닉네임을 입력해 주세요!",
        color=0x57F287
    )
    await ctx.send(embed=embed, view=MainPanelView())

@bot.command(name="청소", aliases=["삭제", "clear"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.channel.send(f"🧹 **{len(deleted)}개**의 메시지를 청소했습니다!")
    await msg.delete(delete_after=3)

@bot.command(name="시세")
async def item_price(ctx, item_id: int):
    embed = await fetch_item_embed(item_id)
    if not embed:
        await ctx.send("존재하지 않거나 한정판이 아닌 아이템 ID입니다.")
    else:
        await ctx.send(embed=embed)

token = os.getenv("TOKEN")
if not token:
    print("Error: TOKEN 환경 변수가 설정되지 않았습니다!")
else:
    bot.run(token)

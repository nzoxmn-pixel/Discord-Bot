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
                # 1단계: 사용자 ID 및 디스플레이 이름 조회
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("❌ 로블록스 API 서버와 통신 중 오류가 발생했습니다.", ephemeral=True)
                        return
                    
                    data = await resp.json()
                    
                    if not data.get("data") or len(data["data"]) == 0:
                        await interaction.followup.send(f"❌ **{username}**은(는) 존재하지 않는 로블록스 계정입니다. 닉네임을 다시 확인해 주세요.", ephemeral=True)
                        return

                    user_info = data["data"][0]
                    roblox_id = user_info["id"]
                    display_name = user_info["displayName"]
                    name = user_info["name"]

                # 2단계: 아바타 썸네일 이미지 가져오기
                avatar_url = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
                params = {"userIds": roblox_id, "size": "150x150", "format": "Png", "isCircular": "false"}
                
                async with session.get(avatar_url, params=params) as avatar_resp:
                    avatar_data = await avatar_resp.json()
                    headshot_url = ""
                    if avatar_data.get("data") and len(avatar_data["data"]) > 0:
                        headshot_url = avatar_data["data"][0]["imageUrl"]

                # 3단계: Verified 역할 부여
                role = discord.utils.get(interaction.guild.roles, name="Verified")
                if not role:
                    await interaction.followup.send("❌ 서버에 'Verified' 역할이 설정되어 있지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
                    return

                if role in interaction.user.roles:
                    await interaction.followup.send(f"✅ 이미 인증이 완료된 계정입니다! (연동된 계정: **{display_name}**)", ephemeral=True)
                    return

                await interaction.user.add_roles(role)
                await interaction.followup.send(f"🎉 인증 성공!\n로블록스 계정 **{display_name}**(ID: {roblox_id})와 연동되어 **Verified** 역할이 지급되었습니다.", ephemeral=True)

                # 4단계: #한국인-플레이어 채널에 프로필 임베드 전송 (이모지가 붙어있어도 이름 끝부분이나 포함 관계로 유연하게 찾도록 수정)
                target_channel = discord.utils.get(interaction.guild.text_channels, lambda c: "한국인-플레이어" in c.name)
                if target_channel:
                    embed = discord.Embed(
                        title="✨ 새로운 플레이어 인증 완료!",
                        description=f"디스코드 유저 {interaction.user.mention} 님의 로블록스 계정 연동 정보입니다.",
                        color=0x00ff00
                    )
                    embed.add_field(name="닉네임 (Username)", value=f"`{name}`", inline=True)
                    embed.add_field(name="표시 이름 (Display Name)", value=f"`{display_name}`", inline=True)
                    embed.add_field(name="로블록스 ID", value=f"`{roblox_id}`", inline=False)
                    
                    if headshot_url:
                        embed.set_thumbnail(url=headshot_url)
                    
                    embed.set_footer(text=f"디스코드 ID: {interaction.user.id}")
                    await target_channel.send(embed=embed)

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

# 3. 인증 패널 생성 명령어 (채널 이름에 이모지가 붙어있어도 '인증' 글자가 포함되면 통과되도록 수정)
@bot.command(name='인증패널')
@commands.has_permissions(administrator=True)
async def verify_panel(ctx):
    if "인증" not in ctx.channel.name:
        await ctx.send("❌ 이 명령어는 **인증** 관련 채널에서만 사용할 수 있습니다.", delete_after=5)
        return

    embed = discord.Embed(
        title="🛡️ 로블록스 디스코드 연동 인증",
        description="서버를 이용하려면 아래의 **[로블록스 인증하기]** 버튼을 누르고 본인의 로블록스 닉네임을 입력해 주세요!",
        color=0x00ff00
    )
    await ctx.send(embed=embed, view=VerifyView())

# 4. 관리자용 공지 임베드 전송 명령어 (!공지 [내용])
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

# 5. 일반 유저 채팅만 골라서 지우는 명령어 (!청소 [개수])
@bot.command(name='청소', aliases=['clear', '삭제'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 30):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: not m.author.bot)
    await ctx.send(f"🧹 일반 유저의 메시지 총 **{len(deleted)}개**를 청소했습니다!", delete_after=3)

# 6. 봇이 보낸 메시지만 골라서 지우는 명령어 (!봇청소 [개수])
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

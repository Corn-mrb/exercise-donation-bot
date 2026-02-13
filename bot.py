"""
Exercise Donation Bot - Main Bot
운동 기부 Discord 봇 메인 파일
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import logging
import config
import database
import lightning_blink as lightning

# 로깅 설정
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Slash commands synced")

bot = MyBot()

# ============================================
# UI Components
# ============================================

class ExerciseSelectView(View):
    """운동 종류 선택 뷰"""
    def __init__(self, action_type, user_id, username):
        super().__init__(timeout=60)
        self.action_type = action_type  # 'setting' or 'record'
        self.user_id = user_id
        self.username = username
        
        # 운동 종류 버튼 생성
        for ex_key, ex_type in config.EXERCISE_TYPES.items():
            button = Button(
                label=ex_type['name'],
                emoji=ex_type['emoji'],
                style=discord.ButtonStyle.primary,
                custom_id=f"{action_type}_{ex_key}"
            )
            button.callback = self.make_callback(ex_key)
            self.add_item(button)
    
    def make_callback(self, exercise_type):
        async def callback(interaction: discord.Interaction):
            if self.action_type == 'setting':
                # 기부 설정 - 금액 선택 뷰로 이동
                view = AmountSelectView(exercise_type, self.user_id, self.username)
                ex_type = config.EXERCISE_TYPES[exercise_type]
                embed = discord.Embed(
                    title=f"{ex_type['emoji']} {ex_type['name']} {ex_type['unit']}당 기부액 선택",
                    color=0x2E75B6
                )
                await interaction.response.edit_message(embed=embed, view=view)
            elif self.action_type == 'record':
                # 운동 기록 - 입력창 띄우기
                modal = ExerciseInputModal(exercise_type, self.user_id, self.username)
                await interaction.response.send_modal(modal)
        return callback

class AmountSelectView(View):
    """금액 선택 뷰 (1, 21, 100, 직접입력)"""
    def __init__(self, exercise_type, user_id, username):
        super().__init__(timeout=60)
        self.exercise_type = exercise_type
        self.user_id = user_id
        self.username = username
        
        # 빠른 선택 버튼
        for amount in config.QUICK_SELECT_AMOUNTS:
            button = Button(
                label=f"{amount} sats",
                style=discord.ButtonStyle.primary,
                custom_id=f"quick_{amount}"
            )
            button.callback = self.make_amount_callback(amount)
            self.add_item(button)
        
        # 직접 입력 버튼
        custom_button = Button(
            label="직접 입력",
            style=discord.ButtonStyle.secondary,
            custom_id="custom_input"
        )
        custom_button.callback = self.custom_input_callback
        self.add_item(custom_button)
    
    def make_amount_callback(self, amount):
        async def callback(interaction: discord.Interaction):
            await self.save_setting(interaction, amount)
        return callback
    
    async def custom_input_callback(self, interaction: discord.Interaction):
        modal = CustomAmountModal(self.exercise_type, self.user_id, self.username)
        await interaction.response.send_modal(modal)
    
    async def save_setting(self, interaction, amount):
        # 사용자 확인/생성
        user = await database.get_user(self.user_id)
        if not user:
            await database.create_user(self.user_id, self.username)
        
        # 설정 저장
        await database.update_donation_setting(self.user_id, self.exercise_type, amount)
        
        ex_type = config.EXERCISE_TYPES[self.exercise_type]
        await interaction.response.edit_message(
            content=f"✅ 설정 완료!\n{ex_type['emoji']} {ex_type['name']}: {amount:,} sats/{ex_type['unit']}",
            embed=None,
            view=None
        )

class CustomAmountModal(Modal, title="직접 입력"):
    """직접 금액 입력 모달"""
    amount_input = TextInput(
        label="금액 (sats)",
        placeholder="예: 2000",
        required=True,
        max_length=10
    )
    
    def __init__(self, exercise_type, user_id, username):
        super().__init__()
        self.exercise_type = exercise_type
        self.user_id = user_id
        self.username = username
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
            if amount <= 0:
                await interaction.response.send_message("❌ 0보다 큰 금액을 입력하세요.", ephemeral=True)
                return
            
            if amount > config.MAX_DONATION:
                await interaction.response.send_message(
                    f"❌ 최대 기부 금액은 {config.MAX_DONATION:,} sats입니다.", 
                    ephemeral=True
                )
                return
            
            # 사용자 확인/생성
            user = await database.get_user(self.user_id)
            if not user:
                await database.create_user(self.user_id, self.username)
            
            # 설정 저장
            await database.update_donation_setting(self.user_id, self.exercise_type, amount)
            
            ex_type = config.EXERCISE_TYPES[self.exercise_type]
            await interaction.response.send_message(
                f"✅ 설정 완료!\n{ex_type['emoji']} {ex_type['name']}: {amount:,} sats/{ex_type['unit']}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ 숫자만 입력하세요.", ephemeral=True)

class ExerciseInputModal(Modal, title="운동 기록"):
    """운동 거리/무게 입력 모달"""
    value_input = TextInput(
        label="거리 또는 무게",
        placeholder="예: 10 또는 10.5",
        required=True,
        max_length=10
    )
    
    memo_input = TextInput(
        label="메모 (선택사항)",
        placeholder="예: 아침 조깅",
        required=False,
        max_length=100,
        style=discord.TextStyle.short
    )
    
    def __init__(self, exercise_type, user_id, username):
        super().__init__()
        self.exercise_type = exercise_type
        self.user_id = user_id
        self.username = username
        
        # 라벨 변경
        ex_type = config.EXERCISE_TYPES[exercise_type]
        self.value_input.label = f"{ex_type['name']} ({ex_type['unit']})"
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = float(self.value_input.value)
            if value <= 0:
                await interaction.response.send_message("❌ 0보다 큰 값을 입력하세요.", ephemeral=True)
                return
            
            # Define reasonable limits based on exercise type
            max_limits = {
                'walking': 1000,  # km
                'cycling': 1000,  # km
                'running': 500,   # km
                'swimming': 100,  # km
                'weight': 500     # kg
            }
            max_value = max_limits.get(self.exercise_type, 1000)
            if value > max_value:
                unit = config.EXERCISE_TYPES[self.exercise_type]['unit']
                await interaction.response.send_message(
                    f"❌ 최대 입력 가능한 값은 {max_value:,} {unit}입니다.", 
                    ephemeral=True
                )
                return
            
            memo = self.memo_input.value or None
            
            # 사용자 확인
            user = await database.get_user(self.user_id)
            if not user:
                await interaction.response.send_message("❌ 먼저 /운동설정 명령으로 설정을 진행하세요.", ephemeral=True)
                return
            
            ex_type = config.EXERCISE_TYPES[self.exercise_type]
            rate = user[ex_type['db_field']]
            
            if rate == 0:
                await interaction.response.send_message(
                    f"❌ {ex_type['name']} 기부 설정이 필요합니다. /운동설정 명령을 사용하세요.",
                    ephemeral=True
                )
                return
            
            # 기부금 계산
            calculated_sats = int(value * rate)
            
            # 운동 기록
            await database.log_exercise(self.user_id, self.exercise_type, value, memo, calculated_sats)
            
            # 사용자 정보 다시 조회
            user = await database.get_user(self.user_id)
            
            # 응답
            embed = discord.Embed(title="운동 기록 완료! 🎉", color=0x00FF00)
            
            record_text = f"{ex_type['emoji']} {ex_type['name']}: {value} {ex_type['unit']}\n"
            record_text += f"💰 적립: {calculated_sats:,} sats\n"
            record_text += f"   ({value} {ex_type['unit']} × {rate:,} sats/{ex_type['unit']})"
            if memo:
                record_text += f"\n📝 메모: {memo}"
            
            embed.add_field(name="📊 기록", value=record_text, inline=False)
            embed.add_field(name="💼 누적 기부금", value=f"{user['accumulated_sats']:,} sats", inline=True)
            embed.add_field(name="🔥 연속 운동", value=f"{user['streak_days']}일", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ 숫자만 입력하세요.", ephemeral=True)

class LeaderboardView(View):
    """리더보드 카테고리 선택 뷰"""
    def __init__(self):
        super().__init__(timeout=120)
        
        categories = [
            ('🚶', '걷기', 'walking'),
            ('🚴', '자전거', 'cycling'),
            ('🏃', '달리기', 'running'),
            ('🏊', '수영', 'swimming'),
            ('💪', '웨이트', 'weight'),
            ('💰', '기부액', 'donation'),
            ('🎯', '기부횟수', 'donation_count')
        ]
        
        for emoji, name, category in categories:
            button = Button(
                label=name,
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                custom_id=f"lb_{category}"
            )
            button.callback = self.make_callback(category, name, emoji)
            self.add_item(button)
    
    def make_callback(self, category, name, emoji):
        async def callback(interaction: discord.Interaction):
            leaders = await database.get_leaderboard(category, 10)
            
            if not leaders:
                await interaction.response.send_message("❌ 순위 정보가 없습니다.", ephemeral=True)
                return
            
            title = f"{emoji} {name} 랭킹 TOP 10"
            embed = discord.Embed(title=title, color=0xFFD700)
            
            rank_text = ""
            medals = ['🥇', '🥈', '🥉']
            
            for idx, leader in enumerate(leaders):
                medal = medals[idx] if idx < 3 else f"{idx + 1}위"
                username = leader['username']
                total = leader['total']
                
                if category in ['walking', 'cycling', 'running', 'swimming', 'distance']:
                    rank_text += f"{medal}  @{username}    {total:.1f} km\n"
                elif category == 'weight':
                    rank_text += f"{medal}  @{username}    {total:.1f} kg\n"
                elif category == 'donation':
                    rank_text += f"{medal}  @{username}    {int(total):,} sats\n"
                elif category == 'donation_count':
                    rank_text += f"{medal}  @{username}    {int(total)}회\n"
            
            embed.description = rank_text
            
            if category == 'donation':
                total_users = await database.get_total_users()
                embed.set_footer(text=f"참여자: {total_users}명")
            
            # 버튼 유지
            view = LeaderboardView()
            await interaction.response.edit_message(embed=embed, view=view)
        
        return callback

# ============================================
# Slash Commands
# ============================================

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    await database.init_db()

@bot.tree.command(name="운동설정", description="운동별 기부 설정")
@commands.cooldown(1, 30, commands.BucketType.user)
async def donation_setting(interaction: discord.Interaction):
    """운동별 기부 설정"""
    view = ExerciseSelectView('setting', str(interaction.user.id), interaction.user.name)
    embed = discord.Embed(
        title="⚙️ 운동 종류를 선택하세요",
        color=0x2E75B6
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="내설정", description="현재 설정 확인")
async def my_settings(interaction: discord.Interaction):
    """현재 설정 확인"""
    user = await database.get_user(str(interaction.user.id))
    if not user:
        await interaction.response.send_message("❌ 먼저 /운동설정 명령으로 설정을 진행하세요.")
        return
    
    embed = discord.Embed(title="⚙️ 내 설정", color=0x2E75B6)
    
    settings_text = ""
    for ex_type_key, ex_type in config.EXERCISE_TYPES.items():
        rate = user[ex_type['db_field']]
        settings_text += f"{ex_type['emoji']} {ex_type['name']}: {rate:,} sats/{ex_type['unit']}\n"
    
    embed.add_field(name="💰 기부 설정", value=settings_text, inline=False)
    embed.add_field(name="📍 기부 지갑", value=f"`{config.DONATION_ADDRESS}`", inline=False)
    
    auto_status = "ON" if user['auto_donate_enabled'] else "OFF"
    embed.add_field(name="🤖 자동 기부", value=auto_status, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="운동", description="운동 기록")
@commands.cooldown(1, 60, commands.BucketType.user)
async def exercise(interaction: discord.Interaction):
    """운동 기록"""
    view = ExerciseSelectView('record', str(interaction.user.id), interaction.user.name)
    embed = discord.Embed(
        title="🏃 운동 종류를 선택하세요",
        color=0x2E75B6
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="내통계", description="개인 통계 조회")
async def my_stats(interaction: discord.Interaction):
    """개인 통계 조회"""
    user = await database.get_user(str(interaction.user.id))
    if not user:
        await interaction.response.send_message("❌ 기록된 통계가 없습니다.")
        return
    
    stats = await database.get_user_stats(str(interaction.user.id))
    embed = discord.Embed(title="🏃 운동 통계", color=0x2E75B6)
    
    exercise_text = ""
    exercise_text += f"🚶 걷기: {stats['walking']['distance']:.1f} km ({stats['walking']['sats']:,} sats)\n"
    exercise_text += f"🚴 자전거: {stats['cycling']['distance']:.1f} km ({stats['cycling']['sats']:,} sats)\n"
    exercise_text += f"🏃 달리기: {stats['running']['distance']:.1f} km ({stats['running']['sats']:,} sats)\n"
    exercise_text += f"🏊 수영: {stats['swimming']['distance']:.1f} km ({stats['swimming']['sats']:,} sats)\n"
    exercise_text += f"💪 웨이트: {stats['weight']['weight']:.1f} kg ({stats['weight']['sats']:,} sats)"
    embed.add_field(name="【운동별 기록】", value=exercise_text, inline=False)
    
    total_text = f"📏 총 거리: {stats['total_distance']:.1f} km\n"
    total_text += f"⚖️ 총 무게: {stats['total_weight']:.1f} kg\n"
    total_text += f"🔥 연속 운동: {stats['streak_days']}일"
    embed.add_field(name="【총 운동량】", value=total_text, inline=False)
    
    donation_text = f"💼 현재 누적: {stats['accumulated_sats']:,} sats\n"
    donation_text += f"✅ 총 기부 횟수: {stats['total_donation_count']}회\n"
    donation_text += f"💸 총 기부액: {stats['total_donated_sats']:,} sats"
    embed.add_field(name="【기부 정보】", value=donation_text, inline=False)
    
    donation_rank = await database.get_user_rank(str(interaction.user.id), 'donation')
    distance_rank = await database.get_user_rank(str(interaction.user.id), 'distance')
    weight_rank = await database.get_user_rank(str(interaction.user.id), 'weight')
    total_users = await database.get_total_users()
    
    rank_text = f"🏆 기부 순위: {donation_rank}위 / {total_users}명\n"
    rank_text += f"📊 거리 순위: {distance_rank}위 / {total_users}명\n"
    rank_text += f"💪 웨이트 순위: {weight_rank}위 / {total_users}명"
    embed.add_field(name="【순위】", value=rank_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="운동순위", description="리더보드 조회")
async def leaderboard(interaction: discord.Interaction):
    """리더보드 조회"""
    # 기본값: 전체 거리 순위
    leaders = await database.get_leaderboard('distance', 10)
    
    if not leaders:
        await interaction.response.send_message("❌ 순위 정보가 없습니다.")
        return
    
    embed = discord.Embed(title="📊 전체 거리 랭킹 TOP 10", color=0xFFD700)
    
    rank_text = ""
    medals = ['🥇', '🥈', '🥉']
    
    for idx, leader in enumerate(leaders):
        medal = medals[idx] if idx < 3 else f"{idx + 1}위"
        username = leader['username']
        total = leader['total']
        rank_text += f"{medal}  @{username}    {total:.1f} km\n"
    
    embed.description = rank_text
    
    total_users = await database.get_total_users()
    embed.set_footer(text=f"참여자: {total_users}명\n\n다른 순위를 보려면 아래 버튼을 선택하세요")
    
    view = LeaderboardView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="운동기부", description="기부 실행")
@commands.cooldown(1, 300, commands.BucketType.user)
async def donate(interaction: discord.Interaction):
    """기부 실행 (Phase 2: Lightning 결제)"""
    user = await database.get_user(str(interaction.user.id))
    if not user:
        await interaction.response.send_message("❌ 기록된 정보가 없습니다.")
        return
    
    if user['accumulated_sats'] == 0:
        await interaction.response.send_message("❌ 기부할 금액이 없습니다. 먼저 운동을 기록하세요!")
        return
    
    amount = user['accumulated_sats']
    
    # 최소 금액 확인
    if amount < config.MIN_DONATION:
        await interaction.response.send_message(
            f"❌ 최소 기부 금액은 {config.MIN_DONATION:,} sats입니다.\n"
            f"현재 누적: {amount:,} sats"
        )
        return
    
    # 즉시 응답 (Lightning Invoice 생성 중) - 본인만 보이게
    await interaction.response.send_message("⏳ Lightning Invoice 생성 중...", ephemeral=True)
    
    try:
        # Lightning Invoice 생성
        comment = f"운동 기부 - {interaction.user.name}"
        invoice, qr_buffer, payment_hash = await lightning.create_lightning_payment(amount, comment)
        
        # QR 코드 이미지
        qr_file = discord.File(qr_buffer, filename="invoice_qr.png")
        
        # 임베드 생성
        embed = discord.Embed(
            title="⚡ Lightning 기부",
            description=f"**{amount:,} sats** 기부를 진행합니다.",
            color=0xF7931A
        )
        
        embed.add_field(
            name="📍 받는 곳",
            value=f"`{config.DONATION_ADDRESS}`",
            inline=False
        )
        
        embed.add_field(
            name="💡 결제 방법",
            value="1️⃣ QR 코드 스캔 (Lightning 지갑 앱)\n2️⃣ 또는 아래 Invoice 복사",
            inline=False
        )
        
        # Invoice를 3줄로 나눠서 표시 (Discord 필드 제한)
        invoice_chunks = [invoice[i:i+1024] for i in range(0, len(invoice), 1024)]
        for idx, chunk in enumerate(invoice_chunks):
            field_name = "⚡ Lightning Invoice" if idx == 0 else f"⚡ Invoice (계속 {idx+1})"
            embed.add_field(name=field_name, value=f"`{chunk}`", inline=False)
        
        embed.set_image(url="attachment://invoice_qr.png")
        embed.set_footer(text="⏱️ 5분 안에 결제해주세요")
        
        # 메시지 업데이트 (본인만 보이게)
        await interaction.edit_original_response(
            content=None,
            embed=embed,
            attachments=[qr_file]
        )
        
        # 결제 대기 메시지 (본인만 보이게)
        await interaction.followup.send("⏳ 결제 확인 중... (최대 5분)", ephemeral=True)
        
        # 결제 확인 (5분 타임아웃) - invoice로 확인
        if invoice:
            payment_result = await lightning.verify_payment(invoice, timeout=300)
            
            if payment_result:
                # 결제 완료 - citadel@blink.sv로 자동 전송
                try:
                    # Lightning Address로 자동 전송
                    transfer_result = await lightning.send_to_lightning_address(
                        destination=config.DONATION_ADDRESS,
                        amount_sats=amount,
                        memo=f"운동 기부 - {interaction.user.name}"
                    )
                    
                    fee = transfer_result.get("fee", 0)
                    status = transfer_result.get("status")
                    
                    if status == "SUCCESS":
                        # DB 업데이트
                        async with database.aiosqlite.connect(config.DATABASE_PATH) as db:
                            await db.execute('''
                                UPDATE users 
                                SET accumulated_sats = accumulated_sats - ?,
                                    total_donated_sats = total_donated_sats + ?,
                                    total_donation_count = total_donation_count + 1
                                WHERE user_id = ?
                            ''', (amount, amount, str(interaction.user.id)))
                            
                            await db.execute('''
                                INSERT INTO donation_history 
                                (user_id, amount, lightning_address, donation_type, status, timestamp, lightning_invoice)
                                VALUES (?, ?, ?, 'manual', 'completed', ?, ?)
                            ''', (str(interaction.user.id), amount, config.DONATION_ADDRESS, 
                                  discord.utils.utcnow().isoformat(), invoice))
                            
                            await db.commit()
                        
                        # 완료 메시지 (공개)
                        fee_info = "**무료!** (Blink 내부 거래)" if fee == 0 else f"수수료: {fee} sats"
                        
                        success_embed = discord.Embed(
                            title="✅ 기부 완료!",
                            description=f"**{amount:,} sats** 기부가 완료되었습니다!",
                            color=0x00FF00
                        )
                        success_embed.add_field(name="받는 곳", value=config.DONATION_ADDRESS, inline=False)
                        success_embed.add_field(name="수수료", value=fee_info, inline=False)
                        success_embed.add_field(name="감사합니다! 🙏", value="당신의 운동과 기부가 세상을 바꿉니다!", inline=False)
                        
                        await interaction.followup.send(embed=success_embed)
                    else:
                        await interaction.followup.send(
                            f"❌ 전송 실패: {status}\n금액은 mrb@blink.sv에 보관되어 있습니다.",
                            ephemeral=True
                        )
                    
                except Exception as transfer_error:
                    # 전송 실패
                    await interaction.followup.send(
                        f"❌ 기부 전송 중 오류가 발생했습니다.\n"
                        f"오류: {str(transfer_error)}\n\n"
                        f"금액은 mrb@blink.sv에 보관되어 있습니다.\n"
                        f"수동으로 전송해주세요.",
                        ephemeral=True
                    )
            
            elif payment_result is False:
                # 결제 실패 (본인만)
                await interaction.followup.send("❌ 결제가 실패했습니다. 다시 시도해주세요.", ephemeral=True)
            
            else:
                # verify_url 없음 (결제 확인 불가) - 본인만
                await interaction.followup.send(
                    "⚠️ 자동 결제 확인이 불가능합니다.\n"
                    "결제 후 `/기부내역`으로 확인해주세요.",
                    ephemeral=True
                )
        else:
            # verify_url 없음 - 본인만
            await interaction.followup.send(
                "⚠️ 자동 결제 확인이 불가능합니다.\n"
                "결제 완료 후 관리자에게 문의하거나 `/기부내역`으로 확인해주세요.",
                ephemeral=True
            )
    
    except Exception as e:
        error_msg = str(e)
        await interaction.followup.send(
            f"❌ Lightning Invoice 생성 중 오류가 발생했습니다.\n"
            f"오류: {error_msg}\n\n"
            f"나중에 다시 시도해주세요.",
            ephemeral=True  # 에러도 본인만
        )
        print(f"Lightning payment error: {e}")


@bot.tree.command(name="기부내역", description="기부 내역 조회")
async def donation_history(interaction: discord.Interaction):
    """기부 내역 조회"""
    async with database.aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = database.aiosqlite.Row
        async with db.execute('''
            SELECT * FROM donation_history 
            WHERE user_id = ? AND status = 'completed'
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (str(interaction.user.id),)) as cursor:
            donations = await cursor.fetchall()
    
    if not donations:
        await interaction.response.send_message("❌ 기부 내역이 없습니다.")
        return
    
    embed = discord.Embed(title="📜 기부 내역", color=0x2E75B6)
    
    history_text = ""
    for idx, donation in enumerate(donations, 1):
        timestamp = donation['timestamp'][:10]  # YYYY-MM-DD
        amount = donation['amount']
        dtype = "자동" if donation['donation_type'].startswith('auto') else "수동"
        history_text += f"{idx}. {timestamp}  {amount:,} sats ({dtype})\n"
    
    embed.description = history_text
    
    user = await database.get_user(str(interaction.user.id))
    embed.set_footer(text=f"총 기부: {user['total_donated_sats']:,} sats ({user['total_donation_count']}회)")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="사용법", description="사용법 안내")
async def help_command(interaction: discord.Interaction):
    """사용법 안내"""
    embed = discord.Embed(
        title="🤖 운동 기부 봇 사용법",
        description="운동하고 기부하는 Discord 봇입니다!",
        color=0x2E75B6
    )
    
    embed.add_field(
        name="⚙️ 설정",
        value="`/운동설정` - 기부액 설정\n`/내설정` - 현재 설정 확인",
        inline=False
    )
    
    embed.add_field(
        name="🏃 운동 기록",
        value="`/운동` - 운동 기록하기",
        inline=False
    )
    
    embed.add_field(
        name="📊 통계",
        value="`/내통계` - 개인 통계\n`/운동순위` - 리더보드",
        inline=False
    )
    
    embed.add_field(
        name="💰 기부",
        value="`/운동기부` - 기부하기\n`/기부내역` - 기부 이력",
        inline=False
    )
    
    embed.set_footer(text="운동 종류: 걷기, 자전거, 달리기, 수영, 웨이트")
    
    await interaction.response.send_message(embed=embed)

# ============================================
# Error Handlers
# ============================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handle app command errors"""
    if isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(int(error.retry_after), 60)
        if minutes > 0:
            time_msg = f"{minutes}분 {seconds}초"
        else:
            time_msg = f"{seconds}초"
        
        await interaction.response.send_message(
            f"⏱️ 이 명령어는 너무 자주 사용할 수 없습니다.\n"
            f"**{time_msg}** 후에 다시 시도하세요.",
            ephemeral=True
        )
    else:
        # Re-raise other errors
        raise error

if __name__ == '__main__':
    try:
        # 환경변수 검증
        config.validate_config()
        
        # 설정 출력 (디버깅용)
        if config.LOG_LEVEL == 'DEBUG':
            config.print_config()
        
        logger.info("🚀 Starting Exercise Donation Bot...")
        bot.run(config.DISCORD_TOKEN)
        
    except ValueError as e:
        logger.error(f"❌ Configuration Error: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")

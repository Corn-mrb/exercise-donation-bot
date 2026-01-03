"""
Exercise Donation Bot - Configuration
환경변수 및 설정 관리
"""
import os
import logging
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ===========================================
# Discord 설정
# ===========================================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# ===========================================
# Blink API 설정
# ===========================================
BLINK_API_KEY = os.getenv('BLINK_API_KEY')
BLINK_API_ENDPOINT = os.getenv('BLINK_API_ENDPOINT', 'https://api.blink.sv/graphql')

# ===========================================
# Database 설정
# ===========================================
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/exercise_bot.db')

# ===========================================
# Donation 설정
# ===========================================
DONATION_ADDRESS = os.getenv('DONATION_ADDRESS', 'citadel@blink.sv')

# ===========================================
# Environment 설정
# ===========================================
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
IS_PRODUCTION = ENVIRONMENT == 'production'

# ===========================================
# Donation Limits
# ===========================================
MIN_DONATION = int(os.getenv('MIN_DONATION', '1'))  # 최소 1 sats
MAX_DONATION = int(os.getenv('MAX_DONATION', '1000000'))  # 최대 1M sats
MIN_AUTO_AMOUNT = int(os.getenv('MIN_AUTO_AMOUNT', '1'))  # 자동 기부 최소 목표 금액

# ===========================================
# Quick Select Amounts
# ===========================================
QUICK_SELECT_AMOUNTS = [1, 21, 100]

# ===========================================
# Retry 설정
# ===========================================
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '1'))  # seconds

# ===========================================
# Payment 설정
# ===========================================
PAYMENT_CHECK_INTERVAL = int(os.getenv('PAYMENT_CHECK_INTERVAL', '5'))  # seconds
PAYMENT_TIMEOUT = int(os.getenv('PAYMENT_TIMEOUT', '300'))  # seconds (5분)

# ===========================================
# Exercise Types
# ===========================================
EXERCISE_TYPES = {
    'walking': {
        'emoji': '🚶',
        'name': '걷기',
        'unit': 'km',
        'db_field': 'walking_sats_per_km',
        'total_field': 'total_walking_km'
    },
    'cycling': {
        'emoji': '🚴',
        'name': '자전거',
        'unit': 'km',
        'db_field': 'cycling_sats_per_km',
        'total_field': 'total_cycling_km'
    },
    'running': {
        'emoji': '🏃',
        'name': '달리기',
        'unit': 'km',
        'db_field': 'running_sats_per_km',
        'total_field': 'total_running_km'
    },
    'swimming': {
        'emoji': '🏊',
        'name': '수영',
        'unit': 'km',
        'db_field': 'swimming_sats_per_km',
        'total_field': 'total_swimming_km'
    },
    'weight': {
        'emoji': '🏋️',
        'name': '웨이트',
        'unit': 'kg',
        'db_field': 'weight_sats_per_kg',
        'total_field': 'total_weight_kg'
    }
}

# ===========================================
# Validation
# ===========================================
def validate_config():
    """필수 환경변수 검증"""
    errors = []
    
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN is required")
    
    if not BLINK_API_KEY:
        errors.append("BLINK_API_KEY is required")
    
    if not DONATION_ADDRESS:
        errors.append("DONATION_ADDRESS is required")
    
    if errors:
        for error in errors:
            logger.error(f"Config Error: {error}")
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    logger.info("✅ Configuration validated successfully")
    return True

def print_config():
    """설정 정보 출력 (디버깅용, 민감정보 마스킹)"""
    logger.info("=== Configuration ===")
    logger.info(f"ENVIRONMENT: {ENVIRONMENT}")
    logger.info(f"DATABASE_PATH: {DATABASE_PATH}")
    logger.info(f"DONATION_ADDRESS: {DONATION_ADDRESS}")
    logger.info(f"BLINK_API_ENDPOINT: {BLINK_API_ENDPOINT}")
    logger.info(f"DISCORD_TOKEN: {'*' * 10}...{DISCORD_TOKEN[-4:] if DISCORD_TOKEN else 'NOT SET'}")
    logger.info(f"BLINK_API_KEY: {'*' * 10}...{BLINK_API_KEY[-4:] if BLINK_API_KEY else 'NOT SET'}")
    logger.info("====================")

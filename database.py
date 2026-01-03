"""
Exercise Donation Bot - Database Manager
데이터베이스 연결 및 쿼리 관리
"""
import aiosqlite
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 연결 관리 (싱글톤 패턴)"""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_connection(self) -> aiosqlite.Connection:
        """DB 연결 가져오기 (재사용)"""
        if self._connection is None:
            db_dir = os.path.dirname(config.DATABASE_PATH)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                logger.info(f"Created database directory: {db_dir}")
            
            self._connection = await aiosqlite.connect(config.DATABASE_PATH)
            self._connection.row_factory = aiosqlite.Row
            logger.info(f"Database connected: {config.DATABASE_PATH}")
        
        return self._connection
    
    async def close(self):
        """DB 연결 종료"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")


# 전역 DB 매니저
db_manager = DatabaseManager()


async def init_db():
    """데이터베이스 초기화"""
    try:
        db = await db_manager.get_connection()
        
        # users 테이블
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                walking_sats_per_km INTEGER DEFAULT 0,
                cycling_sats_per_km INTEGER DEFAULT 0,
                running_sats_per_km INTEGER DEFAULT 0,
                weight_sats_per_kg INTEGER DEFAULT 0,
                swimming_sats_per_km INTEGER DEFAULT 0,
                total_walking_km REAL DEFAULT 0,
                total_cycling_km REAL DEFAULT 0,
                total_running_km REAL DEFAULT 0,
                total_weight_kg REAL DEFAULT 0,
                total_swimming_km REAL DEFAULT 0,
                accumulated_sats INTEGER DEFAULT 0,
                total_donated_sats INTEGER DEFAULT 0,
                total_donation_count INTEGER DEFAULT 0,
                created_at TEXT,
                last_exercise_date TEXT,
                streak_days INTEGER DEFAULT 0,
                auto_donate_enabled INTEGER DEFAULT 0,
                auto_donate_type TEXT,
                auto_donate_target_amount INTEGER,
                auto_donate_schedule_type TEXT,
                auto_donate_schedule_day INTEGER,
                next_auto_donate_date TEXT
            )
        ''')
        
        # exercise_logs 테이블
        await db.execute('''
            CREATE TABLE IF NOT EXISTS exercise_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                exercise_type TEXT,
                value REAL,
                unit TEXT,
                calculated_sats INTEGER,
                memo TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # donation_history 테이블
        await db.execute('''
            CREATE TABLE IF NOT EXISTS donation_history (
                donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount INTEGER,
                lightning_address TEXT,
                lightning_invoice TEXT,
                payment_hash TEXT,
                donation_type TEXT,
                status TEXT,
                error_message TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        await db.commit()
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def get_user(user_id: str) -> Optional[aiosqlite.Row]:
    """사용자 정보 조회"""
    try:
        db = await db_manager.get_connection()
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None


async def create_user(user_id: str, username: str) -> bool:
    """새 사용자 생성"""
    try:
        db = await db_manager.get_connection()
        await db.execute('''
            INSERT INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
        ''', (user_id, username, datetime.now().isoformat()))
        await db.commit()
        logger.info(f"New user created: {username} ({user_id})")
        return True
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
        return False


async def update_donation_setting(user_id: str, exercise_type: str, sats_amount: int) -> bool:
    """기부 설정 업데이트"""
    try:
        field = config.EXERCISE_TYPES[exercise_type]['db_field']
        db = await db_manager.get_connection()
        await db.execute(f'''
            UPDATE users SET {field} = ? WHERE user_id = ?
        ''', (sats_amount, user_id))
        await db.commit()
        logger.debug(f"Updated {exercise_type} setting for {user_id}: {sats_amount} sats")
        return True
    except Exception as e:
        logger.error(f"Error updating donation setting: {e}")
        return False


async def log_exercise(user_id: str, exercise_type: str, value: float, memo: str, calculated_sats: int) -> bool:
    """운동 기록 저장"""
    try:
        unit = config.EXERCISE_TYPES[exercise_type]['unit']
        total_field = config.EXERCISE_TYPES[exercise_type]['total_field']
        
        db = await db_manager.get_connection()
        
        # 운동 로그 저장
        await db.execute('''
            INSERT INTO exercise_logs (user_id, exercise_type, value, unit, calculated_sats, memo, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, exercise_type, value, unit, calculated_sats, memo, datetime.now().isoformat()))
        
        # 사용자 총계 업데이트
        await db.execute(f'''
            UPDATE users 
            SET {total_field} = {total_field} + ?,
                accumulated_sats = accumulated_sats + ?,
                last_exercise_date = ?
            WHERE user_id = ?
        ''', (value, calculated_sats, datetime.now().isoformat(), user_id))
        
        await db.commit()
        logger.info(f"Exercise logged: {user_id} - {exercise_type} {value}{unit} = {calculated_sats} sats")
        return True
        
    except Exception as e:
        logger.error(f"Error logging exercise: {e}")
        return False


async def get_user_stats(user_id: str) -> Optional[Dict[str, Any]]:
    """사용자 통계 조회"""
    try:
        db = await db_manager.get_connection()
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            user = await cursor.fetchone()
            
        if not user:
            return None
            
        return {
            'walking': {
                'distance': user['total_walking_km'],
                'sats': user['total_walking_km'] * user['walking_sats_per_km']
            },
            'cycling': {
                'distance': user['total_cycling_km'],
                'sats': user['total_cycling_km'] * user['cycling_sats_per_km']
            },
            'running': {
                'distance': user['total_running_km'],
                'sats': user['total_running_km'] * user['running_sats_per_km']
            },
            'weight': {
                'weight': user['total_weight_kg'],
                'sats': user['total_weight_kg'] * user['weight_sats_per_kg']
            },
            'swimming': {
                'distance': user['total_swimming_km'],
                'sats': user['total_swimming_km'] * user['swimming_sats_per_km']
            },
            'total_distance': user['total_walking_km'] + user['total_cycling_km'] + user['total_running_km'] + user['total_swimming_km'],
            'total_weight': user['total_weight_kg'],
            'accumulated_sats': user['accumulated_sats'],
            'total_donated_sats': user['total_donated_sats'],
            'total_donation_count': user['total_donation_count'],
            'streak_days': user['streak_days']
        }
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return None


async def get_leaderboard(category: str = 'distance', limit: int = 10) -> List[aiosqlite.Row]:
    """리더보드 조회"""
    try:
        db = await db_manager.get_connection()
        
        if category == 'distance':
            query = '''
                SELECT user_id, username, 
                       (total_walking_km + total_cycling_km + total_running_km + total_swimming_km) as total
                FROM users
                WHERE (total_walking_km + total_cycling_km + total_running_km + total_swimming_km) > 0
                ORDER BY total DESC
                LIMIT ?
            '''
        elif category == 'donation':
            query = '''
                SELECT user_id, username, total_donated_sats as total
                FROM users
                WHERE total_donated_sats > 0
                ORDER BY total DESC
                LIMIT ?
            '''
        elif category == 'donation_count':
            query = '''
                SELECT user_id, username, total_donation_count as total
                FROM users
                WHERE total_donation_count > 0
                ORDER BY total DESC
                LIMIT ?
            '''
        elif category in ['walking', 'cycling', 'running', 'swimming']:
            field = f'total_{category}_km'
            query = f'''
                SELECT user_id, username, {field} as total
                FROM users
                WHERE {field} > 0
                ORDER BY total DESC
                LIMIT ?
            '''
        elif category == 'weight':
            query = '''
                SELECT user_id, username, total_weight_kg as total
                FROM users
                WHERE total_weight_kg > 0
                ORDER BY total DESC
                LIMIT ?
            '''
        else:
            return []
        
        async with db.execute(query, (limit,)) as cursor:
            return await cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return []


async def get_user_rank(user_id: str, category: str = 'distance') -> Optional[int]:
    """사용자 순위 조회"""
    try:
        db = await db_manager.get_connection()
        
        if category == 'distance':
            query = '''
                SELECT COUNT(*) + 1 as rank
                FROM users
                WHERE (total_walking_km + total_cycling_km + total_running_km + total_swimming_km) > 
                      (SELECT total_walking_km + total_cycling_km + total_running_km + total_swimming_km
                       FROM users WHERE user_id = ?)
            '''
        elif category == 'donation':
            query = '''
                SELECT COUNT(*) + 1 as rank
                FROM users
                WHERE total_donated_sats > (SELECT total_donated_sats FROM users WHERE user_id = ?)
            '''
        elif category == 'weight':
            query = '''
                SELECT COUNT(*) + 1 as rank
                FROM users
                WHERE total_weight_kg > (SELECT total_weight_kg FROM users WHERE user_id = ?)
            '''
        else:
            return None
        
        async with db.execute(query, (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None
            
    except Exception as e:
        logger.error(f"Error getting user rank: {e}")
        return None


async def get_total_users() -> int:
    """전체 사용자 수"""
    try:
        db = await db_manager.get_connection()
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting total users: {e}")
        return 0


async def update_donation_complete(user_id: str, amount: int, invoice: str, donation_address: str) -> bool:
    """기부 완료 후 DB 업데이트"""
    try:
        db = await db_manager.get_connection()
        
        # 사용자 통계 업데이트
        await db.execute('''
            UPDATE users 
            SET accumulated_sats = accumulated_sats - ?,
                total_donated_sats = total_donated_sats + ?,
                total_donation_count = total_donation_count + 1
            WHERE user_id = ?
        ''', (amount, amount, user_id))
        
        # 기부 히스토리 추가
        await db.execute('''
            INSERT INTO donation_history 
            (user_id, amount, lightning_address, donation_type, status, timestamp, lightning_invoice)
            VALUES (?, ?, ?, 'manual', 'completed', ?, ?)
        ''', (user_id, amount, donation_address, datetime.now().isoformat(), invoice))
        
        await db.commit()
        logger.info(f"Donation completed: {user_id} - {amount} sats to {donation_address}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating donation complete: {e}")
        return False

import json
import secrets

from sqlalchemy import select

from .config import Settings
from .database import make_database
from .models import Config, OfficialEvent, Room, RoomMember, School, User
from .services.security import hash_password
from .time import utcnow


def seed(db, settings: Settings, echo=print):
    now = utcnow()

    defaults = {
        'site_name': '研时',
        'exam_date': '2027-12-25',
        'exam_year': 2028,
        'registration_open': True,  # 自助注册仍需有效邀请码
    }
    for key, value in defaults.items():
        if db.get(Config, key) is None:
            db.add(Config(config_key=key, config_value=json.dumps(value, ensure_ascii=False),
                          updated_at=now))

    if db.scalar(select(OfficialEvent.id).limit(1)) is None:
        events = [
            ('2028 考研初试', '2027-12-25', '2028', 0),
            ('2028 考研网上报名', '2027-10-08', '2028', 1),
            ('2028 考研成绩公布', '2028-02-20', '2028', 2),
            ('2028 考研复试', '2028-03-20', '2028', 3),
        ]
        for title, date, year, order in events:
            db.add(OfficialEvent(title=title, event_date=date, year=year, sort_order=order))

    # 内置七校（基础信息；校徽/风景图用前端内置素材，复试线等半自动信息留空）
    builtin_schools = [
        ('tsinghua', '清华大学', '清华', 1),
        ('pku', '北京大学', '北大', 2),
        ('nju', '南京大学', '南大', 3),
        ('fudan', '复旦大学', '复旦', 4),
        ('sjtu', '上海交通大学', '上交', 5),
        ('ustc', '中国科学技术大学', '中科大', 6),
        ('zju', '浙江大学', '浙大', 7),
    ]
    for key, name, short, order in builtin_schools:
        if not db.scalar(select(School.id).where(School.key == key)):
            db.add(School(key=key, name=name, short=short, is_builtin=True, sort_order=order))

    admin = db.scalar(select(User).where(User.email == settings.admin_email))
    if not admin:
        generated = not settings.admin_password
        password = settings.admin_password or secrets.token_urlsafe(12)
        admin = User(
            email=settings.admin_email, password_hash=hash_password(password),
            nickname='管理员', role='admin', daily_goal_min=300,
            exam_year=2028, exam_date='2027-12-25',
        )
        db.add(admin)
        db.commit()
        echo('========================================================')
        echo(f'初始管理员已创建：{admin.email}')
        echo(f'登录密码：{password}')
        if generated:
            echo('（密码为随机生成，仅显示一次，请立即登录并修改）')
        echo('========================================================')

    # 固定一个四人自习室，管理员为房主
    room = db.scalar(select(Room).order_by(Room.id).limit(1))
    if not room:
        room = Room(
            code='YANSHI', name='研时 · 四人自习室',
            intro='大雪深埋，与三个同道并肩；只同步状态，不设摄像头。',
            owner_id=admin.id, capacity=4,
        )
        db.add(room)
        db.flush()
    if not db.scalar(select(RoomMember.id).where(
            RoomMember.room_id == room.id, RoomMember.user_id == admin.id)):
        db.add(RoomMember(room_id=room.id, user_id=admin.id, role='owner'))

    db.commit()


if __name__ == '__main__':
    settings = Settings()
    _, sessions = make_database(settings.database_url)
    with sessions() as db:
        seed(db, settings)
    print('系统配置 / 官方节点 / 管理员已就绪；未生成任何虚构学习数据。')

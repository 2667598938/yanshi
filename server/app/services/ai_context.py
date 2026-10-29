"""Owner-only, bounded summaries. Today's work survives overdue backlogs."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from ..models import LearningRecord, RoomPresence
from ..time import utcnow
from .presence import primary, active_devices
from .session_records import display_record

CN = timezone(timedelta(hours=8))
DEFAULT_SUBJECTS = {'math': '数学', 'cs408': '408', 'english': '英语', 'politics': '政治',
                    'algo': '算法刷题', 'project': '项目开发', 'recite': '八股背诵', 'other': '其他'}


def bounded_int(value, upper):
    try:
        return max(0, min(upper, int(value or 0)))
    except (TypeError, ValueError, OverflowError):
        return 0


def subject_catalog(db, user_id):
    rows = db.scalars(select(LearningRecord).where(LearningRecord.user_id == user_id,
        LearningRecord.deleted == 0, func.json_extract(LearningRecord.body, '$.type') == 'subject')).all()
    subjects = [json.loads(row.body) for row in rows]
    # Legacy unsynced clients use built-ins; a synced catalog is authoritative.
    if not subjects:
        return [{'id': key, 'name': name} for key, name in DEFAULT_SUBJECTS.items()]
    result = [{'id': str(s['id']), 'name': str(s.get('name', ''))[:40]}
              for s in subjects if not s.get('archived')]
    if not any(s['id'] == 'other' for s in result):
        result.append({'id': 'other', 'name': '其他'})
    return sorted(result, key=lambda s: s['id'])


def account_context(db, user_id, budget=6000, scene='review'):
    now = utcnow()
    today = (now + timedelta(hours=8)).date()
    day_key = today.isoformat()
    heat, subject_seconds = {}, {}
    pending, completed, study, mistakes, nodes = [], [], [], [], []
    recent_done = overdue = today_count = excluded = today_completed = today_pending = 0
    rows = db.scalars(select(LearningRecord).where(LearningRecord.user_id == user_id,
        LearningRecord.deleted == 0, func.json_extract(LearningRecord.body, '$.type').in_(
            ['task', 'session', 'mistake', 'timeNode']))).all()
    for row in rows:
        v = display_record(db, user_id, json.loads(row.body))
        kind = v.get('type')
        if kind == 'session':
            if v.get('conflict_flag') or v.get('validation_issue'):
                excluded += 1
                continue
            day, sec = str(v.get('date', '')), bounded_int(v.get('actualSec'), 10800)
            if (today - timedelta(days=29)).isoformat() <= day <= day_key:
                heat[day] = heat.get(day, 0) + sec
            if day == day_key:
                today_count += int(v.get('status') == 'done')
                sid = str(v.get('subjectId', 'other'))
                subject_seconds[sid] = subject_seconds.get(sid, 0) + sec
                study.append((bounded_int(v.get('startedAt'), 253402300799000), {'subject': sid, 'seconds': sec,
                    'content': str(v.get('learningContent', ''))[:60], 'note': str(v.get('note', ''))[:60]}))
        elif kind == 'task':
            item = {'title': str(v.get('title', ''))[:50], 'due': str(v.get('dueDate', ''))[:10],
                    'min': bounded_int(v.get('estimatedMin'), 1440), 'criteria': str(v.get('acceptCriteria', ''))[:50]}
            if v.get('done'):
                stamp = bounded_int(v.get('doneAt'), 253402300799000)
                try:
                    done_day = datetime.fromtimestamp(stamp / 1000, CN).date() if stamp else None
                except (ValueError, OverflowError, OSError):
                    done_day = None
                item['completed_on'] = done_day.isoformat() if done_day else ''
                today_completed += int(done_day == today)
                recent_done += int(done_day is not None and today - timedelta(days=6) <= done_day <= today)
                completed.append((stamp, item))
            else:
                pending.append(item)
                today_pending += int(item['due'] == day_key)
                overdue += int(bool(item['due']) and item['due'] < day_key)
        elif kind == 'mistake' and not v.get('mastered'):
            mistakes.append({'chapter': str(v.get('chapter', ''))[:30], 'reason': str(v.get('reason', ''))[:30],
                'question': str(v.get('content', ''))[:80], 'subject': str(v.get('subjectId', 'other'))})
        elif kind == 'timeNode':
            value = v.get('value') or v
            nodes.append({'name': str(value.get('node_name', ''))[:40], 'date': str(value.get('target_date', ''))[:10]})
    # Today, upcoming, overdue, undated; old backlog cannot evict today's category.
    pending.sort(key=lambda t: (0 if t['due'] == day_key else 1 if t['due'] > day_key else 2 if t['due'] else 3,
                                 t['due'] or '9999', t['title']))
    completed.sort(key=lambda pair: pair[0], reverse=True)
    device = primary(active_devices(db, user_id))
    status = device.status if device else 'offline'
    if not device:
        legacy = db.scalar(select(RoomPresence).where(RoomPresence.user_id == user_id)
            .order_by(RoomPresence.last_heartbeat_at.desc()).limit(1))
        if legacy and legacy.status != 'offline' and (now - legacy.last_heartbeat_at).total_seconds() <= 90:
            status = legacy.status
    result = {'source': '本人已同步摘要；只读，不含组员/密钥', 'date': day_key,
        'tasks': {'pending': [], 'completed': []},
        'task_counts': {'pending': len(pending), 'completed': len(completed), 'overdue_pending': overdue,
                        'today_pending': today_pending, 'today_completed': today_completed},
        'recent_7_days': {'completed': recent_done}, 'self_status': status,
        'today_focus_seconds': heat.get(day_key, 0), 'today_pomodoros': today_count,
        'heatmap': {'days': 30, 'active_days': sum(s > 0 for s in heat.values()), 'seconds': sum(heat.values())},
        'task_list_truncated': False}
    if excluded:
        result['session_issues'] = {'excluded': excluded, 'note': '冲突/无效计时未计入，不能据此认定没有学习'}
    cap = max(600, min(12000, budget)) - 160
    def fits():
        return len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= cap
    lists = [('pending', pending), ('completed', [item for _, item in completed])]
    # Reserve one from each category before optional rich facts or more tasks.
    for key, items in lists:
        if items:
            item = dict(items[0])
            result['tasks'][key].append(item)
            if not fits():
                item.pop('criteria', None)
                item['title'] = item['title'][:20]
            if not fits():
                result['tasks'][key].pop()
    optional = {'subject_seconds_today': subject_seconds, 'study_today': [item for _,item in sorted(study,key=lambda pair:pair[0],reverse=True)[:4]],
                'mistakes_to_review': mistakes[:3], 'time_nodes': sorted(nodes, key=lambda n: n['date'])[:4],
                'daily_seconds_recent_7': [[(today-timedelta(days=i)).isoformat(), heat.get((today-timedelta(days=i)).isoformat(), 0)] for i in range(6, -1, -1)]}
    if scene == 'plan':
        optional = {key: optional[key] for key in ['time_nodes', 'mistakes_to_review', 'subject_seconds_today', 'study_today', 'daily_seconds_recent_7']}
    if device and status == 'focusing':
        detail = json.loads(device.detail or '{}')
        anchor = detail.get('focus_started_at')
        if anchor:
            optional['current_focus_seconds'] = bounded_int((now.replace(tzinfo=timezone.utc).timestamp()*1000-anchor)//1000, 10800)
    for key, value in optional.items():
        if value:
            result[key] = value
            if not fits():
                del result[key]
    for i in range(1, 20):
        for key, items in lists:
            if i < len(items) and (key != 'completed' or i < 6):
                result['tasks'][key].append(items[i])
                if not fits():
                    result['tasks'][key].pop()
    result['task_list_truncated'] = any(len(result['tasks'][key]) < len(items) for key, items in lists)
    return result


TASK_INSTRUCTION = """当用户要求计划、安排任务或把回复转换为任务时，直接生成可执行、可导入的建议。优先3至8项；较长计划分步生成，给结构化内容预留输出空间。不要只说等待确认。
在回复末尾提供yanshi_tasks代码块，内容为JSON对象：
{"tasks":[{"title":"任务名称","due_date":"YYYY-MM-DD","estimated_min":30,"subject_id":"other","accept_criteria":"完成标准"}]}。
subject_id必须使用系统提供的本人科目目录中的id，不可填中文名称；无法匹配用other。日期、可用时间等信息不够时先追问，不编造用户条件。
最多30条；必须由用户预览、修正并手动确认导入。你不能自动新增或修改数据。普通答疑无需此块。
账号摘要可能省略明细，今天时长仅含已结算记录；当前一轮另列。不能据省略/未同步数据推断用户没有学习。"""

"""AI 助教服务：火山方舟豆包（服务端持有 Key，非流式，会话历史落库）。"""
import json

import httpx

from ..errors import ApiError

BASE_PERSONA = """你是「研时」为考研学生打造的 AI 助教，服务于一个 4 人互助学习小组。
职责：
1. 考研答疑：覆盖政治、英语（一/二）、数学（一/二）、408 计算机学科专业基础及各专业课，严格依据考研大纲，不超纲、不编造；讲题先定位考点，再讲思路与易错点，必要时给一道同类变式。
2. 备考工具：作文批改、学习计划生成、极限/知识点推导、每日与每周复盘。
3. 简短情绪支持：疲惫时给一句实在的鼓励，不灌空洞鸡汤。
规则：
- 分点作答、精炼、直接可用；不确定的内容明确说明，不猜测。
- 计划与任务要量化到科目、章节、题量、页码，不写"多看书"这类空话。
- 强调"记录时长≠学会"，关注任务完成与错题消化，而不是只堆学习时长。
- 一律用中文回答。"""

SCENES = {
    'general': '当前为通用问答，可闲聊但不偏离考研学习主题。',
    'kaoyan': '当前为考研专项答疑（408、数学、英语、政治、专业课）。按"考点定位→正确思路（解释为什么）→易错点→一道同类变式"组织，优先讲拿分套路。',
    'essay': '当前为英语作文批改。先确认英语一/二与题型，再给参考分与档次、结构与切题问题、逐句语法搭配修改、升级表达，最后给完整范文；评分仅为练习参考。',
    'plan': '当前为学习计划生成。结合考试日期与用户可用时间，输出分阶段、可执行、含休息与复盘的计划，任务必须量化。',
    'review': '当前为学习复盘。基于用户附带的真实记录（时长/任务/错题）分析时间分配、薄弱科目、中断原因，给明日可量化任务；数据不足时明确说明，不编造数据。',
}

HISTORY_TURNS = 10     # 最多带 10 轮历史


def build_messages(scene: str, history: list, content: str, context: dict | None):
    system = BASE_PERSONA + '\n' + SCENES.get(scene, SCENES['general'])
    if context:
        system += '\n用户附带的本地数据（仅供本次分析，不要原样罗列）：' + json.dumps(
            context, ensure_ascii=False)[:8000]
    messages = [{'role': 'system', 'content': system}]
    messages.extend(history)
    messages.append({'role': 'user', 'content': content})
    return messages


async def call_ark(settings, messages):
    if not settings.ai_enabled:
        raise ApiError(503, 50301, 'AI 尚未配置（服务端未填写火山方舟 Key）')
    url = settings.volc_base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': settings.volc_model, 'messages': messages,
        'temperature': 0.3, 'max_tokens': settings.ai_max_tokens, 'stream': False,
    }
    headers = {'Authorization': 'Bearer ' + settings.volc_api_key,
               'Content-Type': 'application/json'}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15),
                                     trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError:
        raise ApiError(502, 50201, 'AI 服务连接失败，请稍后重试') from None
    if resp.status_code != 200:
        hint = {401: 'AI Key 无效或已失效', 403: 'AI 模型权限不足',
                404: 'AI 模型不可用', 429: 'AI 调用频率超限或额度不足'}.get(resp.status_code)
        raise ApiError(502, 50201, hint or 'AI 服务暂时不可用，请稍后重试')
    try:
        data = resp.json()
        return data['choices'][0]['message']['content'].strip()
    except Exception:
        raise ApiError(502, 50201, 'AI 返回内容解析失败') from None

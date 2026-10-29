"""AI 助教服务：VIP 用户自填 Key（OpenAI 兼容）为唯一主路径。

`call_ark` / `stream_ark` 仅为历史/测试占位，生产聊天路由不会调用，也不会回退平台 Key。
"""
import json
import time

import httpx

from ..errors import ApiError

PROVIDERS = {
    'deepseek': {'label': 'DeepSeek', 'base_url': 'https://api.deepseek.com/v1',
                 'default_model': 'deepseek-chat'},
    'moonshot': {'label': 'Kimi', 'base_url': 'https://api.moonshot.cn/v1',
                 'default_model': 'moonshot-v1-8k'},
    'zhipu': {'label': '智谱 GLM', 'base_url': 'https://open.bigmodel.cn/api/paas/v4',
              'default_model': 'glm-4-flash'},
    'siliconflow': {'label': '硅基流动', 'base_url': 'https://api.siliconflow.cn/v1',
                    'default_model': 'Qwen/Qwen2.5-7B-Instruct'},
    'openai': {'label': 'OpenAI', 'base_url': 'https://api.openai.com/v1',
               'default_model': 'gpt-4o-mini'},
    'custom': {'label': '自定义', 'base_url': '', 'default_model': ''},
}


def check_finish_reason(reason):
    if reason == 'length':
        raise ApiError(502, 50202, '回答达到模型输出上限，内容未完整生成。请缩短问题或分步生成计划后重试')
    if reason and reason != 'stop':
        raise ApiError(502, 50202, '模型未完整返回回答，请调整问题后重试')

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


def resolve_base_url(provider: str, base_url: str = '') -> str:
    base = (base_url or PROVIDERS.get(provider, {}).get('base_url', '')).strip().rstrip('/')
    if not base.startswith(('http://', 'https://')):
        raise ApiError(400, 40001, '服务商地址无效')
    return base


def default_model(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get('default_model', '')


async def call_openai(base_url: str, api_key: str, model: str, messages: list,
                      max_tokens: int = 1200) -> dict:
    """OpenAI 兼容 /chat/completions，返回内容与用量。"""
    started = time.monotonic()
    url = base_url + '/chat/completions'
    payload = {'model': model, 'messages': messages, 'temperature': 0.3,
               'max_tokens': max_tokens, 'stream': False}
    headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15),
                                     trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError:
        raise ApiError(502, 50201, 'AI 服务连接失败，请检查网络或服务商地址') from None
    if resp.status_code != 200:
        hint = {401: 'API Key 无效或已失效', 403: '模型权限不足',
                404: '模型不可用，请检查模型名', 429: '调用频率超限或额度不足'}.get(resp.status_code)
        raise ApiError(502, 50201, hint or 'AI 服务暂时不可用，请稍后重试')
    try:
        data = resp.json()
        choice = data['choices'][0]
        content = choice['message']['content'].strip()
        usage = data.get('usage') or {}
    except Exception:
        raise ApiError(502, 50201, 'AI 返回内容解析失败') from None
    check_finish_reason(choice.get('finish_reason'))
    return {
        'content': content,
        'prompt_tokens': usage.get('prompt_tokens'),
        'completion_tokens': usage.get('completion_tokens'),
        'latency_ms': int((time.monotonic() - started) * 1000),
    }


async def stream_openai_compat(url: str, api_key: str, payload: dict,
                               label: str = 'AI'):
    """OpenAI 兼容流式接口：逐段产出 delta，最后产出用量。

    部分服务商不接受 stream_options，首次 400 时自动重试一次去掉该字段。
    """
    started = time.monotonic()
    headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
    base_payload = {**payload, 'stream': True}
    usage = None
    finished = False
    finish_reason = None
    saw_content = False
    for attempt in (0, 1):
        body = dict(base_payload)
        if attempt == 0:
            body['stream_options'] = {'include_usage': True}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15),
                                         trust_env=False) as client:
                async with client.stream('POST', url, headers=headers, json=body) as resp:
                    if resp.status_code == 400 and attempt == 0:
                        await resp.aread()
                        continue
                    if resp.status_code != 200:
                        await resp.aread()
                        hint = {401: 'API Key 无效或已失效', 403: '模型权限不足',
                                404: '模型不可用，请检查模型名',
                                429: '调用频率超限或额度不足'}.get(resp.status_code)
                        raise ApiError(502, 50201, hint or f'{label}服务暂时不可用，请稍后重试')
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith('data:'):
                            continue
                        data = line[5:].strip()
                        if data == '[DONE]':
                            finished = True
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        if obj.get('usage'):
                            usage = obj['usage']
                        choices = obj.get('choices') or []
                        if choices:
                            if choices[0].get('finish_reason'):
                                finish_reason = choices[0]['finish_reason']
                                finished = True
                            delta = (choices[0].get('delta') or {}).get('content')
                            if delta:
                                if not isinstance(delta, str): raise ApiError(502, 50201, '模型流式内容格式无效')
                                saw_content = True
                                yield {'delta': delta}
                    break
        except httpx.HTTPError:
            raise ApiError(502, 50201, f'{label}连接失败，请稍后重试') from None
    check_finish_reason(finish_reason)
    if not finished or not saw_content:
        raise ApiError(502, 50201, '模型连接提前结束或未返回有效回答，请重试')
    yield {'usage': usage or {}, 'latency_ms': int((time.monotonic() - started) * 1000)}


async def stream_ark(settings, messages):
    """历史测试占位（火山方舟），生产聊天不调用。"""
    if not settings.ai_enabled:
        raise ApiError(503, 50301, 'AI 尚未配置（服务端未填写火山方舟 Key）')
    url = settings.volc_base_url.rstrip('/') + '/chat/completions'
    payload = {'model': settings.volc_model, 'messages': messages,
               'temperature': 0.3, 'max_tokens': settings.ai_max_tokens}
    async for chunk in stream_openai_compat(url, settings.volc_api_key, payload):
        yield chunk


async def stream_openai(base_url: str, api_key: str, model: str, messages: list,
                        max_tokens: int = 1200):
    """VIP 自填 Key 的流式输出。"""
    payload = {'model': model, 'messages': messages, 'temperature': 0.3,
               'max_tokens': max_tokens}
    async for chunk in stream_openai_compat(base_url + '/chat/completions',
                                            api_key, payload):
        yield chunk


class ModelCatalog(list):
    def __init__(self):
        super().__init__()
        self.details = []


async def fetch_models(base_url: str, api_key: str) -> list:
    """用用户 Key 实时拉取模型列表；失败由调用方降级为手填。"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=5),
                                     trust_env=False) as client:
            resp = await client.get(base_url + '/models',
                                    headers={'Authorization': 'Bearer ' + api_key})
        if resp.status_code != 200:
            status=resp.status_code
            code={401:'AI_KEY_INVALID',403:'AI_KEY_INVALID',402:'AI_NO_QUOTA',404:'AI_NO_MODELS_API',405:'AI_NO_MODELS_API',429:'AI_RATE_LIMITED'}.get(status,'AI_UPSTREAM_ERROR')
            return failed_catalog(code,resp.headers.get('Retry-After'))
        data = resp.json()
        rows = data.get('data') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return failed_catalog('AI_MODELS_EMPTY')
        models = ModelCatalog()
        for row in rows[:1000]:
            mid = row.get('id') if isinstance(row, dict) else None
            if isinstance(mid, str) and 0 < len(mid) <= 120 and mid not in models:
                models.append(mid)
                capabilities = row.get('capabilities') if isinstance(row.get('capabilities'), dict) else {}
                context = row.get('context_length') or row.get('context_window') or row.get('max_model_len')
                vision = capabilities.get('vision', row.get('supports_vision'))
                models.details.append({'id': mid,
                    'context_length': context if isinstance(context, int) and not isinstance(context, bool) and 0 < context <= 10000000 else None,
                    'supports_images': vision if isinstance(vision, bool) else None})
                if len(models) >= 200: break
        return models if models else failed_catalog('AI_MODELS_EMPTY')
    except httpx.TimeoutException:
        return failed_catalog('AI_UPSTREAM_TIMEOUT')
    except (httpx.HTTPError, ValueError):
        return failed_catalog('AI_UPSTREAM_ERROR')


CATALOG_ERRORS={
 'AI_KEY_INVALID':'API密钥无效，或该账号无权读取模型列表，可手动填写模型ID',
 'AI_NO_QUOTA':'供应商报告额度不足，请检查账单，也可手动填写模型ID',
 'AI_NO_MODELS_API':'该服务商不支持模型目录接口，请手动填写模型ID',
 'AI_MODELS_EMPTY':'供应商返回空目录，请手动填写模型ID',
 'AI_UPSTREAM_TIMEOUT':'供应商响应超时，可重试或手动填写模型ID',
 'AI_RATE_LIMITED':'供应商请求限流，请稍后重试或手动填写模型ID',
 'AI_UPSTREAM_ERROR':'供应商暂不可用，可重试或手动填写模型ID'}

def failed_catalog(code,retry=None):
    result=ModelCatalog()
    result.error={'code':code,'message':CATALOG_ERRORS[code]}
    if retry and str(retry).isdigit():result.error['retry_after']=min(int(retry),3600)
    return result

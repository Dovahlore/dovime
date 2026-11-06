# -*- coding: utf-8 -*-
"""dovime —— 龙语输入法（Dovahzul IME）独立运行版。

与 dovahwall.cn 主站里的 /s/ime 同一套页面与词典，脱离 Django 站点独立运行：

    pip install -r requirements.txt
    python app.py            →  http://127.0.0.1:8000

AI 直译/润色需要一个 OpenAI 兼容的 API Key，只从环境变量或同目录 .env 读取：
    IME_AI_KEY（也兼容 DEEPSEEK_KEY / DASHSCOPE_API_KEY）
仓库里不含任何 Key；Key 只在服务端使用，浏览器端不接触。
"""
import json
import os
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dovzul_lexicon import get_lexicon

from flask import Flask, Response, jsonify, render_template, request, stream_with_context


def _load_dotenv():
    """极简 .env 加载（不覆盖已存在的环境变量；.env 已被 .gitignore 排除）。"""
    p = BASE_DIR / ".env"
    if not p.exists():
        return
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

app = Flask(__name__)

# AI 供应商：任意 OpenAI 兼容端点。默认与 dovahwall.cn 线上同款（dashscope + deepseek-v4-pro）。
PROVIDER = {
    "name": os.environ.get("IME_AI_NAME", "default"),
    "api_key": (
        os.environ.get("IME_AI_KEY")
        or os.environ.get("DEEPSEEK_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or ""
    ),
    "base_url": os.environ.get("IME_AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "model": os.environ.get("IME_AI_MODEL", "deepseek-v4-pro"),
    "timeout": float(os.environ.get("IME_AI_TIMEOUT", "15") or 15),
    "max_retries": int(os.environ.get("IME_AI_MAX_RETRIES", "0") or 0),
}

SYS_FWD = (
    "你是《上古卷轴5》龙语(Dovahzul)翻译专家。用户给出一句中文与一条离线逐词参考（可能有误，仅供参考）。"
    "请把中文直接译成龙语拉丁转写：主谓宾陈述语序（疑问句也用陈述语序）；动词无时态，需要时用助词 fen=将、fent=应当、"
    "drey=曾经、lost=已经、los=正在/是；通常不用冠词（fin/faal=the、aan=a 仅需强调时用）；属格 dii=我的、hin=你的、"
    "ok=他的、ek=她的，或词尾 i/u；复数=重复词尾字母加 e；完成体词尾 aan；否定 ni/nid；复合词中心词在前；"
    "撇号可省略（Zu'u 与 Zuu 均可）；没有字母 C，用 K；人名等专名按发音音译。"
    "你可以调用 dict_lookup 工具查询龙语词典验证用词——把需要验证的词全部合并进一次调用（queries 列表），不要逐词反复调用，查 1-2 轮内完成。只使用词典里真实存在的词。"
    "只输出这一句龙语拉丁转写本身，不加任何解释与标点。"
)
SYS_REV = (
    "你是《上古卷轴5》龙语(Dovahzul)翻译专家。用户会给出一行龙语拉丁转写原文，以及一条离线逐词参考（可能有误，仅供参考）。"
    "请按龙语语法自己理解原文，译成一句通顺自然的中文。龙语语法要点：语序主谓宾近似英语但更简单；"
    "动词无时态变化，助词 fen=将、fent=应当、drey=曾经、lost=已经、los=正在/是；冠词 fin/faal=the、aan=a/an；"
    "属格：词尾 i=他的/其、u=我们的，独立代词 dii=我的、hin=你的、ok=他的、ek=她的；复数=重复词尾字母加 e；"
    "完成体词尾 aan；否定 ni/nid，前缀 vo- 表相反；复合词中心词在前（vulonkrein=夜+太阳=月）；"
    "撇号只是转写记号可忽略；字母 C 一律写作 K。未收录词多为汉字拼音或专有名词音译，请按最合理的中文还原（如人名）。"
    "你可以调用 dict_lookup 工具查询龙语词典核对词义——把要核对的词合并进一次调用（queries 列表），不要逐词反复调用。只输出这一句中文本身，不加解释。"
)

MAX_TEXT_CHARS = 2000
MAX_TOOL_ROUNDS = 3      # 含工具的轮次上限，超出后不再提供工具
MAX_TOOL_CALLS = 10      # 每请求工具调用总次数预算，超出后不再提供工具

TOOLS = [{
    "type": "function",
    "function": {
        "name": "dict_lookup",
        "description": (
            "查龙语词典（thuum.org 全量 4227 词），支持一次查多个词。queries 里每项可为龙语词（jun）、"
            "英文义项（king）或中文词（王）；返回每个词的匹配词条：龙语词 | 英文义项 | 正典级别 | 词性 | 中文。"
            "请把需要查的词全部合并进一次调用（queries 列表），不要逐词多次调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要查询/验证的词列表（最多 10 个）",
                }
            },
            "required": ["queries"],
        },
    },
}]


def _open_client(provider):
    from openai import OpenAI

    return OpenAI(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        timeout=provider.get("timeout", 15.0),
        max_retries=provider.get("max_retries", 0),
    )


def _run_dict_lookup(args_json):
    try:
        data = json.loads(args_json or "{}")
    except Exception:
        data = {}
    queries = data.get("queries")
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list) or not queries:
        single = data.get("query")
        queries = [single] if isinstance(single, str) and single.strip() else []
    queries = [str(q).strip() for q in queries if str(q).strip()][:10]
    if not queries:
        return "未提供要查询的词"
    lex = get_lexicon()
    parts = []
    for q in queries:
        entries = lex.lookup(q, limit=4)
        if not entries:
            parts.append("【%s】词典无匹配" % q)
        else:
            parts.append("【%s】\n%s" % (q, "\n".join(lex.entry_line(e) for e in entries)))
    return "\n\n".join(parts)


@app.get("/")
@app.get("/ime")
def page():
    """龙语输入法（Dovahzul IME）页面：离线转换引擎 + AI 直译/润色。"""
    return render_template("ime.html")


@app.get("/healthz")
def healthz():
    lex = get_lexicon()
    return jsonify({
        "ok": True,
        "lexicon": lex.size,
        "model": PROVIDER["model"],
        "ai_configured": bool(PROVIDER["api_key"]),
    })


@app.post("/ime/ai")
def translate():
    """POST {direction: 'fwd'|'rev', text: str} → text/plain 流式（<think>…思考/查词…</think>正文）。"""
    try:
        data = json.loads(request.get_data(cache=True) or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"success": False, "error": "请求体不是合法 JSON"}), 400

    direction = data.get("direction", "fwd")
    if direction not in ("fwd", "rev"):
        return jsonify({"success": False, "error": "direction 只能是 fwd 或 rev"}), 400

    text = str(data.get("text", ""))[:MAX_TEXT_CHARS].strip()
    if not text:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    if not PROVIDER["api_key"]:
        return jsonify({
            "success": False,
            "error": "未配置 AI Key：请设置环境变量 IME_AI_KEY（或 DEEPSEEK_KEY / DASHSCOPE_API_KEY），"
                     "或复制 .env.example 为 .env 填入。词典与离线转换不受影响。",
        }), 503

    providers = [PROVIDER]
    messages = [
        {"role": "system", "content": SYS_FWD if direction == "fwd" else SYS_REV},
        {"role": "user", "content": text},
    ]

    def generate():
        state = {"produced": False, "in_think": False, "closed": False}
        failures = []

        def clean(piece):
            return piece.replace("<think>", "").replace("</think>", "")

        for provider in providers:
            try:
                client = _open_client(provider)
                msgs = list(messages)
                tool_budget = MAX_TOOL_CALLS
                for _round in range(MAX_TOOL_ROUNDS):
                    kwargs = dict(model=provider["model"], stream=True, temperature=0.2, messages=msgs)
                    use_tools = tool_budget > 0
                    try:
                        stream = client.chat.completions.create(
                            tools=TOOLS, tool_choice="auto", **kwargs) if use_tools else client.chat.completions.create(**kwargs)
                    except Exception as exc:
                        if use_tools and "tool" in str(exc).lower():
                            stream = client.chat.completions.create(**kwargs)
                        else:
                            raise

                    tool_calls = {}
                    round_content = []  # 工具轮里的 content 可能是「发起工具前的自言自语」，先缓冲，轮次结束再定性
                    for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None)
                        if reasoning:
                            if not state["in_think"]:
                                state["in_think"] = True
                                yield "\n<think>\n"
                            yield clean(reasoning)
                        content = getattr(delta, "content", None)
                        if content:
                            round_content.append(content)
                        calls = getattr(delta, "tool_calls", None)
                        if calls:
                            for tc in calls:
                                idx = getattr(tc, "index", 0) or 0
                                slot = tool_calls.setdefault(idx, {"id": "", "name": "", "args": ""})
                                if getattr(tc, "id", None):
                                    slot["id"] = tc.id
                                fn = getattr(tc, "function", None)
                                if fn is not None:
                                    if getattr(fn, "name", None):
                                        slot["name"] = slot["name"] or fn.name
                                    if getattr(fn, "arguments", None):
                                        slot["args"] += fn.arguments

                    if not tool_calls:
                        # 本轮无工具调用：缓冲的 content 即最终答案
                        if round_content:
                            if state["in_think"] and not state["closed"]:
                                state["closed"] = True
                                yield "\n</think>\n\n"
                            state["produced"] = True
                            yield clean("".join(round_content))
                        break

                    # 本轮发起了工具调用：content 归入思考流，不算正文
                    if round_content:
                        if not state["in_think"]:
                            state["in_think"] = True
                            yield "\n<think>\n"
                        yield clean("".join(round_content)) + "\n"
                    tool_budget -= len(tool_calls)

                    ordered = [tool_calls[k] for k in sorted(tool_calls)]
                    msgs.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": s["id"] or "call_%d" % i, "type": "function",
                             "function": {"name": s["name"], "arguments": s["args"] or "{}"}}
                            for i, s in enumerate(ordered)
                        ],
                    })
                    for i, s in enumerate(ordered):
                        if s["name"] == "dict_lookup":
                            result = _run_dict_lookup(s["args"])
                        else:
                            result = "未知工具: " + s["name"]
                        if not state["in_think"]:
                            state["in_think"] = True
                            yield "\n<think>\n"
                        try:
                            payload = json.loads(s["args"] or "{}")
                            qs = payload.get("queries") or payload.get("query") or s["args"][:40]
                            q_prev = ", ".join(qs) if isinstance(qs, list) else qs
                        except Exception:
                            q_prev = s["args"][:40]
                        yield "\n🔧 dict_lookup(%s)\n%s\n" % (q_prev, result)
                        msgs.append({
                            "role": "tool",
                            "tool_call_id": s["id"] or "call_%d" % i,
                            "content": result[:4000],
                        })

                # 工具轮次/预算耗尽仍无正文：无工具强制终答一轮
                if not state["produced"]:
                    stream = client.chat.completions.create(
                        model=provider["model"], stream=True, temperature=0.2, messages=msgs)
                    for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None)
                        if content:
                            if state["in_think"] and not state["closed"]:
                                state["closed"] = True
                                yield "\n</think>\n\n"
                            state["produced"] = True
                            yield clean(content)

                if state["in_think"] and not state["closed"]:
                    state["closed"] = True
                    yield "\n</think>\n\n"
                if not state["produced"]:
                    yield "[AI 这次没吐出译文（供应商抖动），请重试一次]"
                return
            except Exception as exc:
                if state["produced"]:
                    return  # 已流出部分正文，不重复追发
                failures.append("%s: %s" % (provider.get("name", "?"), exc))
                print("[dovime %s AI stream failed] %s" % (provider.get("name", "?"), exc))
                continue

        if state["in_think"] and not state["closed"]:
            yield "\n</think>\n\n"
        detail = "; ".join(failures) or "no providers configured"
        yield "\n[AI 调用异常：All AI providers failed: %s]" % detail

    response = Response(stream_with_context(generate()), content_type="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Accel-Buffering"] = "no"
    return response


if __name__ == "__main__":
    host = os.environ.get("IME_HOST", "127.0.0.1")
    port = int(os.environ.get("IME_PORT", "8000") or 8000)
    debug = os.environ.get("IME_DEBUG", "").lower() in ("1", "true", "yes")
    print(" * dovime 龙语输入法 → http://%s:%d" % (host, port))
    print(" * AI Key: %s（未配置时页面离线功能可用，AI 按钮会提示 503）" % ("已配置" if PROVIDER["api_key"] else "未配置"))
    app.run(host=host, port=port, debug=debug, threaded=True)

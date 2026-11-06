# dovime · 龙语输入法（Dovahzul IME）

[English](README.md) | 简体中文

《上古卷轴5：天际》龙语（Dovahzul）学习与翻译网页应用——离线词典 + AI 双向翻译 + 符文打字机 + 学习小测。

这是 [dovahwall.cn](https://www.dovahwall.cn) 主站内「龙语输入法」的**独立运行版**：不依赖原站点，几个 Python 文件即可跑起来。

**在线体验**：<https://www.dovahwall.cn/s/ime>

## 功能

- **离线转换**：中文 ↔ 龙语逐词直译，内置 thuum.org 全量 4227 词词典（含正典级别 / 词性 / 构词注），点词可换候选
- **AI 直译**：中文直接译成符合语法的龙语拉丁转写（流式输出，模型思考与查词过程在「思考区」实时可见）
- **AI 润色**：龙语原文按语法译成通顺中文（可还原未收录的人名 / 拼音音译）
- **词典工具**：AI 翻译时可调用 `dict_lookup` 查询 / 验证词典（批量查询、调用预算限制）
- **符文打字机**：直接打拉丁字母即时出龙文符文（aa / ah / ii 等双元音自动合成单符文）
- **学习小测**：字母 / 词义 / 整句三档无限连刷，答错当场亮答案与解析
- 语法速成、27+5 条龙吼图鉴、屈折变化器、AI 翻译记录（本地存储，不上传）

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://127.0.0.1:8000
```

页面本体（词典 / 双向转换 / 符文 / 学习）完全离线可用。**AI 功能**需要一个 OpenAI 兼容 API Key：

```bash
# 方式一：环境变量
export IME_AI_KEY=你的Key        # Windows: set IME_AI_KEY=你的Key

# 方式二：复制 .env.example 为 .env，填入 IME_AI_KEY=你的Key
```

> Key 只在服务端读取，浏览器永远接触不到；`.env` 已被 `.gitignore` 排除，不会提交进仓库。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `IME_AI_KEY` | — | API Key（AI 功能必填；也兼容 `DEEPSEEK_KEY` / `DASHSCOPE_API_KEY`） |
| `IME_AI_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容端点 |
| `IME_AI_MODEL` | `deepseek-v4-pro` | 模型名 |
| `IME_AI_TIMEOUT` | `15` | 上游超时（秒） |
| `IME_HOST` / `IME_PORT` | `127.0.0.1` / `8000` | 监听地址 / 端口 |

默认值与 dovahwall.cn 线上同款。换其他供应商只需改两个变量，例如 DeepSeek 官方接口：

```bash
IME_AI_BASE_URL=https://api.deepseek.com/v1
IME_AI_MODEL=deepseek-chat
```

## 生产部署

```bash
pip install gunicorn
gunicorn -w 1 -b 0.0.0.0:8000 app:app --timeout 120
```

AI 接口是流式响应（响应已自带 `X-Accel-Buffering: no`）。若前面有 nginx，建议对该路径再显式关缓冲：

```nginx
location /ime/ai {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

## 目录结构

```
app.py                  # Flask 入口：页面 + /ime/ai 流式 AI 端点（含 dict_lookup 词典工具）
dovzul_lexicon.py       # 服务端词典：从前端 data.js / ref.js 解析 thuum.org 全量词库
templates/ime.html      # 单页应用：转换 / 词典 / 龙吼 / 语法 / 符文 / 学习
static/ime/js/          # core.js 转换引擎 + app.js UI + data.js/ref.js 词典数据 + font.js 字体加载
static/ime/font/        # Dragon Alphabet 字体（thuum.org）
static/ime/img/         # 图标
.env.example            # AI 配置模板（复制为 .env 使用，不入库）
```

## 安全说明

- 仓库不含任何 API Key；Key 仅从环境变量 / `.env` 读取
- AI 请求由服务端代理转发，前端不接触 Key，可直接公开部署
- AI 调用有预算限制（每请求 ≤10 次工具调用、≤3 轮、输入截断 2000 字符），防止滥用

## 致谢与声明

- 词典数据（4227 词）与 Dragon Alphabet 字体来自 [thuum.org](https://thuum.org) 社区词典
- 龙吼数据整理自 [UESP](https://en.uesp.net)
- 本项目为**非官方粉丝作品**；The Elder Scrolls 相关权利归 Bethesda Softworks / ZeniMax Media 所有，本项目与其无隶属关系，不作商业用途

## License

[MIT](LICENSE) © Dovahlore

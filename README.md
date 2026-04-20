# doc-fetch

> 多格式文档提取 + 简历结构化解析 + 网易 TASTED 六力评估工具

## 架构概览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              doc-fetch                                   │
│                                                                          │
│  main.py (CLI入口)                                                       │
│  python main.py <file|dir> [--parse] [--evaluate] [--report] [-o file]  │
│                                                                          │
├─────────────────────────┬────────────────────────────────────────────────┤
│                         │                                                │
│   Layer 1: 文本提取      │   Layer 2: 结构化解析 / TASTED评估             │
│   extractors/           │   parsers/                                     │
│                         │                                                │
│  ┌───────────────────┐  │  ┌──────────────────────────────────────────┐  │
│  │  extract_text()   │  │  │  parse_resume()      evaluate_tasted()  │  │
│  │  (统一入口)        │──┼──│  raw text            raw text           │  │
│  └───────┬───────────┘  │  │      │                    │              │  │
│          │ 注册表分派     │  │      ▼                    ▼              │  │
│          ▼              │  │  ┌─────────┐         ┌──────────────┐   │  │
│  ┌──────────────────┐   │  │  │ llm.md  │         │tasted-eval.md│   │  │
│  │ PDFExtractor     │   │  │  └────┬────┘         └──────┬───────┘   │  │
│  │ ┌──────────────┐ │   │  │       │                     │           │  │
│  │ │ get_text()   │ │   │  │       └──────────┬──────────┘           │  │
│  │ │ (嵌入文本)    │ │   │  │                  ▼                      │  │
│  │ └──────┬───────┘ │   │  │         LangChain ChatOpenAI            │  │
│  │        │ 乱码?    │   │  │         JsonOutputParser                │  │
│  │        ▼         │   │  └──────────────────────────────────────────┘  │
│  │ ┌──────────────┐ │   │                                                │
│  │ │ _is_legible()│ │   │   .env 配置                                    │
│  │ │ 三层检测:     │ │   │  ┌──────────────────────────────────────────┐  │
│  │ │ ①页级字符比  │ │   │  │ OPENAI_API_KEY=sk-xxx                    │  │
│  │ │ ②零CJK检测  │ │   │  │ BASE_URL=https://api.minimaxi...         │  │
│  │ │ ③行级乱码率  │ │   │  │ DEFAULT_LLM_PROVIDER=MiniMax-M2.5       │  │
│  │ └──────┬───────┘ │   │  └──────────────────────────────────────────┘  │
│  │        │ 不可读    │   │                                                │
│  │        ▼         │   │                                                │
│  │ ┌──────────────┐ │   │                                                │
│  │ │ RapidOCR     │ │   │                                                │
│  │ │ (中英文混排)  │ │   │                                                │
│  │ └──────┬───────┘ │   │                                                │
│  │        │ 不够?    │   │                                                │
│  │        ▼         │   │                                                │
│  │ ┌──────────────┐ │   │                                                │
│  │ │ Vision API   │ │   │                                                │
│  │ │ (GPT-4o)     │ │   │                                                │
│  │ └──────────────┘ │   │                                                │
│  │ + 长页分片 OCR   │   │                                                │
│  └──────────────────┘   │                                                │
│                         │                                                │
│  ┌──────────────────┐   │                                                │
│  │ DocxExtractor    │   │                                                │
│  │ 段落 + 表格       │   │                                                │
│  ├──────────────────┤   │                                                │
│  │ ExcelExtractor   │   │                                                │
│  │ 逐Sheet逐行      │   │                                                │
│  ├──────────────────┤   │                                                │
│  │ PptxExtractor    │   │                                                │
│  │ Slide→Shape→Text │   │                                                │
│  ├──────────────────┤   │                                                │
│  │ HTMLExtractor    │   │                                                │
│  │ BeautifulSoup    │   │                                                │
│  ├──────────────────┤   │                                                │
│  │ PlainTextExtractor│  │                                                │
│  │ TXT/MD/CSV/JSON  │   │                                                │
│  └──────────────────┘   │                                                │
│                         │                                                │
└─────────────────────────┴────────────────────────────────────────────────┘
```

## 支持格式

| 格式   | 扩展名                                           | 提取方式                                   |
| ------ | ------------------------------------------------ | ------------------------------------------ |
| PDF    | `.pdf`                                           | PyMuPDF + RapidOCR + Vision API (三级策略) |
| Word   | `.docx` `.doc`                                   | python-docx                                |
| Excel  | `.xlsx` `.xls`                                   | pandas + openpyxl                          |
| PPT    | `.pptx`                                          | python-pptx                                |
| HTML   | `.html` `.htm`                                   | BeautifulSoup                              |
| 纯文本 | `.txt` `.md` `.csv` `.json` `.xml` `.log` `.rst` | 直接读取 + 编码检测                        |

## PDF 乱码检测 (三层防御)

针对 Type3 自定义字体导致的乱码问题，`_is_legible()` 实现了三层检测：

1. **页级字符比例** — CJK + ASCII 可打印字符占比 < 60% → 乱码
2. **零 CJK 检测** — 文本量 ≥ 100 字符、0 个 CJK、非 ASCII > 15% → 乱码
3. **行级乱码率** — 超过 15% 的行单独判定为乱码 → 整页 OCR（解决混合乱码）

## 使用方式

### 文本提取

```bash
# 提取单个文件
python main.py doc/resume4.pdf

# 提取目录下所有文件
python main.py doc/

# 输出到文件
python main.py doc/resume4.pdf -o output/text.txt
```

### 简历结构化解析 (`--parse`)

```bash
# 提取 + 结构化解析（输出 JSON）
python main.py doc/resume4.pdf --parse

# 输出到文件
python main.py doc/resume4.pdf --parse -o output/res4.json

# 指定模型
python main.py doc/resume4.pdf --parse --model gpt-4o
```

输出 JSON 结构示例：

```json
{
  "resumeBase": { "applicantName": "王若茵", "mobile": "138xxxxxxxx", "email": "..." },
  "resumeEducationList": [...],
  "resumeWorkExpList": [...],
  "resumeProjectList": [...]
}
```

### TASTED 六力评估 (`--evaluate`)

基于网易人才观 **TASTED 六力**，对候选人简历进行深度能力评估，输出结构化评分与招聘建议。

```bash
# 评估单份简历（输出 JSON）
python main.py doc/resume4.pdf --evaluate

# 输出可读 Markdown 报告
python main.py doc/resume4.pdf --evaluate --report

# 保存评估报告到文件
python main.py doc/resume4.pdf --evaluate --report -o output/report_resume4.md

# 批量评估目录下所有简历
python main.py doc/ --evaluate -o output/batch_tasted.json
```

#### TASTED 六力说明

| 维度   | 英文       | 核心问题                           |
| ------ | ---------- | ---------------------------------- |
| 审美力 | Taste      | 对产品与体验有超越功能的感知与追求 |
| 洞察力 | Awareness  | 穿透表象，发现本质规律与趋势信号   |
| 标准感 | Standard   | 拥有内在质量基准，拒绝平庸         |
| 结构力 | Tectonics  | 将复杂问题拆解为清晰可执行框架     |
| 判断力 | Evaluation | 在不确定中给出有依据的正确决策     |
| 自驱力 | Drive      | 强烈内在动机，主动出发持续前进     |

#### 评估输出结构（JSON）

```json
{
  "candidate": {
    "name": "王若茵",
    "currentPosition": "游戏交互设计师",
    "yearsOfExperience": 3
  },
  "tastedEvaluation": {
    "taste": {
      "score": 8,
      "evidence": ["负责核心玩法UI设计..."],
      "comment": "审美力突出"
    },
    "awareness": { "score": 7, "evidence": ["..."], "comment": "..." },
    "standard": { "score": 6, "evidence": ["..."], "comment": "..." },
    "tectonics": { "score": 7, "evidence": ["..."], "comment": "..." },
    "evaluation": { "score": 6, "evidence": ["..."], "comment": "..." },
    "drive": {
      "score": 9,
      "evidence": ["独立推进..."],
      "comment": "自驱力极强"
    }
  },
  "summary": {
    "totalScore": 43,
    "level": "A",
    "strengths": ["自驱力", "审美力"],
    "weaknesses": ["标准感"],
    "overallComment": "候选人综合能力较强，适合...",
    "recommendation": "推荐"
  }
}
```

#### 综合等级与招聘建议

| 等级 | 总分区间 | 招聘建议           |
| ---- | -------- | ------------------ |
| S    | ≥ 50     | 强烈推荐           |
| A    | 40–49    | 推荐               |
| B    | 30–39    | 待定（需面试验证） |
| C    | < 30     | 暂不推荐           |

## 代码调用

```python
from extractors import extract_text
from parsers.resume import parse_resume
from parsers.tasted import evaluate_tasted, format_tasted_report

text = extract_text("resume.pdf")       # 提取原始文本

data = parse_resume(text)               # 结构化简历 JSON

result = evaluate_tasted(text)          # TASTED 六力评估 JSON
report = format_tasted_report(result)   # 格式化为 Markdown 报告
```

## API 服务

### 启动服务

```bash
# 方式一：直接运行
python -m api.app

# 方式二：使用 uvicorn
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问：

- **API 地址**：<http://localhost:8000>
- **Swagger 文档**：<http://localhost:8000/docs>
- **ReDoc 文档**：<http://localhost:8000/redoc>

### 接口列表

| 方法   | 路径        | 说明                                        |
| ------ | ----------- | ------------------------------------------- |
| `GET`  | `/health`   | 健康检查 & 返回支持的文件格式列表           |
| `POST` | `/extract`  | 上传文件 → 返回提取的原始文本               |
| `POST` | `/parse`    | 上传简历 → 返回结构化 JSON                  |
| `POST` | `/evaluate` | 上传简历 → 返回 TASTED 六力评估             |
| `POST` | `/analyze`  | 上传简历 → **组合分析**（parse + evaluate） |

### 接口详情

#### `POST /extract` — 文本提取

```bash
curl -X POST http://localhost:8000/extract \
  -F "file=@doc/resume4.pdf"
```

返回：

```json
{ "filename": "resume4.pdf", "chars": 2345, "text": "..." }
```

#### `POST /parse` — 简历结构化解析

```bash
curl -X POST http://localhost:8000/parse \
  -F "file=@doc/resume4.pdf"

# 指定模型
curl -X POST "http://localhost:8000/parse?model=gpt-4o" \
  -F "file=@doc/resume4.pdf"
```

返回：

```json
{
  "filename": "resume4.pdf",
  "chars": 2345,
  "data": {
    "resumeBase": {...},
    "resumeEducationList": [...],
    "resumeWorkExpList": [...],
    "resumeProjectList": [...]
  }
}
```

#### `POST /evaluate` — TASTED 六力评估

```bash
# JSON 格式
curl -X POST http://localhost:8000/evaluate \
  -F "file=@doc/resume4.pdf"

# Markdown 报告
curl -X POST "http://localhost:8000/evaluate?report=true" \
  -F "file=@doc/resume4.pdf"
```

参数：

| 参数     | 类型   | 默认    | 说明                          |
| -------- | ------ | ------- | ----------------------------- |
| `file`   | File   | 必填    | 简历文件                      |
| `model`  | string | 默认LLM | 指定 LLM 模型                 |
| `report` | bool   | false   | `true` 返回 Markdown 格式报告 |

#### `POST /analyze` — 组合分析（推荐）

**一次请求，同时返回结构化简历 + TASTED 评估 + 快速摘要**

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@doc/resume4.pdf"

# 包含 Markdown 报告
curl -X POST "http://localhost:8000/analyze?report=true" \
  -F "file=@doc/resume4.pdf"
```

返回结构：

```json
{
  "filename": "resume4.pdf",
  "chars": 2345,

  "summary": {
    "candidateName": "王若茵",
    "currentPosition": "游戏交互设计师",
    "yearsOfExperience": 3,
    "tastedLevel": "A",
    "tastedScore": 43,
    "recommendation": "推荐",
    "strengths": ["自驱力", "审美力"],
    "weaknesses": ["标准感"]
  },

  "parsed": {
    "resumeBase": {...},
    "resumeEducationList": [...],
    "resumeWorkExpList": [...],
    "resumeProjectList": [...]
  },

  "evaluation": {
    "candidate": {...},
    "tastedEvaluation": {...},
    "summary": {...}
  },

  "report": "# TASTED 六力评估报告\n..."
}
```

> 💡 **`summary` 字段**：提供快速概览，无需深入解析 `parsed` 和 `evaluation` 即可获取候选人关键信息。

## 配置 (.env)

```env
OPENAI_API_KEY=sk-xxx
BASE_URL=https://api.minimaxi.com/v1
DEFAULT_LLM_PROVIDER=MiniMax-M2.5
```

## 项目结构

```
doc-fetch/
├── main.py                    # CLI 入口
├── requirements.txt
├── .env                       # API 配置（不纳入版本控制）
├── .env.example               # 配置模板
├── api/                       # FastAPI 服务层
│   ├── __init__.py
│   └── app.py                 # FastAPI 应用（/extract /parse /evaluate /analyze）
├── prompts/
│   ├── llm.md                 # 简历结构化解析 prompt
│   ├── tasted-eval.md         # TASTED 六力评估 prompt
│   └── netease-tasted.md      # TASTED 六力说明文档
├── extractors/                # 文本提取层
│   ├── __init__.py            # 注册表 + extract_text()
│   ├── base.py                # Extractor ABC
│   ├── pdf.py                 # PDF 三级策略 + 乱码检测 + 长页分片
│   ├── docx.py                # Word
│   ├── xlsx.py                # Excel
│   ├── pptx.py                # PPT
│   ├── html.py                # HTML
│   └── plaintext.py           # 纯文本
├── parsers/                   # 解析 & 评估层
│   ├── __init__.py
│   ├── resume.py              # LangChain 简历结构化解析
│   └── tasted.py              # TASTED 六力评估 + Markdown报告生成
├── doc/                       # 测试简历文件
├── output/                    # 解析 / 评估结果输出
└── result/                    # 历史提取文本
```

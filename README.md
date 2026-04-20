# doc-fetch

> 多格式文档提取 + 简历结构化解析工具

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                          doc-fetch                                  │
│                                                                     │
│  main.py (CLI入口)                                                  │
│  python main.py <file|dir> [--parse] [-o output] [--model MODEL]   │
│                                                                     │
├─────────────────────────┬───────────────────────────────────────────┤
│                         │                                           │
│   Layer 1: 文本提取      │   Layer 2: 结构化解析                     │
│   extractors/           │   parsers/                                │
│                         │                                           │
│  ┌───────────────────┐  │  ┌─────────────────────────────────────┐  │
│  │  extract_text()   │  │  │  parse_resume()                    │  │
│  │  (统一入口)        │──┼──│  raw text → structured JSON        │  │
│  └───────┬───────────┘  │  │                                     │  │
│          │ 注册表分派     │  │  ┌──────────┐  ┌────────────────┐  │  │
│          ▼              │  │  │PromptFile│→│  LangChain     │  │  │
│  ┌──────────────────┐   │  │  │llm.md    │  │  ChatOpenAI    │  │  │
│  │ PDFExtractor     │   │  │  └──────────┘  │  JsonParser    │  │  │
│  │ ┌──────────────┐ │   │  │                └────────────────┘  │  │
│  │ │ get_text()   │ │   │  └─────────────────────────────────────┘  │
│  │ │ (嵌入文本)    │ │   │                                           │
│  │ └──────┬───────┘ │   │   .env 配置                               │
│  │        │ 乱码?    │   │  ┌─────────────────────────────────────┐  │
│  │        ▼         │   │  │ OPENAI_API_KEY=sk-xxx               │  │
│  │ ┌──────────────┐ │   │  │ BASE_URL=https://api.minimaxi...    │  │
│  │ │ _is_legible()│ │   │  │ DEFAULT_LLM_PROVIDER=MiniMax-M2.5  │  │
│  │ │ 三层检测:     │ │   │  └─────────────────────────────────────┘  │
│  │ │ ①页级字符比  │ │   │                                           │
│  │ │ ②零CJK检测  │ │   │                                           │
│  │ │ ③行级乱码率  │ │   │                                           │
│  │ └──────┬───────┘ │   │                                           │
│  │        │ 不可读    │   │                                           │
│  │        ▼         │   │                                           │
│  │ ┌──────────────┐ │   │                                           │
│  │ │ RapidOCR     │ │   │                                           │
│  │ │ (中英文混排)  │ │   │                                           │
│  │ └──────┬───────┘ │   │                                           │
│  │        │ 不够?    │   │                                           │
│  │        ▼         │   │                                           │
│  │ ┌──────────────┐ │   │                                           │
│  │ │ Vision API   │ │   │                                           │
│  │ │ (GPT-4o)     │ │   │                                           │
│  │ └──────────────┘ │   │                                           │
│  │ + 长页分片 OCR   │   │                                           │
│  └──────────────────┘   │                                           │
│                         │                                           │
│  ┌──────────────────┐   │                                           │
│  │ DocxExtractor    │   │                                           │
│  │ 段落 + 表格       │   │                                           │
│  ├──────────────────┤   │                                           │
│  │ ExcelExtractor   │   │                                           │
│  │ 逐Sheet逐行      │   │                                           │
│  ├──────────────────┤   │                                           │
│  │ PptxExtractor    │   │                                           │
│  │ Slide→Shape→Text │   │                                           │
│  ├──────────────────┤   │                                           │
│  │ HTMLExtractor    │   │                                           │
│  │ BeautifulSoup    │   │                                           │
│  ├──────────────────┤   │                                           │
│  │ PlainTextExtractor│  │                                           │
│  │ TXT/MD/CSV/JSON  │   │                                           │
│  └──────────────────┘   │                                           │
│                         │                                           │
└─────────────────────────┴───────────────────────────────────────────┘
```

## 支持格式

| 格式 | 扩展名 | 提取方式 |
|------|--------|---------|
| PDF | `.pdf` | PyMuPDF + RapidOCR + Vision API (三级策略) |
| Word | `.docx` `.doc` | python-docx |
| Excel | `.xlsx` `.xls` | pandas + openpyxl |
| PPT | `.pptx` | python-pptx |
| HTML | `.html` `.htm` | BeautifulSoup |
| 纯文本 | `.txt` `.md` `.csv` `.json` `.xml` `.log` `.rst` | 直接读取 + 编码检测 |

## PDF 乱码检测 (三层防御)

针对 Type3 自定义字体导致的乱码问题，`_is_legible()` 实现了三层检测：

1. **页级字符比例** — CJK + ASCII 可打印字符占比 < 60% → 乱码
2. **零 CJK 检测** — 文本量 ≥ 100 字符、0 个 CJK、非 ASCII > 15% → 乱码
3. **行级乱码率** — 超过 15% 的行单独判定为乱码 → 整页 OCR（解决混合乱码）

## 使用方式

```bash
# 文本提取
python main.py doc/resume4.pdf

# 提取 + 结构化解析
python main.py doc/resume4.pdf --parse

# 输出到文件
python main.py doc/resume4.pdf --parse -o output/res4.json

# 指定模型
python main.py doc/resume4.pdf --parse --model gpt-4o
```

## 代码调用

```python
from extractors import extract_text
from parsers.resume import parse_resume

text = extract_text("resume.pdf")    # raw text
data = parse_resume(text)            # structured JSON
```

## 配置 (.env)

```env
OPENAI_API_KEY=sk-xxx
BASE_URL=https://api.minimaxi.com/v1
DEFAULT_LLM_PROVIDER=MiniMax-M2.5
```

## 项目结构

```
doc-fetch/
├── main.py                  # CLI 入口
├── requirements.txt
├── .env                     # API 配置
├── prompts/
│   └── llm.md               # 简历结构化 prompt
├── extractors/              # 文本提取层
│   ├── __init__.py          # 注册表 + extract_text()
│   ├── base.py              # Extractor ABC
│   ├── pdf.py               # PDF 三级策略 + 乱码检测 + 长页分片
│   ├── docx.py              # Word
│   ├── xlsx.py              # Excel
│   ├── pptx.py              # PPT
│   ├── html.py              # HTML
│   └── plaintext.py         # 纯文本
├── parsers/                 # 结构化解析层
│   ├── __init__.py
│   └── resume.py            # LangChain 简历解析
├── doc/                     # 测试简历 PDF
└── output/                  # 解析结果 JSON
```

# epub-pdf

将 EPUB 电子书转换为适合连续阅读的 PDF。可选地，在写入 PDF 前通过 OpenAI 兼容的 Responses API 翻译章节内容。

## 安装

使用 `uv` 同步项目环境和依赖：

```powershell
uv sync --extra dev
```

## 基本转换

```powershell
uv run epub-pdf .\book.epub -o .\book.pdf
```

## 图形界面

启动桌面程序：

```powershell
uv run epub-pdf-gui
```

界面中可选择 EPUB 和 PDF 输出位置，输入 API 地址和密钥后点击“测试连接并获取模型”。连接成功后，从模型下拉框选择一个支持 Responses API 的文本模型，再执行翻译。转换完成后会显示完整输出路径，并提供“打开 PDF”和“打开所在文件夹”按钮。API 密钥不会被保存。

转换器按 EPUB 的 spine（阅读顺序）读取正文，保留标题、段落、列表、引用与代码块，并生成带页眉和页码的 A4 PDF。

Windows 会自动探测常见中文字体；也可显式指定支持中文的 TrueType 字体：

```powershell
uv run epub-pdf .\book.epub -o .\book.pdf --font C:\Windows\Fonts\simhei.ttf
```

## 翻译后转换

设置 API 配置后添加 `--translate`：

```powershell
$env:OPENAI_API_KEY = "your-api-key"
uv run epub-pdf .\english-book.epub -o .\chinese-book.pdf --translate --target-language "简体中文" --model gpt-5.6-terra --font C:\Windows\Fonts\simhei.ttf
```

默认请求地址为 `https://api.openai.com/v1/responses`。兼容 OpenAI Responses API 的服务可覆盖根地址：

```powershell
uv run epub-pdf .\book.epub -o .\book.pdf --translate --api-base http://localhost:8000/v1 --model your-model
```

翻译只处理正文段落；章节标题、EPUB 元数据和版式由本地程序处理。每个请求会按段落组切分，避免截断段落；单个超长段落会单独发送。`--chunk-size` 用于控制每组请求的目标字符数（默认 20000）。

## 常用参数

```text
--title TEXT              覆盖 PDF 标题
--author TEXT             覆盖 PDF 作者
--font PATH               覆盖自动探测的 TrueType 字体路径
--font-size NUMBER        正文字号，默认 10.5
--translate               调用模型翻译正文
--target-language TEXT    目标语言，默认 简体中文
--model TEXT              模型名，默认 gpt-5.6-terra
--api-base URL            OpenAI 兼容 API 根地址
--api-key TEXT            API Key；未指定时读取 OPENAI_API_KEY
--chunk-size NUMBER       单次翻译请求最大字符数，默认 20000
```

翻译会产生 API 费用。请先对短 EPUB 验证模型质量、目标语言和字体，再处理整本书。

## 开发

```powershell
uv sync --extra dev
uv run pytest
```

本项目只处理没有 DRM 限制、且你有权转换的 EPUB 文件。

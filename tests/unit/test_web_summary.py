from unittest.mock import MagicMock, patch
from inthon.tools.builtin_tools import _web_read_real
from examples.text_utils import clean_html, summarize_text


def test_web_read_real_charset_detection():
    # Test Content-Type header detection
    mock_resp = MagicMock()
    mock_resp.read.return_value = "Bonjour l'école".encode("iso-8859-1")
    mock_resp.headers = {"Content-Type": "text/html; charset=iso-8859-1"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = _web_read_real("http://dummy-url.com")
        assert "Bonjour l'école" in res

    # Test Meta charset tag detection
    mock_resp_meta = MagicMock()
    html_with_meta = (
        '<html><head><meta charset="gbk"></head><body>测试中文</body></html>'
    )
    mock_resp_meta.read.return_value = html_with_meta.encode("gbk")
    mock_resp_meta.headers = {}
    mock_resp_meta.__enter__.return_value = mock_resp_meta

    with patch("urllib.request.urlopen", return_value=mock_resp_meta):
        res = _web_read_real("http://dummy-url.com")
        assert "测试中文" in res


def test_clean_html_filtering():
    html = """
    <html>
      <head><title>Test Page</title></head>
      <body>
        <nav><a href="#">Home</a></nav>
        <header><h1>Welcome to Test Site</h1></header>
        <main>
          <p>This is the first main paragraph of the article. It should be extracted because it contains actual content.</p>
          <p>Here is another paragraph containing relevant news and features about the project.</p>
          <div>Some short text.</div>
        </main>
        <footer>Copyright 2026</footer>
        <script>console.log("hello");</script>
        <style>body { color: red; }</style>
      </body>
    </html>
    """
    cleaned = clean_html(html)
    assert "Home" not in cleaned
    assert "Welcome" not in cleaned
    assert "Copyright" not in cleaned
    assert "console.log" not in cleaned
    assert "This is the first main paragraph" in cleaned


def test_language_agnostic_summarize():
    # 1. English text
    english_text = (
        "Inthon is an agent-oriented programming language designed for AI workflows. "
        "It provides standard capabilities like sandboxed execution and persistent memory. "
        "Using Inthon, developers can build multi-agent architectures that execute complex tasks. "
        "Inthon features a tree-walk interpreter and a custom bytecode virtual machine. "
        "The bytecode VM executes loops up to fifty times faster than the interpreter. "
        "It also integrates with visual trace tools to inspect the agents' step-by-step reasoning. "
        "This makes Inthon a highly scalable and industrial grade tool for development."
    )
    summary_en = summarize_text(english_text, num_sentences=2)
    assert len(summary_en) > 0
    assert len(summary_en) < len(english_text)

    # 2. Chinese (CJK) text
    chinese_text = (
        "Inthon是一种专为人工智能工作流设计的面向智能体的编程语言。 "
        "它提供了诸如沙箱执行和持久性语义内存之类的标准功能。 "
        "利用Inthon，开发人员可以构建能够执行复杂任务的多智能体协作架构。 "
        "Inthon配备了树遍历解释器和自定义字节码虚拟机。 "
        "该虚拟机在处理循环时的执行速度比常规解释器快达五十倍。 "
        "它还与可视化跟踪工具无缝集成，便于审查智能体的推理过程。 "
        "这使得Inthon成为一个极具扩展性且达到工业级标准的开发工具。"
    )
    summary_zh = summarize_text(chinese_text, num_sentences=2)
    assert len(summary_zh) > 0
    assert len(summary_zh) < len(chinese_text)

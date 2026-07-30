"""Tests for the online web-search module (no live network required)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hallucination_detector import WebSearcher
from hallucination_detector.web_search import (
    _ngram_sim, _extract_uddg, _char_ngrams, _strip_tags,
)

SAMPLE_HTML = """
<div class="results--main">
  <div class="result results_links_deep">
    <a class="result__a" href="/l/?kh=-1&uddg=https%3A%2F%2Fexample.edu%2Fpaper">人工智能在教育领域的应用日益广泛</a>
    <a class="result__snippet" href="/l/?...">许多研究机构指出，个性化学习能够显著提升学生的学习效率。根据 Wang 等人（2023）的研究。</a>
    <span class="result__url">example.edu</span>
  </div>
  <div class="result results_links_deep">
    <a class="result__a" href="/l/?kh=-1&uddg=https%3A%2F%2Fother.com%2Fdoc">另一篇相关文章</a>
    <a class="result__snippet" href="/l/?...">深度学习模型需要大量标注数据，Transformer 架构自 2017 年提出。</a>
    <span class="result__url">other.com</span>
  </div>
  <div class="result results_links_deep">
    <a class="result__a" href="/l/?kh=-1&uddg=https%3A%2F%2Fshort.com%2Fx">短标题</a>
    <a class="result__snippet" href="/l/?...">snippet</a>
  </div>
</div>
"""


def test_parse_html_extracts_records():
    res = WebSearcher._parse_html(SAMPLE_HTML)
    assert len(res) == 3
    assert res[0]["title"] == "人工智能在教育领域的应用日益广泛"
    assert res[0]["url"] == "https://example.edu/paper"
    assert "个性化学习" in res[0]["snippet"]
    assert res[1]["url"] == "https://other.com/doc"


def test_extract_uddg():
    assert _extract_uddg("/l/?kh=-1&uddg=https%3A%2F%2Fexample.edu") == "https://example.edu"
    assert _extract_uddg("https://plain.com/x") is None


def test_strip_tags_and_entities():
    assert _strip_tags("<b>hello</b> &amp; world") == "hello & world"
    assert _strip_tags("<a href='x'>title</a>") == "title"


def test_ngram_sim_high_for_identical():
    a = "个性化学习能够显著提升学生的学习效率"
    assert _ngram_sim(a, a) == 1.0
    b = "机器学习方法在图像识别中表现优异"
    assert _ngram_sim(a, b) < 0.3


def test_char_ngrams_fallback_short():
    # very short input returns the whole string as a single token
    assert _char_ngrams("ab", 3) == {"ab"}


def test_check_paragraph_too_short():
    r = WebSearcher().check_paragraph("短句")
    assert r["checked"] is False
    assert r["reason"] == "too_short"


def test_check_paragraph_with_mock_session(monkeypatch):
    class FakeResp:
        status_code = 200
        text = SAMPLE_HTML

    class FakeSession:
        def get(self, url, timeout=15):
            return FakeResp()

    searcher = WebSearcher(max_results=5)
    monkeypatch.setattr(searcher, "_get_session", lambda: FakeSession())

    para = "人工智能在教育领域的应用日益广泛。许多研究机构指出，个性化学习能够显著提升学生的学习效率。"
    r = searcher.check_paragraph(para)
    assert r["checked"] is True
    assert r["found"] is True
    assert len(r["results"]) == 3
    assert r["best_similarity"] > 0.3
    assert r["query"].startswith('"')


def test_check_text_with_mock_session(monkeypatch):
    class FakeResp:
        status_code = 200
        text = SAMPLE_HTML

    class FakeSession:
        def get(self, url, timeout=15):
            return FakeResp()

    searcher = WebSearcher(max_results=5)
    monkeypatch.setattr(searcher, "_get_session", lambda: FakeSession())

    text = ("人工智能在教育领域的应用日益广泛。许多研究机构指出，个性化学习能够显著提升学生的学习效率。"
            "深度学习模型需要大量标注数据。Transformer 架构自 2017 年提出以来成为主流方法。"
            "注意力机制使得模型能够捕捉长距离依赖关系。数据隐私问题仍然是部署此类系统的主要障碍。"
            "本文提出的框架在保护隐私的同时保持了较高推荐精度。实验结果表明该方法的 F1 值达到 0.91。"
            "个性化学习能够显著提升学生的学习效率。根据 Wang 等人（2023）的研究，自适应系统可将成绩提高约 23%。"
            "该研究在三个城市的 12 所学校开展，样本量为 1840 名学生。自然语言处理技术持续快速发展。"
            "预训练语言模型显著降低了下游任务的标注成本。知识蒸馏可压缩大模型以适配边缘设备。")
    res = searcher.check_text(text, top_n=8)
    assert res["paragraphs_checked"] <= 8
    assert res["paragraphs_checked"] > 0
    assert any(c.get("found") for c in res["checks"])


def test_search_returns_empty_on_session_false(monkeypatch):
    searcher = WebSearcher()
    monkeypatch.setattr(searcher, "_get_session", lambda: False)
    assert searcher.search('"anything"') == []

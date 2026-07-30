"""Tests for the offline plagiarism checker."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hallucination_detector.plagiarism_checker import PlagiarismChecker

REF1 = (
    "人工智能在教育领域的应用日益广泛。许多研究机构指出，个性化学习能够显著提升学生的学习效率。"
    "根据 Wang 等人（2023）的研究，基于深度学习的自适应系统可以将测试成绩提高约 23%。"
    "该研究在三个城市的 12 所学校开展，样本量为 1840 名学生。"
    "深度学习模型需要大量标注数据。Transformer 架构自 2017 年提出以来，已成为自然语言处理的主流方法。"
)
REF2 = (
    "气候变化对农业生产构成了严重威胁。极端天气事件频发导致粮食减产，需要采取适应性措施。"
    "本研究表明，灌溉效率的提升可以缓解部分负面影响。"
)

PAPER_HIGH = (
    "人工智能在教育领域的应用日益广泛。许多研究机构指出，个性化学习能够显著提升学生的学习效率。"
    "根据 Wang 等人（2023）的研究，基于深度学习的自适应系统可以将测试成绩提高约 23%。"
    "该研究在三个城市的 12 所学校开展，样本量为 1840 名学生。"
    "然而，数据隐私问题仍然是部署此类系统的主要障碍。本文提出的框架在保护隐私的同时保持了较高推荐精度。"
)
PAPER_LOW = (
    "今天的午餐我吃了一碗牛肉面，味道还不错。下午去公园散步，看到很多人在放风筝。"
    "晚上准备看一部科幻电影，听说评价很好。周末打算去图书馆借几本书。"
)
PAPER_SELF = (
    "本研究提出了一种新的方法。本研究提出了一种新的方法。"
    "实验结果表明该方法有效。实验结果表明该方法有效。"
    "未来工作将进一步完善该系统。未来工作将进一步完善该系统。"
)


def test_high_overlap_detected():
    c = PlagiarismChecker()
    r = c.check(PAPER_HIGH, [REF1, REF2])
    assert r["overall"] > 0.3
    assert r["ref_count"] == 2
    assert len(r["fragments"]) > 0
    # the high-overlap reference should rank first
    assert r["per_ref"][0]["name"] == "ref1"
    assert r["per_ref"][0]["jaccard"] > r["per_ref"][1]["jaccard"]


def test_unrelated_paper_low_overlap():
    c = PlagiarismChecker()
    r = c.check(PAPER_LOW, [REF1, REF2])
    assert r["overall"] < 0.1
    assert len(r["fragments"]) == 0


def test_self_repetition_detected():
    c = PlagiarismChecker()
    r = c.check(PAPER_SELF, [])
    assert r["ref_count"] == 0
    assert r["self_rate"] > 0.3


def test_no_refs_gives_zero_overall():
    c = PlagiarismChecker()
    r = c.check(PAPER_HIGH, [])
    assert r["overall"] == 0.0
    assert r["ref_count"] == 0
    # self-rate should still be computed
    assert r["self_rate"] >= 0.0


def test_ngram_fingerprint_nonempty():
    c = PlagiarismChecker()
    grams = c.build_ngrams("人工智能在教育领域的应用日益广泛")
    assert len(grams) > 0
    assert any(g.startswith("c:") for g in grams)

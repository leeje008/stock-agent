"""문서 현행화 검증 — README가 실제 앱 탭 구성과 어긋나지 않는지 확인한다.

app.py 의 st.tabs(...) 라벨 목록을 AST로 읽어 README에 모두 문서화되어 있는지 본다.
탭을 추가하고 문서를 잊으면 이 테스트가 실패한다.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tab_labels() -> list[str]:
    """app.py 의 st.tabs([...]) 첫 인자에서 탭 라벨 리스트를 추출."""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            return [
                el.value for el in node.args[0].elts
                if isinstance(el, ast.Constant) and isinstance(el.value, str)
            ]
    raise AssertionError("app.py 에서 st.tabs 라벨을 찾지 못했습니다")


def test_tab_labels_found():
    labels = _tab_labels()
    assert len(labels) >= 13
    assert "리스크 관리" in labels
    assert "세금 계산기" in labels


@pytest.mark.parametrize("label", _tab_labels())
def test_readme_documents_each_tab(label):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert label in readme, f"README에 '{label}' 탭 설명이 없습니다"


def test_readme_tab_section_count_matches_app():
    """README의 '(Tab N)' 섹션 수가 실제 탭 수와 일치."""
    import re
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sections = re.findall(r"^### \d+\. .*\(Tab \d+\)", readme, flags=re.MULTILINE)
    assert len(sections) == len(_tab_labels())


def test_technical_guide_covers_new_subsystems():
    guide = (ROOT / "TECHNICAL_GUIDE.md").read_text(encoding="utf-8")
    for topic in ("analysis/risk.py", "analysis/tax.py", "ui/data_cache.py", "st.cache_data"):
        assert topic in guide, f"TECHNICAL_GUIDE에 {topic} 설명이 없습니다"

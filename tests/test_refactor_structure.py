"""리팩터링 구조/동작보존 검증.

- 각 탭 모듈이 import 가능하고 render(ctx) 를 노출하는지
- app.py 가 11개 탭에 대해 with tabN: tab_N.render(ctx) 를 호출하는지 (AST)
- AppContext 가 필요한 필드를 갖는지
"""
import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TAB_NUMS = list(range(1, 12))
TAB_MODULES = [f"tab_{n}" for n in TAB_NUMS] + ["tab_risk", "tab_tax"]


@pytest.mark.parametrize("name", TAB_MODULES)
def test_tab_module_exposes_render(name):
    mod = importlib.import_module(f"ui.tabs.{name}")
    assert hasattr(mod, "render")
    assert callable(mod.render)
    # render(ctx) 단일 인자
    import inspect
    params = list(inspect.signature(mod.render).parameters)
    assert params == ["ctx"]


def test_app_calls_all_tab_renders():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    called = set()
    for node in ast.walk(tree):
        # tab_N.render(ctx) 형태 탐지
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "render"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id.startswith("tab_")
        ):
            called.add(node.func.value.id)
    assert called == set(TAB_MODULES)


def test_app_constructs_context():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    ctx_construct = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AppContext"
        for node in ast.walk(tree)
    )
    assert ctx_construct


def test_appcontext_fields():
    from ui.context import AppContext
    fields = set(AppContext.__dataclass_fields__)
    required = {
        "pm", "fetcher", "market_proc", "news_fetcher", "tracker",
        "isa_mgr", "isa_account", "budget", "risk_level", "strategy",
    }
    assert required <= fields
    assert hasattr(AppContext, "load_portfolio_data")

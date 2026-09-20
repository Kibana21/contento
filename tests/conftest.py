import pytest

from src.loaders import load_brand_pack, load_profile
from src.render import fixtures as fx
from src.render.context import RenderContext


@pytest.fixture(scope="session")
def brand():
    return load_brand_pack()


@pytest.fixture(scope="session")
def profile():
    return load_profile("profiles/demo-agent")


@pytest.fixture
def festive_ctx(brand, profile):
    return RenderContext(design=fx.festive_design(), brief=fx.festive_brief(),
                         copy=fx.festive_copy(), profile=profile, brand=brand)


@pytest.fixture
def seminar_ctx(brand, profile):
    return RenderContext(design=fx.seminar_design(), brief=fx.seminar_brief(),
                         copy=fx.seminar_copy(), profile=profile, brand=brand)


@pytest.fixture(scope="session")
def rendered(tmp_path_factory):
    """Render both fixtures once; expensive, so shared across tests."""
    from src.render.renderer import render
    out = tmp_path_factory.mktemp("render")
    b, p = load_brand_pack(), load_profile("profiles/demo-agent")
    results = {}
    for name, d, br, cp in [("festive", fx.festive_design(), fx.festive_brief(), fx.festive_copy()),
                            ("seminar", fx.seminar_design(), fx.seminar_brief(), fx.seminar_copy())]:
        ctx = RenderContext(design=d, brief=br, copy=cp, profile=p, brand=b)
        results[name] = (d, render(ctx, out, name=name))
    return results

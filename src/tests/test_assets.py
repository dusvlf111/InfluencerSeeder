from core.assets import (
    guide_image_path,
    guide_image_for_selector,
    GUIDE_STEP_FOR_SELECTOR,
)


class TestGuideImages:
    def test_all_six_step_images_exist(self):
        for n in range(1, 7):
            assert guide_image_path(n).exists(), f"missing step{n}.png"

    def test_path_name_format(self):
        assert guide_image_path(3).name == "step3.png"

    def test_selector_mapping_resolves_to_existing_image(self):
        for step_id in GUIDE_STEP_FOR_SELECTOR:
            p = guide_image_for_selector(step_id)
            assert p is not None and p.exists()

    def test_unknown_selector_returns_none(self):
        assert guide_image_for_selector("does-not-exist") is None

"""Data-driven flow interpreter (260610-4).

``ConfigurableFlow`` reads the ordered ``flow_steps.csv`` (via
``storage.load_flow_steps``) and executes it phase-by-phase instead of the
hard-coded ``HashtagFlow.run``. With the **default** flow_steps it is
behavior-identical to ``HashtagFlow``: same ``_step`` status messages, same
log prefixes (``[1]``..``[6]``/``[skip]``/``[OK]``/``[grid]``), same per-step
delays, the same blocked check after the tag click, the same dedup/filter/save
path, ``source_tag``/``source_post_url`` recording, ``_collected`` increments,
``_save_state(tag, post+1)`` and back-navigation timing.

The ``collect_open`` action marks the per_tag→per_post boundary: everything in
the ``per_post`` phase runs once per collected post URL. If ``flow_steps`` is
empty or unparseable the flow falls back to the proven ``HashtagFlow``.

Registered as the default ``hashtag`` mode (and the ``keyword`` alias);
``HashtagFlow`` stays available as ``hashtag_legacy`` for regression/fallback.
"""

import logging
import time

from core.flows.base import Flow, Outcome
from core.flows.hashtag import HashtagFlow
from core.flows.steps import (
    ClickStep,
    TypeStep,
    ClickIndexStep,
    CollectPostUrls,
    PeekUsernameGate,
    NavigateToProfile,
    ExtractProfile,
    ApplyFilters,
    SaveResult,
    OpenHomeIfNeeded,
    GoBackStep,
    ScrollStep,
    keyword_tag_plan,
)

_log = logging.getLogger(__name__)


# ── Action registry: action string → Step factory ──────────────────────────────
#
# Factories take (selector_ref, param) and return a ready Step. The per-action
# orchestration (status messages, delays, Outcome handling) lives in the flow's
# phase runners below so the default flow reproduces HashtagFlow exactly.

def _click(ref, param):        return ClickStep(selector_ref=ref or "search_icon", param=param)
def _type(ref, param):         return TypeStep(selector_ref=ref or "search_input", param=param or "#{keyword}")
def _click_index(ref, param):  return ClickIndexStep(selector_ref=ref or "tag_result", param=param or "{tag_index}")
def _collect_open(ref, param): return CollectPostUrls()
def _peek_gate(ref, param):    return PeekUsernameGate()
def _navigate(ref, param):     return NavigateToProfile()
def _extract(ref, param):      return ExtractProfile()
def _filter(ref, param):       return ApplyFilters()
def _save(ref, param):         return SaveResult()
def _open_home(ref, param):    return OpenHomeIfNeeded()
def _go_back(ref, param):      return GoBackStep(selector_ref=ref, param=param)
def _scroll(ref, param):       return ScrollStep(selector_ref=ref, param=param)


ACTIONS = {
    "open_home":        _open_home,
    "click":            _click,
    "type":             _type,
    "click_index":      _click_index,
    "collect_open":     _collect_open,
    "peek_gate":        _peek_gate,
    "navigate_profile": _navigate,
    "extract":          _extract,
    "filter":           _filter,
    "save":             _save,
    "go_back":          _go_back,
    "scroll":           _scroll,
    # ``wait`` has no Step — handled inline by the runner (thread._random_delay).
    "wait":             None,
}


class ConfigurableFlow(Flow):
    """Interprets ``flow_steps.csv`` as an ordered, phased action sequence."""

    mode = "hashtag"

    # ── plan building ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_plan(rows):
        """Split enabled rows into (pre_loop, per_tag, per_post) buckets.

        Unknown actions are dropped here too (defensive — load already filters).
        Returns None when there is nothing runnable, signalling a fallback.
        """
        pre_loop, per_tag, per_post = [], [], []
        bucket = {"pre_loop": pre_loop, "per_tag": per_tag, "per_post": per_post}
        for row in rows:
            if not row.get("enabled", False):
                continue
            action = row.get("action")
            if action not in ACTIONS:
                _log.warning("ConfigurableFlow: skipping unknown action %r", action)
                continue
            phase = row.get("phase") or "per_post"
            bucket.get(phase, per_post).append(row)
        if not (pre_loop or per_tag or per_post):
            return None
        return pre_loop, per_tag, per_post

    # ── run ─────────────────────────────────────────────────────────────────────

    def run(self, ctx) -> None:
        t = ctx.thread
        try:
            from core.storage import load_flow_steps
            rows = load_flow_steps()
        except Exception as exc:
            _log.warning("ConfigurableFlow: load_flow_steps failed (%s); falling back", exc)
            return HashtagFlow().run(ctx)

        plan = self._build_plan(rows)
        if plan is None:
            _log.warning("ConfigurableFlow: empty/invalid flow_steps; falling back to HashtagFlow")
            return HashtagFlow().run(ctx)

        pre_loop, per_tag, per_post = plan
        driver = ctx.driver

        # Multi-keyword plan: each comma/newline keyword is one tag (suggestion
        # index 0). ``plan_idx`` is the loop/resume cursor; the suggestion index
        # to click lives in ``ctx.tag_index`` (kept separate per A.2).
        kw_plan = keyword_tag_plan(t.search_term, t.max_tags)

        # pre_loop steps run once before the tag loop.
        for row in pre_loop:
            ACTIONS[row["action"]](row.get("selector_ref", ""), row.get("param", "")).execute(ctx)

        # Step-number labels mirror the original "Step N/6 — ..." messages so the
        # status bar / logs stay identical for the default flow.
        n_total = 6
        n_plan = len(kw_plan)

        for plan_idx in range(t._start_tag_index, n_plan):
            if t._stop or t._collected >= t.count:
                break
            keyword, sugg_idx = kw_plan[plan_idx]
            ctx.keyword = keyword
            ctx.tag_index = sugg_idx            # suggestion to click (0 per keyword)
            ctx.plan_index = plan_idx           # plan/resume cursor (state save)
            t._current_plan_index = plan_idx

            # Always start from home page for the search icon (original inline guard).
            if "instagram.com" not in driver.current_url:
                driver.get("https://www.instagram.com/")
                time.sleep(2)

            if not self._run_per_tag(ctx, per_tag, per_post, plan_idx, n_plan):
                # _run_per_tag returns False to break the whole tag loop
                # (no suggestion / step error / blocked).
                if getattr(t, "_blocked", False):
                    return
                break

    # ── per_tag phase ─────────────────────────────────────────────────────────

    def _run_per_tag(self, ctx, per_tag, per_post, plan_idx, n_plan) -> bool:
        """Run the per_tag steps up to ``collect_open``, then the per_post loop.

        ``plan_idx`` is the keyword/plan cursor (resume + state messages);
        the suggestion index to click is ``ctx.tag_index`` (kept separate).

        Returns True to continue to the next tag, False to break the tag loop.
        """
        t, driver = ctx.thread, ctx.driver
        keyword = ctx.keyword
        step_no = 0
        n_total_label = 6   # status labels mirror the original "Step N/6" scheme

        for row in per_tag:
            action = row["action"]
            ref = row.get("selector_ref", "")
            param = row.get("param", "")

            if action == "collect_open":
                # Step 4 (collect URLs) then drive the post loop.
                t._step("Step 4/6 — Collecting post URLs from tag grid")
                ACTIONS[action](ref, param).execute(ctx)
                self._run_per_post(ctx, per_post, plan_idx, n_plan)
                return True

            step_no += 1
            step = ACTIONS[action](ref, param)

            if action == "click":
                t._step(f"Step {step_no}/{n_total_label} — Clicking search icon  "
                        f"(키워드 {plan_idx + 1}/{n_plan})")
                try:
                    step.execute(ctx)
                except Exception as exc:
                    t._log(f"  [step{step_no}-err] {exc}")
                    return False
                t._random_delay(f"step{step_no}")

            elif action == "type":
                t._step(f"Step {step_no}/{n_total_label} — '{keyword}' 검색")
                try:
                    step.execute(ctx)
                except Exception as exc:
                    t._log(f"  [step{step_no}-err] {exc}")
                    return False
                t._random_delay(f"step{step_no}")

            elif action == "click_index":
                t._step(f"Step {step_no}/{n_total_label} — '{keyword}' 검색·태그 선택")
                outcome = step.execute(ctx)
                if outcome is Outcome.NEXT_TAG:
                    t._log(f"  [stop] no tag suggestion for '{keyword}'")
                    return False
                t._random_delay(f"step{step_no}")

                # Block check + grid capture happen right after the tag click,
                # exactly as in the original flow.
                if t._is_blocked(driver):
                    t.blocked_signal.emit()
                    t._log("[blocked] 차단 감지 - 일시정지")
                    t._save_state(plan_idx, 0)
                    t._blocked = True
                    return False
                ctx.tag_grid_url = driver.current_url
                t._log(f"[grid] {ctx.tag_grid_url}")

            else:
                # open_home / wait / scroll / go_back used as a per_tag step.
                self._run_aux(ctx, action, ref, param)

        # No collect_open in this tag's per_tag phase — nothing to loop over.
        return True

    # ── per_post phase ────────────────────────────────────────────────────────

    def _run_per_post(self, ctx, per_post, plan_idx, n_plan) -> None:
        t, driver = ctx.thread, ctx.driver
        tag_grid_url = ctx.tag_grid_url
        post_urls = ctx.post_urls

        # Resume support: skip already-processed posts within the resumed tag.
        resume_post_start = (
            t._start_post_index if plan_idx == t._start_tag_index else 0
        )

        for post_idx, post_url in enumerate(post_urls):
            if t._stop or t._collected >= t.count:
                break
            if post_idx < resume_post_start:
                continue

            ctx.post_index = post_idx
            ctx.post_url = post_url

            # Step 4 (navigate to post) — mirrors the original pre-peek navigate.
            t._step(f"Step 4/6 — Opening post {post_idx + 1}/{len(post_urls)}"
                    f"  (키워드 {plan_idx + 1}/{n_plan})")
            t._log(f"[4] {post_url}")
            try:
                driver.get(post_url)
            except Exception as exc:
                t._log(f"  [4-err] {exc}")
                continue
            t._random_delay("step4")

            if self._run_post_steps(ctx, per_post, 6, tag_grid_url) is Outcome.SKIP_POST:
                continue

    def _run_post_steps(self, ctx, per_post, n_total, tag_grid_url) -> Outcome:
        """Execute the per_post action steps for the current post.

        Returns SKIP_POST when a step aborted the post (the caller then
        ``continue``s); CONTINUE when the post completed and back-nav ran.
        """
        t, driver = ctx.thread, ctx.driver

        for row in per_post:
            action = row["action"]
            ref = row.get("selector_ref", "")
            param = row.get("param", "")
            step = ACTIONS[action] if ACTIONS[action] is None else ACTIONS[action](ref, param)

            if action == "peek_gate":
                if step.execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    return Outcome.SKIP_POST

            elif action == "navigate_profile":
                t._step("Step 5/6 — Navigating to profile")
                if step.execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.5)
                    return Outcome.SKIP_POST
                t._random_delay("step5")

            elif action == "extract":
                t._step("Step 6/6 — Saving profile data")
                if step.execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.5)
                    return Outcome.SKIP_POST

                # Dedup gate (covers excluded + already-collected + seen) —
                # original places this immediately after extract.
                username = ctx.profile_info["username"]
                if t._should_skip(username):
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    return Outcome.SKIP_POST

            elif action == "filter":
                if step.execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    return Outcome.SKIP_POST

            elif action == "save":
                if step.execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    return Outcome.SKIP_POST
                t._random_delay("step6")

            elif action == "go_back":
                t._step("Returning to tag grid...")
                step.execute(ctx)
                t._random_delay("back")

            else:
                # open_home / wait / scroll used inside the post loop.
                self._run_aux(ctx, action, ref, param)

        return Outcome.CONTINUE

    # ── auxiliary actions (open_home / wait / scroll / go_back outside main path) ─

    def _run_aux(self, ctx, action, ref, param) -> None:
        t = ctx.thread
        if action == "wait":
            t._random_delay(param or "step1")
            return
        factory = ACTIONS.get(action)
        if factory is None:
            return
        factory(ref, param).execute(ctx)

"""Hashtag collection flow.

Drives Instagram's tag search → grid → post → profile pipeline using the
reusable Steps in ``core.flows.steps`` and the capability methods on
``ctx.thread`` (ScraperThread). Registered as the default flow (and the
``keyword`` alias) in ``core.flows.__init__``.

Behavior is identical to the original ``ScraperThread.run()`` post-login loop:
the same log prefixes (``[1]``..``[6]``/``[skip]``/``[OK]``/``[grid]``), signal
emit order, dedup/filter/save logic, ``source_tag``/``source_post_url``
recording, ``_collected`` increments and ``_save_state(tag, post+1)``.
"""

import time

from core.flows.base import Flow, Outcome
from core.flows.steps import (
    ClickSearchIcon,
    TypeSearch,
    ClickTagSuggestion,
    CollectPostUrls,
    PeekUsernameGate,
    NavigateToProfile,
    ExtractProfile,
    ApplyFilters,
    SaveResult,
    keyword_tag_plan,
)


class HashtagFlow(Flow):
    mode = "hashtag"

    def run(self, ctx) -> None:
        t = ctx.thread
        driver = ctx.driver

        # Multi-keyword plan (Fix-1): each comma/newline keyword = one tag
        # (suggestion index 0). ``plan_idx`` is the loop/resume cursor; the
        # suggestion index to click is ``ctx.tag_index`` (kept separate).
        kw_plan = keyword_tag_plan(t.search_term, t.max_tags)
        n_plan = len(kw_plan)

        for plan_idx in range(t._start_tag_index, n_plan):
            if t._stop or t._collected >= t.count:
                break
            keyword, sugg_idx = kw_plan[plan_idx]
            ctx.keyword = keyword
            ctx.tag_index = sugg_idx
            ctx.plan_index = plan_idx
            t._current_plan_index = plan_idx

            # Always start from home page for search icon.
            if "instagram.com" not in driver.current_url:
                driver.get("https://www.instagram.com/")
                time.sleep(2)

            # --- Step 1 ---
            t._step(
                f"Step 1/6 — Clicking search icon  (키워드 {plan_idx + 1}/{n_plan})"
            )
            try:
                ClickSearchIcon().execute(ctx)
            except Exception as exc:
                t._log(f"  [step1-err] {exc}")
                break
            t._random_delay("step1")

            # --- Step 2 ---
            t._step(f"Step 2/6 — '{keyword}' 검색")
            try:
                TypeSearch().execute(ctx)
            except Exception as exc:
                t._log(f"  [step2-err] {exc}")
                break
            t._random_delay("step2")

            # --- Step 3 ---
            t._step(f"Step 3/6 — '{keyword}' 검색·태그 선택")
            outcome = ClickTagSuggestion().execute(ctx)
            if outcome is Outcome.NEXT_TAG:
                t._log(f"  [stop] no tag suggestion for '{keyword}'")
                break
            t._random_delay("step3")

            if t._is_blocked(driver):
                t.blocked_signal.emit()
                t._log("[blocked] 차단 감지 - 일시정지")
                t._save_state(plan_idx, 0)
                t._blocked = True
                return

            tag_grid_url = driver.current_url
            ctx.tag_grid_url = tag_grid_url
            t._log(f"[grid] {tag_grid_url}")

            # --- Step 4 (collect URLs) ---
            t._step("Step 4/6 — Collecting post URLs from tag grid")
            CollectPostUrls().execute(ctx)
            post_urls = ctx.post_urls

            # Resume support: skip already-processed posts within the
            # resumed tag only (§7).
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

                # --- Step 4 (navigate to post) ---
                t._step(
                    f"Step 4/6 — Opening post {post_idx + 1}/{len(post_urls)}"
                    f"  (키워드 {plan_idx + 1}/{n_plan})"
                )
                t._log(f"[4] {post_url}")
                try:
                    driver.get(post_url)
                except Exception as exc:
                    t._log(f"  [4-err] {exc}")
                    continue
                t._random_delay("step4")

                # --- Early dedup gate (§6): peek username before Step5 ---
                if PeekUsernameGate().execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    continue

                # --- Step 5 ---
                t._step("Step 5/6 — Navigating to profile")
                if NavigateToProfile().execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.5)
                    continue
                t._random_delay("step5")

                # --- Step 6 ---
                t._step("Step 6/6 — Saving profile data")
                if ExtractProfile().execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.5)
                    continue

                username = ctx.profile_info["username"]

                # Dedup gate (covers excluded + already-collected + seen).
                if t._should_skip(username):
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    continue

                # Follower-range filter (filter-failed usernames marked seen).
                if ApplyFilters().execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    continue

                # --- Save ---
                if SaveResult().execute(ctx) is Outcome.SKIP_POST:
                    driver.get(tag_grid_url)
                    time.sleep(1.0)
                    continue

                t._random_delay("step6")

                # Back to tag grid.
                t._step("Returning to tag grid...")
                driver.get(tag_grid_url)
                t._random_delay("back")

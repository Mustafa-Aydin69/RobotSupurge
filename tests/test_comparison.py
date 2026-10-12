"""Karşılaştırma çekirdeği (comparison.py) testleri."""

import json
import math
import unittest
from pathlib import Path

from comparison import (
    AGENT_KEYS, ComparisonJob, ComparisonSettings, RunResult, common_dirt_draws, common_dirt_rng,
    coverage_steps, mean_clean_ratio, run_pair, summarize, summarize_coverage,
)

REFERENCE = json.loads((Path(__file__).parent / "data" / "comparison_reference.json").read_text(encoding="utf-8"))


class EquivalenceWithPhase4ToolTests(unittest.TestCase):
    """Faz 4 aracının kaydedilmiş çıktılarıyla birebir eşdeğerlik."""

    def test_coverage_matches_reference(self):
        for case in REFERENCE["coverage"]:
            with self.subTest(**{k: case[k] for k in ("agent", "rows", "cols", "seed")}):
                self.assertEqual(coverage_steps(case["agent"], case["rows"], case["cols"], case["seed"]),
                                 case["value"])

    def test_clean_ratio_matches_reference(self):
        for case in REFERENCE["clean_ratio"]:
            with self.subTest(**{k: case[k] for k in ("agent", "rows", "cols", "seed", "mode")}):
                value = mean_clean_ratio(case["agent"], case["rows"], case["cols"], case["seed"],
                                         steps=case["steps"], dirt_every=case["dirt_every"], mode=case["mode"])
                self.assertEqual(value, case["value"])

    def test_reference_covers_all_agents_and_modes(self):
        self.assertEqual({c["agent"] for c in REFERENCE["clean_ratio"]}, set(AGENT_KEYS))
        self.assertEqual({c["mode"] for c in REFERENCE["clean_ratio"]}, {"common", "independent"})


class CommonDirtReproducibilityTests(unittest.TestCase):
    def test_common_draws_are_the_same_for_every_agent(self):
        """Ortak biçimde deneme dizisi yalnızca seed'e bağlıdır, ajana değil."""
        sequences = []
        for _agent in AGENT_KEYS:
            rng = common_dirt_rng(7)
            sequences.append([common_dirt_draws(rng, 9) for _ in range(30)])
        self.assertTrue(all(seq == sequences[0] for seq in sequences))

    def test_common_mode_is_reproducible(self):
        settings = ComparisonSettings(rows=3, cols=4, seed_count=1, steps=300, dirt_mode="common")
        a = run_pair_to_end("goal", 3, settings)
        b = run_pair_to_end("goal", 3, settings)
        self.assertEqual(a, b)


def run_pair_to_end(agent_type, seed, settings):
    generator = run_pair(agent_type, seed, settings)
    while True:
        try:
            next(generator)
        except StopIteration as stop:
            return stop.value


class CoverageSummaryTests(unittest.TestCase):
    def test_all_completed(self):
        s = summarize_coverage([10, 20, 30, 40], cap=100)
        self.assertEqual((s.completed, s.incomplete, s.mean, s.median, s.worst), (4, 0, 25, 25, 40))
        self.assertIsNone(s.mean_lower_bound)

    def test_incomplete_runs_are_not_treated_as_completed(self):
        s = summarize_coverage([10, None, 30, None, 50], cap=100)
        self.assertEqual((s.completed, s.incomplete), (3, 2))
        self.assertIsNone(s.mean, "Tamamlanmayan koşu varken ortalama verilmez")
        self.assertEqual(s.mean_lower_bound, (10 + 30 + 50 + 100 + 100) / 5)   # alt sınır
        self.assertEqual(s.median, 50)          # sıralı: 10, 30, 50, ∞, ∞
        self.assertIsNone(s.worst, "En kötü değer sınırdan büyüktür, bilinmez")

    def test_median_unknown_when_majority_incomplete(self):
        s = summarize_coverage([10, None, None], cap=100)
        self.assertIsNone(s.median)

    def test_run_that_does_not_cover_within_cap_is_incomplete(self):
        settings = ComparisonSettings(rows=6, cols=6, seed_count=1, steps=20)
        result = run_pair_to_end("reflex", 0, settings)
        self.assertIsNone(result.coverage_step)
        summary = summarize([result], settings)[0]
        self.assertEqual((summary.coverage.completed, summary.coverage.incomplete), (0, 1))


class MovesPerCleanTests(unittest.TestCase):
    def test_zero_cleans_is_undefined_not_division_error(self):
        result = RunResult("reflex", 0, 5, 1.0, moves=10, cleans=0)
        self.assertIsNone(result.moves_per_clean)

    def test_summary_counts_undefined_runs(self):
        settings = ComparisonSettings(seed_count=3)
        results = [RunResult("model", 0, 5, 0.5, 10, 0), RunResult("model", 1, 6, 0.6, 12, 4),
                   RunResult("model", 2, 7, 0.7, 9, 3)]
        summary = summarize(results, settings)[0]
        self.assertEqual(summary.moves_per_clean_undefined, 1)
        self.assertEqual(summary.moves_per_clean_mean, (3 + 3) / 2)

    def test_all_undefined_gives_none(self):
        settings = ComparisonSettings(seed_count=2)
        results = [RunResult("goal", 0, 5, 1.0, 10, 0), RunResult("goal", 1, 5, 1.0, 10, 0)]
        self.assertIsNone(summarize(results, settings)[0].moves_per_clean_mean)

    def test_dirt_free_runs_can_have_zero_cleans(self):
        """Gerçek bir koşuda sıfır temizlik: kirlenme kapalı ve başlangıçta her oda temiz."""
        from simulation import Simulation
        seed = next(s for s in range(200)
                    if all(st.value == "Clean" for st in Simulation(seed=s, rows=1, cols=2).environment.statuses().values()))
        settings = ComparisonSettings(rows=1, cols=2, seed_start=seed, seed_count=1, steps=50,
                                      probability=0.0)
        result = run_pair_to_end("reflex", seed, settings)
        self.assertEqual(result.cleans, 0)
        self.assertIsNone(result.moves_per_clean)


class StatisticsTests(unittest.TestCase):
    def test_stdev_is_none_for_single_run(self):
        settings = ComparisonSettings(seed_count=1)
        summary = summarize([RunResult("reflex", 0, 5, 0.5, 4, 2)], settings)[0]
        self.assertIsNone(summary.clean_ratio_stdev)

    def test_stdev_for_multiple_runs(self):
        settings = ComparisonSettings(seed_count=2)
        summary = summarize([RunResult("reflex", 0, 5, 0.4, 4, 2), RunResult("reflex", 1, 5, 0.6, 4, 2)],
                            settings)[0]
        self.assertAlmostEqual(summary.clean_ratio_stdev, math.sqrt(0.02))


class ComparisonJobTests(unittest.TestCase):
    def small_settings(self, **overrides):
        values = dict(rows=3, cols=3, seed_start=0, seed_count=3, steps=200, dirt_every=4, dirt_mode="common")
        values.update(overrides)
        return ComparisonSettings(**values)

    def test_job_runs_all_agents_and_seeds(self):
        job = ComparisonJob(self.small_settings())
        while not job.advance(0.01):
            pass
        self.assertEqual((job.done, job.total), (9, 9))
        self.assertEqual([s.agent_type for s in job.summary()], list(AGENT_KEYS))

    def test_job_matches_blocking_measurements(self):
        settings = self.small_settings(steps=300)
        job = ComparisonJob(settings)
        while not job.advance(0.005):
            pass
        for result in job.results:
            self.assertEqual(result.coverage_step,
                             coverage_steps(result.agent_type, 3, 3, result.seed, cap=300))
            self.assertEqual(result.clean_ratio,
                             mean_clean_ratio(result.agent_type, 3, 3, result.seed, steps=300, mode="common"))

    def test_slices_respect_time_budget(self):
        job = ComparisonJob(self.small_settings(rows=6, cols=6, steps=3000, seed_count=1))
        while not job.advance(0.015):
            pass
        # Tek bir parça, bütçeyi en fazla bir kontrol aralığı (50 adım) kadar aşabilir.
        self.assertLess(job.longest_slice, 0.1)

    def test_cancel_stops_and_gives_no_summary(self):
        job = ComparisonJob(self.small_settings(seed_count=5, steps=1000))
        job.advance(0.005)
        done_before = job.done
        job.cancel()
        self.assertFalse(job.advance(1.0))
        self.assertEqual(job.done, done_before, "İptalden sonra yeni iş yapılmamalı")
        self.assertFalse(job.finished)
        self.assertIsNone(job.summary(), "Kısmi sonuç tamamlanmış gibi sunulmamalı")

    def test_restart_after_cancel_gives_same_result_as_uninterrupted(self):
        settings = self.small_settings()
        first = ComparisonJob(settings)
        first.advance(0.002)
        first.cancel()
        second = ComparisonJob(settings)
        while not second.advance(0.01):
            pass
        third = ComparisonJob(settings)
        while not third.advance(0.05):
            pass
        self.assertEqual(second.summary(), third.summary())

    def test_invalid_settings_are_rejected(self):
        for overrides in ({"rows": 1, "cols": 1}, {"seed_count": 0}, {"steps": 0}, {"dirt_every": 0},
                          {"dirt_mode": "x"}):
            with self.subTest(**overrides), self.assertRaises(ValueError):
                ComparisonJob(self.small_settings(**overrides))

    def test_different_grid_sizes(self):
        for rows, cols in [(1, 2), (2, 1), (1, 6), (5, 3)]:
            job = ComparisonJob(self.small_settings(rows=rows, cols=cols, seed_count=2, steps=150))
            while not job.advance(0.01):
                pass
            with self.subTest(grid=(rows, cols)):
                self.assertEqual(len(job.summary()), 3)


if __name__ == "__main__":
    unittest.main()

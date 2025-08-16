"""
Performance benchmark tests for Accuracy++ solver
"""

import os
import time
import random
import statistics
import pytest
from typing import List, Dict, Any

from app.services.solver_ilp import (
    solve_assignment, choose_layout_and_mapping,
    default_weight_fn, default_compat_fn
)


@pytest.mark.performance
class TestPerformanceSolver:
    """Performance benchmarks for ILP solver"""
    
    def setup_method(self):
        """Setup performance test parameters from environment"""
        self.perf_strict = os.getenv("PERF_STRICT", "false").lower() == "true"
        self.mean_threshold_ms = int(os.getenv("PERF_SOLVER_MEAN_MS", "120"))
        self.p95_threshold_ms = int(os.getenv("PERF_SOLVER_P95_MS", "300"))
        self.total_threshold_s = float(os.getenv("PERF_TOTAL_TIME_S", "15"))
        
        # Seed for reproducibility
        random.seed(42)
    
    def _generate_synthetic_slide_spec(self, slide_num: int) -> List[Dict[str, Any]]:
        """Generate synthetic content for a slide"""
        content_items = [
            {"id": f"slide{slide_num}_title", "type": "TITLE", "required": True}
        ]
        
        # Add 1-3 additional content items
        num_items = random.randint(1, 3)
        
        if num_items >= 1:
            content_items.append({
                "id": f"slide{slide_num}_body",
                "type": "BODY",
                "required": True,
                "size_hint": random.choice(["S", "M", "L"])
            })
        
        if num_items >= 2:
            content_type = random.choice(["IMAGE", "TABLE", "CHART"])
            content_items.append({
                "id": f"slide{slide_num}_{content_type.lower()}",
                "type": content_type,
                "required": random.choice([True, False])
            })
        
        if num_items >= 3:
            content_items.append({
                "id": f"slide{slide_num}_extra",
                "type": "TEXTBOX",
                "required": False
            })
        
        return content_items
    
    def _generate_synthetic_layouts(self, num_layouts: int = 5) -> List[Dict[str, Any]]:
        """Generate synthetic layouts with shapes"""
        layouts = []
        
        for i in range(num_layouts):
            shapes = []
            num_shapes = random.randint(6, 10)
            
            # Always include title
            shapes.append({
                "sid": f"layout{i}_title",
                "ph_type": "TITLE",
                "place_ok": True,
                "priority": 1,
                "safety_penalty": 0.0,
                "bbox_px": {"left": 100, "top": 50, "width": 800, "height": 100},
                "slide_width": 1920,
                "slide_height": 1080
            })
            
            # Add various shape types
            for j in range(1, num_shapes):
                shape_type = random.choice(["BODY", "TEXTBOX", "PICTURE", "TABLE", "CHART", "CONTENT"])
                shapes.append({
                    "sid": f"layout{i}_shape{j}",
                    "ph_type": shape_type,
                    "place_ok": random.random() > 0.1,  # 90% placeable
                    "priority": random.randint(1, 5),
                    "safety_penalty": random.random() * 0.3 if random.random() < 0.2 else 0.0,
                    "bbox_px": {
                        "left": random.randint(50, 500),
                        "top": random.randint(150, 400),
                        "width": random.randint(300, 800),
                        "height": random.randint(200, 500)
                    },
                    "slide_width": 1920,
                    "slide_height": 1080
                })
            
            layouts.append({
                "name": f"Layout {i}",
                "layout_id": i,
                "shapes": shapes,
                "archetype_hint": random.choice(["TitleSlide", "TitleBody", "TwoColumn", None])
            })
        
        return layouts
    
    def test_solver_performance_20_slides(self):
        """Benchmark solver performance on 20-slide presentation"""
        print("\n" + "=" * 60)
        print(" PERFORMANCE BENCHMARK: 20-SLIDE PRESENTATION")
        print("=" * 60)
        
        # Generate synthetic data
        layouts = self._generate_synthetic_layouts(5)
        
        # Track timing for each slide
        solve_times_ms = []
        total_start = time.perf_counter()
        
        for slide_num in range(1, 21):
            content_spec = self._generate_synthetic_slide_spec(slide_num)
            
            # Time the solver
            start = time.perf_counter()
            layout, mapping = choose_layout_and_mapping(layouts, content_spec)
            elapsed = time.perf_counter() - start
            
            solve_time_ms = elapsed * 1000
            solve_times_ms.append(solve_time_ms)
            
            print(f"  Slide {slide_num:2d}: {solve_time_ms:6.2f}ms - "
                  f"{len(content_spec)} items -> {len(mapping)} mapped")
        
        total_elapsed = time.perf_counter() - total_start
        
        # Calculate statistics
        mean_ms = statistics.mean(solve_times_ms)
        p95_ms = statistics.quantiles(solve_times_ms, n=20)[18]  # 95th percentile
        max_ms = max(solve_times_ms)
        min_ms = min(solve_times_ms)
        
        # Print summary
        print("\n" + "-" * 40)
        print(" PERFORMANCE SUMMARY")
        print("-" * 40)
        print(f"Solver mean: {mean_ms:.0f}ms | p95: {p95_ms:.0f}ms | "
              f"total: {total_elapsed:.1f}s (20 slides)")
        print(f"Range: {min_ms:.0f}ms - {max_ms:.0f}ms")
        print(f"Thresholds: mean<={self.mean_threshold_ms}ms, "
              f"p95<={self.p95_threshold_ms}ms, total<={self.total_threshold_s}s")
        
        # Check against thresholds
        if self.perf_strict:
            print("\n🔒 STRICT MODE: Enforcing performance thresholds")
            assert mean_ms <= self.mean_threshold_ms, \
                f"Mean solve time {mean_ms:.0f}ms exceeds threshold {self.mean_threshold_ms}ms"
            assert p95_ms <= self.p95_threshold_ms, \
                f"P95 solve time {p95_ms:.0f}ms exceeds threshold {self.p95_threshold_ms}ms"
            assert total_elapsed <= self.total_threshold_s, \
                f"Total time {total_elapsed:.1f}s exceeds threshold {self.total_threshold_s}s"
            print("✅ All performance thresholds met")
        else:
            print("\n📊 NON-STRICT MODE: Logging metrics only")
            
            # Provide feedback even in non-strict mode
            if mean_ms <= self.mean_threshold_ms:
                print(f"✅ Mean time OK: {mean_ms:.0f}ms <= {self.mean_threshold_ms}ms")
            else:
                print(f"⚠️  Mean time high: {mean_ms:.0f}ms > {self.mean_threshold_ms}ms")
            
            if p95_ms <= self.p95_threshold_ms:
                print(f"✅ P95 time OK: {p95_ms:.0f}ms <= {self.p95_threshold_ms}ms")
            else:
                print(f"⚠️  P95 time high: {p95_ms:.0f}ms > {self.p95_threshold_ms}ms")
            
            if total_elapsed <= self.total_threshold_s:
                print(f"✅ Total time OK: {total_elapsed:.1f}s <= {self.total_threshold_s}s")
            else:
                print(f"⚠️  Total time high: {total_elapsed:.1f}s > {self.total_threshold_s}s")
    
    def test_solver_scaling_with_complexity(self):
        """Test how solver scales with increasing complexity"""
        print("\n" + "=" * 60)
        print(" SCALING TEST: COMPLEXITY VS PERFORMANCE")
        print("=" * 60)
        
        complexities = [
            (2, 4, "Simple"),    # 2 content, 4 shapes
            (4, 8, "Medium"),    # 4 content, 8 shapes
            (6, 12, "Complex"),  # 6 content, 12 shapes
            (8, 16, "Heavy")     # 8 content, 16 shapes
        ]
        
        for num_content, num_shapes, label in complexities:
            # Generate test data
            content_items = [
                {
                    "id": f"content_{i}",
                    "type": random.choice(["TITLE", "BODY", "IMAGE", "TABLE"]),
                    "required": i < num_content // 2  # Half required
                }
                for i in range(num_content)
            ]
            
            shape_items = [
                {
                    "sid": f"shape_{i}",
                    "ph_type": random.choice(["TITLE", "BODY", "TEXTBOX", "PICTURE", "TABLE"]),
                    "place_ok": True,
                    "priority": random.randint(1, 5),
                    "safety_penalty": 0.0
                }
                for i in range(num_shapes)
            ]
            
            # Time the solver
            start = time.perf_counter()
            mapping = solve_assignment(
                content_items, shape_items,
                default_weight_fn, default_compat_fn
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            print(f"  {label:8s}: {num_content} content × {num_shapes} shapes = "
                  f"{elapsed_ms:6.2f}ms ({len(mapping)} mapped)")
        
        print("\n✅ Scaling test completed")
    
    def test_cache_and_warmup_effect(self):
        """Test the effect of warmup on solver performance"""
        print("\n" + "=" * 60)
        print(" WARMUP EFFECT TEST")
        print("=" * 60)
        
        # Fixed test case
        content_items = [
            {"id": "title", "type": "TITLE", "required": True},
            {"id": "body", "type": "BODY", "required": True},
            {"id": "image", "type": "IMAGE", "required": False}
        ]
        
        shape_items = [
            {"sid": f"s{i}", "ph_type": t, "place_ok": True}
            for i, t in enumerate(["TITLE", "BODY", "BODY", "PICTURE", "TEXTBOX"])
        ]
        
        times = []
        
        # Run multiple iterations
        for i in range(10):
            start = time.perf_counter()
            mapping = solve_assignment(
                content_items, shape_items,
                default_weight_fn, default_compat_fn
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            
            if i == 0:
                print(f"  First run:  {elapsed_ms:6.2f}ms (cold)")
            elif i == 9:
                print(f"  Last run:   {elapsed_ms:6.2f}ms (warm)")
        
        # Compare first vs rest
        first_time = times[0]
        avg_warm = statistics.mean(times[1:])
        speedup = first_time / avg_warm if avg_warm > 0 else 1.0
        
        print(f"\n  Cold start: {first_time:.2f}ms")
        print(f"  Warm avg:   {avg_warm:.2f}ms")
        print(f"  Speedup:    {speedup:.2f}x")
        
        print("\n✅ Warmup test completed")
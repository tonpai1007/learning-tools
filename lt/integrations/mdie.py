"""
MDIE Physics & Structural Solver Integration for Learning Tools.
Allows the learning-tools Tutor, CLI, and Web service to query MDIE's deterministic physics engines:
- 3D Direct Stiffness FEA (space truss towers, cantilever girders, 3D chair frame)
- Column Buckling Verification (Euler elastic and Johnson inelastic equations)
- Frame and Chair Structural Equilibrium Verification (ANSI/BIFMA proof loads)

Dual-mode:
- REST API: Calls MDIE web service at http://127.0.0.1:8000 when running.
- Direct Library Fallback: Imports mdie.physics.* directly when running standalone or offline.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MDIE_DIR = Path(os.environ.get("MDIE_DIR", r"c:\codework\computational-machine-design")).resolve()
DEFAULT_MDIE_URL = os.environ.get("MDIE_URL", "http://127.0.0.1:8000")


def ensure_mdie_imported():
    """Ensure computational-machine-design is on sys.path for direct physics library import."""
    if MDIE_DIR.exists() and str(MDIE_DIR) not in sys.path:
        sys.path.insert(0, str(MDIE_DIR))


class MDIEPhysicsClient:
    """
    Client connecting learning-tools to the MDIE computational engineering physics solver.
    """

    def __init__(self, base_url: str = DEFAULT_MDIE_URL, mdie_dir: Optional[Path] = None):
        self.base_url = base_url.rstrip("/")
        self.mdie_dir = mdie_dir or MDIE_DIR
        ensure_mdie_imported()

    def is_online(self, timeout: float = 0.8) -> bool:
        """Check if the MDIE FastAPI service (port 8000) is running."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/health",
                headers={"User-Agent": "LearningTools-Tutor/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def solve_3d_fea(self, preset: str = "chair") -> Dict[str, Any]:
        """
        Solve a 3D FEA direct stiffness frame model (presets: 'chair', 'tower', 'girder').
        """
        # 1. Try remote API if server is online
        if self.is_online():
            try:
                req = urllib.request.Request(f"{self.base_url}/api/fea3d/preset/{preset}")
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.warning(f"MDIE FEA API call failed ({e}); using direct library fallback.")

        # 2. Direct library execution
        from mdie.physics.fea_3d import (
            build_chair_3d_fea_model,
            build_space_truss_tower_model,
            build_cantilever_space_frame_model
        )
        if preset == "chair":
            from mdie.core.frame_model import FrameDesignModel
            solver = build_chair_3d_fea_model(FrameDesignModel())
        elif preset == "tower":
            solver = build_space_truss_tower_model()
        elif preset == "girder":
            solver = build_cantilever_space_frame_model()
        else:
            raise ValueError(f"Unknown FEA preset: {preset}")

        return solver.solve()

    def calculate_column_buckling(
        self,
        load_n: float,
        length_mm: float,
        d_outer_mm: float,
        d_inner_mm: float = 0.0,
        E_gpa: float = 205.0,
        K: float = 1.0,
        yield_mpa: float = 370.0
    ) -> Dict[str, Any]:
        """
        Perform deterministic Euler-Johnson column buckling calculation.
        """
        E_mpa = E_gpa * 1000.0
        A = (math.pi / 4.0) * (d_outer_mm**2 - d_inner_mm**2)
        I = (math.pi / 64.0) * (d_outer_mm**4 - d_inner_mm**4)
        r = math.sqrt(I / A) if A > 0 else 0.0

        slenderness = (K * length_mm) / r if r > 0 else 0.0
        critical_slenderness = math.sqrt((2.0 * math.pi**2 * E_mpa) / yield_mpa)

        euler_p_cr = (math.pi**2 * E_mpa * I) / ((K * length_mm)**2) if (K * length_mm) > 0 else 0.0

        if slenderness >= critical_slenderness:
            regime = "Euler (Elastic Buckling)"
            p_cr = euler_p_cr
        else:
            regime = "Johnson (Inelastic Buckling)"
            johnson_term = (yield_mpa * (slenderness**2)) / (4.0 * math.pi**2 * E_mpa)
            p_cr = A * yield_mpa * max(0.0, (1.0 - johnson_term))

        sf_buckling = p_cr / load_n if load_n > 0 else float("inf")
        compressive_stress = load_n / A if A > 0 else 0.0
        sf_yield = yield_mpa / compressive_stress if compressive_stress > 0 else float("inf")

        return {
            "load_n": load_n,
            "length_mm": length_mm,
            "d_outer_mm": d_outer_mm,
            "d_inner_mm": d_inner_mm,
            "area_mm2": round(A, 2),
            "moment_inertia_mm4": round(I, 2),
            "radius_gyration_mm": round(r, 2),
            "slenderness_ratio": round(slenderness, 2),
            "critical_slenderness": round(critical_slenderness, 2),
            "regime": regime,
            "critical_buckling_load_n": round(p_cr, 1),
            "critical_buckling_load_kn": round(p_cr / 1000.0, 2),
            "buckling_safety_factor": round(sf_buckling, 2),
            "compressive_stress_mpa": round(compressive_stress, 2),
            "yield_safety_factor": round(sf_yield, 2),
            "passed": bool(sf_buckling >= 1.5 and sf_yield >= 1.5)
        }

    def query_physics_hook(self, question: str) -> Optional[str]:
        """
        Analyze a query to see if it requires verified physics solving.
        If matched, executes deterministic calculations and formats a Markdown context block.
        """
        q_lower = question.lower()

        # 1. 3D FEA queries (chair, truss, space frame)
        if any(w in q_lower for w in ["fea", "space frame", "truss", "tower", "cantilever"]) or ("chair" in q_lower and any(w in q_lower for w in ["deflection", "stress", "safety factor", "frame"])):
            preset = "chair"
            if "tower" in q_lower or "truss" in q_lower:
                preset = "tower"
            elif "cantilever" in q_lower or "girder" in q_lower:
                preset = "girder"

            try:
                res = self.solve_3d_fea(preset)
                return (
                    f"[VERIFIED MDIE 3D DIRECT STIFFNESS FEA ({preset.upper()})]:\n"
                    f"- Structure: {res.get('structure_name')}\n"
                    f"- Active DOFs: {res.get('num_nodes', 0) * 6} ({res.get('num_nodes', 0)} nodes, {res.get('num_members', 0)} 3D beam members)\n"
                    f"- Max Displacement: {res.get('max_displacement_mm', 0):.2f} mm\n"
                    f"- Max Von Mises Stress: {res.get('max_von_mises_mpa', 0):.1f} MPa\n"
                    f"- Minimum Safety Factor: {res.get('min_safety_factor', 0):.2f}\n"
                    f"- Structural Verdict: {'PASS (meets code safety thresholds)' if res.get('passed') else 'FAIL (excessive deflection or stress)'}"
                )
            except Exception as e:
                logger.warning(f"FEA query failed: {e}")

        # 2. Buckling calculation queries
        if any(w in q_lower for w in ["buckling", "euler", "column", "slenderness"]) and any(c.isdigit() for c in q_lower):
            # Attempt to extract dimensions
            load_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:n|newtons?|kn)', q_lower)
            load_n = 1300.0
            if load_match:
                val = float(load_match.group(1))
                load_n = val * 1000.0 if "kn" in load_match.group(0) else val

            len_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm|m\b|cm)', q_lower)
            len_mm = 450.0
            if len_match:
                val = float(len_match.group(1))
                if "cm" in len_match.group(0):
                    len_mm = val * 10.0
                elif "m" in len_match.group(0) and "mm" not in len_match.group(0):
                    len_mm = val * 1000.0
                else:
                    len_mm = val

            dia_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:dia|diameter|tube|leg)', q_lower)
            dia_mm = 28.0
            if dia_match:
                dia_mm = float(dia_match.group(1))

            try:
                b_res = self.calculate_column_buckling(
                    load_n=load_n,
                    length_mm=len_mm,
                    d_outer_mm=dia_mm,
                    d_inner_mm=max(0.0, dia_mm - 5.0)  # assume 2.5mm wall tube
                )
                return (
                    f"[VERIFIED MDIE DETERMINISTIC BUCKLING SOLVER]:\n"
                    f"- Applied Axial Load: {b_res['load_n']:.1f} N\n"
                    f"- Column Dimensions: L = {b_res['length_mm']:.1f} mm, Tube OD = {b_res['d_outer_mm']:.1f} mm\n"
                    f"- Slenderness Ratio (L/r): {b_res['slenderness_ratio']:.2f} (Critical Transition: {b_res['critical_slenderness']:.2f})\n"
                    f"- Governing Regime: {b_res['regime']}\n"
                    f"- Critical Buckling Load (P_cr): {b_res['critical_buckling_load_kn']:.2f} kN ({b_res['critical_buckling_load_n']:.0f} N)\n"
                    f"- Buckling Safety Factor: {b_res['buckling_safety_factor']:.2f}\n"
                    f"- Compressive Stress: {b_res['compressive_stress_mpa']:.1f} MPa (Yield SF: {b_res['yield_safety_factor']:.2f})\n"
                    f"- Status: {'SAFE / PASS' if b_res['passed'] else 'BUCKLING RISK / FAIL'}"
                )
            except Exception as e:
                logger.warning(f"Buckling calculation failed: {e}")

        return None

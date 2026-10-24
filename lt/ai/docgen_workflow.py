"""
LangGraph Multi-Agent Document Generation Workflow (Learning-Tools Edition)
Orchestrates: Research → Outline → Writer → Fact Checker → Editor → Renderer → QA Validator
All numerical values come from deterministic data sources; agents only author narrative text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, Optional

from langgraph.graph import StateGraph, END

from lt.reporting.diagrams import generate_all_diagrams


# =============================================================================
# State Definition
# =============================================================================

class DocGenState(TypedDict):
    """State passed through the LangGraph workflow."""
    data: dict[str, Any]              # All numerical/structured data from source
    template_vars: dict[str, Any]     # Prepared variables for docxtpl template
    narrative_sections: dict[str, str]  # Agent-authored explanatory text
    outline: list[str]                # Document structure
    fact_check_results: list[tuple[bool, str]]  # (passed, message) from fact checking
    qa_verdict: tuple[bool, str] | None  # Final QA result
    output_path: Path | None
    errors: list[str]
    diagram_paths: dict[str, str]     # diagram_name -> file path


# =============================================================================
# Helper: Prepare Template Variables from Data
# =============================================================================

def _prepare_template_vars(data: dict[str, Any]) -> dict[str, Any]:
    """Prepare all variables for docxtpl template from source data."""
    # The data dict should contain all numerical values
    # This function normalizes/structures them for the template
    template_vars = data.copy()
    
    # Convert boolean passed fields to status strings
    if "yield_passed" in data:
        template_vars["yield_status"] = "PASS" if data["yield_passed"] else "FAIL"
    if "fatigue_passed" in data:
        template_vars["fatigue_status"] = "PASS" if data["fatigue_passed"] else "FAIL"
    if "deflection_passed" in data:
        template_vars["deflection_status"] = "PASS" if data["deflection_passed"] else "FAIL"
    if "all_constraints_passed" in data:
        template_vars["overall_status"] = "PASS" if data["all_constraints_passed"] else "FAIL"
        template_vars["verification_badge"] = (
            "VERIFIED COMPLIANT (PASS)" if data["all_constraints_passed"] else "NON-COMPLIANT (FAIL)"
        )
    
    # Ensure required keys exist with defaults
    defaults = {
        "project_name": "Engineering Report",
        "verification_badge": "STATUS UNKNOWN",
        "yield_sf": 0.0,
        "min_yield_sf": 1.5,
        "yield_status": "FAIL",
        "fatigue_sf": 0.0,
        "min_fatigue_sf": 1.5,
        "fatigue_status": "FAIL",
        "max_deflection_mm": 0.0,
        "max_deflection_limit_mm": 5.0,
        "deflection_status": "FAIL",
        "total_mass_kg": 0.0,
        "mass_limit": "Unconstrained",
        "mass_status": "FAIL",
        "fatigue_life_cycles": "0",
        "target_life_cycles": "10000000",
        "life_status": "FAIL",
        "overall_status": "FAIL",
        "strength_review": "NOT REVIEWED",
        "fatigue_review": "NOT REVIEWED",
        "deflection_review": "NOT REVIEWED",
        "mass_review": "NOT REVIEWED",
        "critical_issues": [],
        "recommendations": [],
        "assumptions": [],
        "material_name": "Unknown",
        "yield_strength_mpa": 0.0,
        "ultimate_strength_mpa": 0.0,
        "endurance_limit_mpa": 0.0,
        "elastic_modulus_gpa": 206.0,
        "density_kgm3": 7850,
        "reactions": [],
        "applied_torque_nm": 0.0,
        "has_critical_section": False,
        "crit_sec": {},
        "has_bearings": False,
        "bearings": [],
        "has_keyway": False,
        "keyway": {},
        "openscad_code": "// No CAD code available",
        "calculation_steps": [],
    }
    
    for key, default_val in defaults.items():
        if key not in template_vars:
            template_vars[key] = default_val
    
    return template_vars


# =============================================================================
# Agent Nodes
# =============================================================================

def research_node(state: DocGenState) -> DocGenState:
    """Research Agent: Gather and structure context from source data."""
    data = state["data"]
    
    # Prepare all template variables
    template_vars = _prepare_template_vars(data)
    state["template_vars"] = template_vars
    
    # Initialize narrative sections
    state["narrative_sections"] = {}
    state["errors"] = []
    state["diagram_paths"] = {}
    
    return state


def diagram_node(state: DocGenState) -> DocGenState:
    """Diagram Agent: Generate SVG/PNG diagrams from data."""
    data = state["data"]
    template_vars = state["template_vars"]
    
    # Generate diagrams in the output directory
    project_name = template_vars.get("project_name", "report").replace(" ", "_")
    output_dir = Path(f"output/{project_name}/diagrams")
    
    try:
        # Check if we have the required data for shaft diagrams
        x_stations = data.get("x_stations", [])
        if x_stations and any(k in data for k in ["shear_force", "bending_moment", "von_mises_stress_mpa", "deflection_mm"]):
            diagram_paths = generate_all_diagrams(data, output_dir)
            state["diagram_paths"] = diagram_paths
            state["template_vars"]["diagram_paths"] = diagram_paths
        else:
            state["diagram_paths"] = {}
            state["template_vars"]["diagram_paths"] = {}
    except Exception as e:
        state["errors"].append(f"Diagram generation failed: {e}")
        state["diagram_paths"] = {}
        state["template_vars"]["diagram_paths"] = {}
    
    return state


def outline_node(state: DocGenState) -> DocGenState:
    """Outline Agent: Create document structure based on available data."""
    template_vars = state["template_vars"]
    
    # Standard engineering report structure
    outline = [
        "Executive Summary",
        "AI Design Review & Root-Cause Analysis",
        "Design Inputs & Engineering Assumptions Log",
        "Material Mechanical Properties",
        "Equilibrium & Support Reactions",
        "Critical Section Analysis (Peak Stress Plane)",
        "Standard Machine Components: Bearings & Keys",
        "Parametric OpenSCAD 3D CAD Definition",
        "Deterministic Physics Solver Audit Trace"
    ]
    
    # Conditionally include sections based on data availability
    if not template_vars.get("has_critical_section"):
        outline.remove("Critical Section Analysis (Peak Stress Plane)")
    if not template_vars.get("has_bearings"):
        outline.remove("Standard Machine Components: Bearings & Keys")
    elif not template_vars.get("has_keyway"):
        # Keep bearings section but note no keyway
        pass
    
    state["outline"] = outline
    return state


def writer_node(state: DocGenState) -> DocGenState:
    """Writer Agent: Generate explanatory narrative text (NO numerical values)."""
    template_vars = state["template_vars"]
    narrative = {}
    
    # Executive Summary narrative
    narrative["exec_summary"] = (
        "This calculation sheet presents the deterministic verification of the "
        f"{template_vars['project_name']} design. All numerical results are derived "
        "from closed-form physics solvers with full audit traceability. "
        "The design is evaluated against yield, fatigue, deflection, and mass constraints."
    )
    
    # AI Design Review narrative
    narrative["ai_review_intro"] = (
        "The AI Design Critic provides an independent assessment of the design "
        "based on deterministic solver outputs. The review identifies root causes "
        "of any constraint violations and recommends specific engineering actions."
    )
    
    # Assumptions narrative
    narrative["assumptions_intro"] = (
        "The following table documents all engineering assumptions made during "
        "model setup. Each assumption is traced to its source and audit status. "
        "CONFIRMED assumptions are verified against standards; ASSUMED items "
        "require validation before manufacturing."
    )
    
    # Materials narrative
    narrative["materials_intro"] = (
        "Material properties are sourced from the material database. "
        "The endurance limit is estimated as 0.5 × Sut for steels per Shigley, "
        "adjusted for surface finish, size, and reliability factors by the fatigue solver."
    )
    
    # Reactions narrative
    narrative["reactions_intro"] = (
        "Support reactions are computed from static equilibrium of the loaded structure. "
        "Vertical reactions and reaction moments at each support are listed below. "
        "The nominal transmitted torque is applied at the driven element."
    )
    
    # Critical section narrative
    if template_vars.get("has_critical_section"):
        narrative["critical_section_intro"] = (
            "The critical section is the axial station with the highest effective "
            "Von Mises stress. Stress concentration factors (Kt) for bending and "
            "torsion are applied per standard design practice. The effective "
            "Von Mises stress combines bending and torsional components using the "
            "distortion energy theory: σ_vm = √(σ_b² + 3τ²)."
        )
    else:
        narrative["critical_section_intro"] = ""
    
    # Bearings narrative
    if template_vars.get("has_bearings"):
        narrative["bearings_intro"] = (
            "Rolling bearings are selected per catalogue data and verified "
            "against ISO 281 L10h rating life. The equivalent dynamic load P "
            "accounts for combined radial and axial loading. Suitability ratings "
            "EXCELLENT/GOOD/MARGINAL indicate margin above the target life."
        )
    else:
        narrative["bearings_intro"] = ""
    
    # Keyway narrative
    if template_vars.get("has_keyway"):
        narrative["keyway_intro"] = (
            "Keyway verification follows DIN 6885-1 for parallel keys. Shear and "
            "crushing safety factors are computed against the key material yield "
            "strength. Both failure modes must pass for the keyway to be acceptable."
        )
    else:
        narrative["keyway_intro"] = ""
    
    # OpenSCAD narrative
    narrative["openscad_intro"] = (
        "The parametric OpenSCAD script below defines the complete 3D geometry "
        "using the solver-selected dimensions. All dimensions are derived from "
        "deterministic calculations, not manual input. The script is ready for "
        "direct use in OpenSCAD, export to STEP/STL, or CAM processing."
    )
    
    # Audit trace narrative
    narrative["audit_intro"] = (
        "The following audit trace documents every calculation step performed by "
        "the deterministic physics solver. This provides full traceability from "
        "inputs to final results, enabling independent verification."
    )
    
    state["narrative_sections"] = narrative
    return state


def fact_checker_node(state: DocGenState) -> DocGenState:
    """Fact Checker Agent: Validate all narrative claims against source data."""
    template_vars = state["template_vars"]
    data = state["data"]
    
    fact_checks = []
    
    # Verify overall status claim
    ai_claim_safe = template_vars["overall_status"] == "PASS"
    physics_safe = data.get("all_constraints_passed", False)
    passed = (ai_claim_safe == physics_safe)
    msg = "Consistent" if passed else f"Mismatch: AI claims {'PASS' if ai_claim_safe else 'FAIL'}, physics says {'PASS' if physics_safe else 'FAIL'}"
    fact_checks.append((passed, f"Overall status: {msg}"))
    
    # Verify yield claim
    ai_claim_yield = template_vars["yield_status"] == "PASS"
    physics_yield = data.get("yield_passed", False)
    passed = (ai_claim_yield == physics_yield)
    msg = "Consistent" if passed else f"Mismatch: AI claims {'PASS' if ai_claim_yield else 'FAIL'}, physics says {'PASS' if physics_yield else 'FAIL'}"
    fact_checks.append((passed, f"Yield constraint: {msg}"))
    
    # Verify fatigue claim
    ai_claim_fatigue = template_vars["fatigue_status"] == "PASS"
    physics_fatigue = data.get("fatigue_passed", False)
    passed = (ai_claim_fatigue == physics_fatigue)
    msg = "Consistent" if passed else f"Mismatch: AI claims {'PASS' if ai_claim_fatigue else 'FAIL'}, physics says {'PASS' if physics_fatigue else 'FAIL'}"
    fact_checks.append((passed, f"Fatigue constraint: {msg}"))
    
    # Verify deflection claim
    ai_claim_deflection = template_vars["deflection_status"] == "PASS"
    physics_deflection = data.get("deflection_passed", False)
    passed = (ai_claim_deflection == physics_deflection)
    msg = "Consistent" if passed else f"Mismatch: AI claims {'PASS' if ai_claim_deflection else 'FAIL'}, physics says {'PASS' if physics_deflection else 'FAIL'}"
    fact_checks.append((passed, f"Deflection constraint: {msg}"))
    
    # Check for any numerical claims in narrative (should be none)
    for section_name, text in state["narrative_sections"].items():
        import re
        numeric_claims = re.findall(r'\d+(?:\.\d+)?\s*(?:MPa|mm|N|N·m|kN|cycles|kg|GPa)', text)
        if numeric_claims:
            fact_checks.append((
                False, 
                f"Section '{section_name}' contains numerical values that should come from template: {numeric_claims}"
            ))
    
    state["fact_check_results"] = fact_checks
    
    # Collect any errors
    for passed, msg in fact_checks:
        if not passed:
            state["errors"].append(f"FACT CHECK FAILED: {msg}")
    
    return state


def editor_node(state: DocGenState) -> DocGenState:
    """Editor Agent: Refine language and ensure consistency."""
    narrative = state["narrative_sections"]
    
    required_keys = [
        "exec_summary", "ai_review_intro", "assumptions_intro", "materials_intro",
        "reactions_intro", "critical_section_intro", "bearings_intro",
        "keyway_intro", "openscad_intro", "audit_intro"
    ]
    
    for key in required_keys:
        if key not in narrative or not narrative[key].strip():
            narrative[key] = f"[Section {key} - content to be generated]"
    
    state["narrative_sections"] = narrative
    return state


def renderer_node(state: DocGenState) -> DocGenState:
    """Renderer Agent: Fill docxtpl template with data and narrative."""
    try:
        from docxtpl import DocxTemplate
        from docxtpl import InlineImage
        from docx.shared import Inches
    except ImportError:
        state["errors"].append("docxtpl not installed. Install with: pip install docxtpl")
        return state
    
    template_path = Path("templates/engineering_report.docx")
    if not template_path.exists():
        state["errors"].append(f"Template not found at {template_path}")
        return state
    
    # Prepare context for docxtpl
    context = {}
    context.update(state["template_vars"])
    context.update(state["narrative_sections"])
    
    # Create the template first
    doc = DocxTemplate(str(template_path))
    
    # Handle diagram images - convert paths to InlineImage objects
    diagram_paths = state.get("diagram_paths", {})
    for diagram_name, diagram_path in diagram_paths.items():
        if diagram_path and Path(diagram_path).exists():
            try:
                context[f"diagram_{diagram_name}"] = InlineImage(
                    doc, 
                    str(diagram_path), 
                    width=Inches(6.5)
                )
            except Exception as e:
                state["errors"].append(f"Failed to load diagram {diagram_name}: {e}")
    
    # Render template
    doc.render(context)
    
    # Save output
    project_name = state["template_vars"].get("project_name", "report").replace(" ", "_")
    output_path = Path(f"output/{project_name}/report.docx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    
    state["output_path"] = output_path
    return state


def qa_validator_node(state: DocGenState) -> DocGenState:
    """QA Validator Agent: Final verification of the generated document."""
    data = state["data"]
    
    # Final physics authority check
    ai_claim_safe = state["template_vars"]["overall_status"] == "PASS"
    physics_safe = data.get("all_constraints_passed", False)
    
    passed = (ai_claim_safe == physics_safe)
    msg = "Consistent" if passed else f"Mismatch: AI claims {'PASS' if ai_claim_safe else 'FAIL'}, physics says {'PASS' if physics_safe else 'FAIL'}"
    state["qa_verdict"] = (passed, msg)
    
    if not passed:
        state["errors"].append(f"QA VALIDATION FAILED: {msg}")
    
    # Verify document was created
    if state["output_path"] is None or not state["output_path"].exists():
        state["errors"].append("QA VALIDATION FAILED: Output document not created")
        state["qa_verdict"] = (False, "Output document not created")
    
    return state


# =============================================================================
# Build Workflow Graph
# =============================================================================

def build_docgen_workflow() -> StateGraph:
    """Build and return the LangGraph workflow for document generation."""
    workflow = StateGraph(DocGenState)
    
    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("diagram", diagram_node)
    workflow.add_node("outline", outline_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("fact_checker", fact_checker_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("renderer", renderer_node)
    workflow.add_node("qa_validator", qa_validator_node)
    
    # Define edges (sequential pipeline)
    workflow.set_entry_point("research")
    workflow.add_edge("research", "diagram")
    workflow.add_edge("diagram", "outline")
    workflow.add_edge("outline", "writer")
    workflow.add_edge("writer", "fact_checker")
    workflow.add_edge("fact_checker", "editor")
    workflow.add_edge("editor", "renderer")
    workflow.add_edge("renderer", "qa_validator")
    workflow.add_edge("qa_validator", END)
    
    return workflow.compile()


# =============================================================================
# Public API
# =============================================================================

def generate_docx_report(data: dict[str, Any]) -> tuple[Path | None, list[str]]:
    """
    Generate a DOCX engineering report using the multi-agent LangGraph workflow.
    
    Args:
        data: Dictionary containing all numerical/structured data from solver.
              Must include keys like: project_name, x_stations, shear_force, 
              bending_moment, von_mises_stress_mpa, deflection_mm, all_constraints_passed,
              yield_passed, fatigue_passed, deflection_passed, etc.
    
    Returns:
        (output_path, errors) - output_path is None if generation failed
    """
    workflow = build_docgen_workflow()
    
    initial_state: DocGenState = {
        "data": data,
        "template_vars": {},
        "narrative_sections": {},
        "outline": [],
        "fact_check_results": [],
        "qa_verdict": None,
        "output_path": None,
        "errors": [],
        "diagram_paths": {},
    }
    
    final_state = workflow.invoke(initial_state)
    
    return final_state["output_path"], final_state["errors"]


__all__ = ["generate_docx_report", "build_docgen_workflow", "DocGenState"]
"""
Anthropic SDK wrapper with full domain knowledge injection.

System prompt structure:
  - Role definition (engineer persona)
  - Full knowledge base (ALL_KNOWLEDGE from knowledge.py) — cache-eligible
  - Dynamic dataset context is in the user message

Prompt caching applied to both system prompt and asset context to minimise
token cost on repeated queries against the same loaded dataset.
"""
import json
import logging
from typing import Optional

import anthropic

from config import settings
from services.knowledge import ALL_KNOWLEDGE

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── System prompt (built once, cached) ───────────────────────────────────────

_ROLE = """\
You are an expert highway asset intelligence analyst. You reason as a senior highways engineer
making capital programme decisions for a local highway authority. Your expertise covers:

- UKPMS and PAS:2161 condition assessment frameworks
- SCANNER survey methodology: RCI calculation, defect parameter engineering interpretation
- CVI (Coarse Visual Inspection) and DVI (Detailed Visual Inspection)
- SCRIM skid resistance surveys and investigatory levels (DMRB HD28)
- Treatment selection and whole-life cost optimisation
- West Sussex County Council (WSCC) network characteristics and data context

When responding you:
- Reference specific NSG references and road names (never generic "this road")
- Explain the engineering reasoning behind deterioration patterns
- Distinguish surface-only from structural failure — this drives treatment cost by 5–10×
- Apply defect driver analysis: Texture-dominant CI → surface treatment; LPV/Rutting-dominant → structural
- Consider whole-life cost, not just unit rate
- Use professional UK highways terminology throughout
- Are direct and actionable — no generic filler, no unnecessary caveats
"""


def _build_system_prompt() -> str:
    knowledge_str = json.dumps(ALL_KNOWLEDGE, indent=2)
    return _ROLE + "\n\n=== DOMAIN KNOWLEDGE BASE ===\n" + knowledge_str


def _build_asset_context(priority_assets: list[dict], stats: dict) -> str:
    lines = [
        "=== LOADED NETWORK DATA ===",
        f"Total assets:          {stats.get('total_assets', 0):>6}",
        f"  SCANNER (A/B/C):     {stats.get('scanner_count', 0):>6}",
        f"  CVI (unclassified):  {stats.get('cvi_count', 0):>6}",
        f"Critical risk:         {stats.get('critical_count', 0):>6}",
        f"High risk:             {stats.get('high_count', 0):>6}",
        f"Medium risk:           {stats.get('medium_count', 0):>6}",
        f"Low / no data:         {stats.get('low_count', 0):>6}",
        f"Network average CI:    {stats.get('avg_ci', 'N/A')}",
        f"Reactive jobs loaded:  {stats.get('total_reactive_jobs', 0):>6}",
    ]

    vs = stats.get("vaisala_stats")
    if vs:
        drift_flag = (
            " ⚠ WEIGHT DRIFT — RAG thresholds are not reliable for this survey: "
            "defect weights used during scoring differ from those against which "
            "Red≥4.0 / Amber≥1.8 were derived. Treat RAG banding as indicative only."
            if vs.get("has_weight_drift") else ""
        )
        lines += [
            "",
            "=== VAISALA DST — LATEST SURVEY ===",
            f"Survey: {vs.get('source_filename')} | Network: {vs.get('network_key')}{drift_flag}",
            "RAG thresholds: Red ≥ 4.0 · Amber ≥ 1.8 (fixed evidence-derived thresholds, NOT percentile ranks).",
            "A Red section has genuinely failed the validated severity threshold — not merely 'worse than average'.",
            f"  Red sections:   {vs.get('red_count', 0):>5}  ({vs.get('red_km', 0):.2f} km)",
            f"  Amber sections: {vs.get('amber_count', 0):>5}  ({vs.get('amber_km', 0):.2f} km)",
            f"  Green sections: {vs.get('green_count', 0):>5}",
            f"  Total network:  {vs.get('section_count', 0)} sections · {vs.get('total_km', 0):.2f} km",
            "",
            "Top 5 Vaisala sections by weighted score (List 4, desc):",
        ]
        for i, s in enumerate(vs.get("top5_sections", []), 1):
            contr = s.get("primary_defect_contribution")
            contr_str = f" ({contr:.4f} score units)" if contr is not None else ""
            lines.append(
                f"  {i}. [{s.get('rag_band','?'):6}] {s.get('section_ref','?')} — "
                f"{s.get('road_name') or '?'} — "
                f"Score={s.get('priority_score', 0):.2f} — "
                f"Treatment: {s.get('treatment') or '—'} — "
                f"Primary defect: {s.get('primary_defect') or '—'}{contr_str}"
            )

    lines += [
        "",
        "=== TOP 20 PRIORITY ASSETS (sorted by composite risk score) ===",
        f"{'#':>3}  {'[BAND]':8}  {'NSG_REF':15}  {'ROAD NAME':30}  {'PARISH':15}  "
        f"{'CI':>6}  {'Score':>6}  {'CI_S':>5}  {'DD_S':>5}  {'EDI_S':>5}  {'RXN_S':>5}  "
        f"{'Driver':12}  EDI",
    ]

    for i, a in enumerate(priority_assets[:20], 1):
        contrib_detail = ""
        if a.get("ci_contribution_lpv") is not None:
            contribs = {
                "LPV": a.get("ci_contribution_lpv", 0) or 0,
                "RUT": a.get("ci_contribution_rutting", 0) or 0,
                "CRK": a.get("ci_contribution_cracking", 0) or 0,
                "TXT": a.get("ci_contribution_texture", 0) or 0,
            }
            contrib_detail = " | " + " ".join(f"{k}:{v:.0%}" for k, v in contribs.items() if v)

        lines.append(
            f"{i:>3}  [{a.get('risk_band','?'):8}]  "
            f"{str(a.get('nsg_ref','?')):15}  "
            f"{str(a.get('road_name') or 'Unknown'):30}  "
            f"{str(a.get('parish') or '—'):15}  "
            f"{str(a.get('avg_ci') or '—'):>6}  "
            f"{a.get('composite_score',0):>6.1f}  "
            f"{a.get('ci_score',0):>5.1f}  "
            f"{a.get('defect_driver_score',0):>5.1f}  "
            f"{a.get('edi_score',0):>5.1f}  "
            f"{a.get('reactive_score',0):>5.1f}  "
            f"{str(a.get('dominant_defect_driver') or '—'):12}  "
            f"{str(a.get('edi_avg') or '—')}"
            f"{contrib_detail}"
        )
        if a.get("treatment_recommendation"):
            lines.append(f"     → {a['treatment_recommendation']}")

    return "\n".join(lines)


# ── Public methods ────────────────────────────────────────────────────────────

def generate_analysis(priority_assets: list[dict], stats: dict) -> str:
    """Generate a structured network analysis briefing."""
    client = _get_client()
    system_prompt = _build_system_prompt()
    asset_context = _build_asset_context(priority_assets, stats)

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=3000,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": asset_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Provide a comprehensive network analysis briefing (max 600 words):\n\n"
                            "1. NETWORK HEALTH SUMMARY\n"
                            "   - Overall condition vs WSCC benchmarks\n"
                            "   - Key risk indicators (% Red, % Amber, avg CI)\n\n"
                            "2. CRITICAL ASSETS — DEFECT DRIVER ANALYSIS\n"
                            "   - Top 5 assets: NSG ref, road name, dominant driver, engineering rationale\n"
                            "   - Distinguish structural vs surface interventions\n\n"
                            "3. PATTERN INSIGHTS\n"
                            "   - Defect clustering (parish, road class, defect type)\n"
                            "   - Surface vs structural split across critical/high band\n\n"
                            "4. PRIORITISED RECOMMENDATIONS\n"
                            "   - Capital programme candidates (structural intervention)\n"
                            "   - Surface treatment programme candidates\n"
                            "   - Sections for monitoring (no immediate intervention)\n\n"
                            "5. DATA QUALITY OBSERVATIONS\n"
                            "   - Any missing data, survey gaps, or low-confidence scores"
                        ),
                    },
                ],
            }
        ],
    )

    u = response.usage
    logger.info(
        "Analysis tokens — in=%d out=%d cache_read=%s cache_create=%s",
        u.input_tokens, u.output_tokens,
        getattr(u, "cache_read_input_tokens", "N/A"),
        getattr(u, "cache_creation_input_tokens", "N/A"),
    )
    return response.content[0].text


_ASSET_NARRATIVE_SYSTEM = (
    "You are an expert highway asset management analyst. "
    "Write a concise 3–4 sentence assessment of this road section for a Head of Highways. "
    "Include: what the condition data shows, what is driving deterioration, "
    "what treatment is recommended and why, and what the consequence of deferral is. "
    "Use professional UK highways terminology. "
    "Base your assessment only on the data provided. "
    "Never invent data not present in the context."
)


def generate_asset_narrative(asset_context: str) -> str:
    """Generate a 3–4 sentence asset assessment for the detail panel."""
    client = _get_client()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=400,
        system=[{
            "type": "text",
            "text": _ASSET_NARRATIVE_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": asset_context}],
    )
    u = response.usage
    logger.info(
        "Asset narrative tokens — in=%d out=%d cache_read=%s",
        u.input_tokens, u.output_tokens,
        getattr(u, "cache_read_input_tokens", "N/A"),
    )
    return response.content[0].text


def answer_query(
    question: str,
    priority_assets: list[dict],
    stats: dict,
    conversation_history: Optional[list[dict]] = None,
) -> str:
    """Answer a free-form question with optional multi-turn history."""
    client = _get_client()
    system_prompt = _build_system_prompt()
    asset_context = _build_asset_context(priority_assets, stats)

    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": asset_context,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": question,
            },
        ],
    })

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=1500,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )

    return response.content[0].text


_VAISALA_NARRATIVE_SYSTEM = (
    "You are an expert highway asset management analyst with deep knowledge of Vaisala DST road condition "
    "surveys and the PAS 2161 road condition management framework. "
    "Write a concise 3–4 sentence assessment of this road section for a Head of Highways. "
    "Cover: what the Vaisala condition data shows; the engineering significance of the defect pattern "
    "(is this surface-only deterioration or structural breakdown — this distinction drives treatment cost "
    "by 5–10×); what treatment is recommended and why; and, if QC fields are present and low, what "
    "confidence limitation applies. "
    "The RAG thresholds (Red ≥ 4.0, Amber ≥ 1.8) are fixed evidence-derived thresholds, not percentile "
    "ranks — a Red classification is a genuine severity statement, not merely 'worse than average'. "
    "If weight drift is flagged, note that RAG banding for this section may not be reliable. "
    "Road Surface Condition and Asphalt Condition scores use an inverted scale — a LOWER score "
    "indicates WORSE condition. A Road Surface Condition of 0.1 is near failure; 1.0 is excellent. "
    "Do not describe low RSC or Asphalt Condition values as good condition. "
    "Use professional UK highways terminology. "
    "Base your assessment only on the data provided. Never invent data not present in the context."
)


def generate_vaisala_section_narrative(section_context: str) -> str:
    """Generate a 3–4 sentence AI assessment for a Vaisala section detail panel."""
    client = _get_client()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=400,
        system=[{
            "type": "text",
            "text": _VAISALA_NARRATIVE_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": section_context}],
    )
    u = response.usage
    logger.info(
        "Vaisala section narrative tokens — in=%d out=%d cache_read=%s",
        u.input_tokens, u.output_tokens,
        getattr(u, "cache_read_input_tokens", "N/A"),
    )
    return response.content[0].text

"""Rebuild the Lee–Tarver audit documents: python -m kunit.lee_tarver_report."""

from __future__ import annotations

from html import escape
from pathlib import Path

from kunit.lee_tarver import (
    SETS,
    LeeTarverSet,
    audit_set,
    render_eos,
    unreacted_pressure,
)


CORRECTIONS = {
    "tnt(i&g)": [
        ("MAT RO", "1.63", "1.61", "cast TNT calibration density"),
        ("TMP0", "288", "298", "source temperature"),
        ("CVR", "2.172e-5", "2.05e-5", "published heat capacity"),
        ("R3", "1.22653e-5", "0.8926 × 2.05e-5", "published omega and heat capacity"),
    ],
    "pbx-9501(i&g)": [
        ("MAT RO", "1.8", "1.838", "25 C calibration density"),
        ("TMP0", "288", "298", "25 C calibration temperature"),
        ("AR1", "0.227", "0.277", "published exponent d"),
    ],
    "jh-2(i&g)": [
        (
            "MAT RO",
            "1.72",
            "1.717",
            "Awan et al., CEJEM (2024), Table 2 / Aerospace Table 4 reactant density; product calibration remains at 1.667",
        ),
        (
            "R3",
            "2.22e-5",
            "0.8938 × 1.6782231e-5",
            "Hong et al. (2020), Table 2 omega; Cawkwell et al. (2016), p. 4 pure-RDX Cv proxy; not a JH-2 calibration",
        ),
        (
            "R2",
            "-0.032785",
            "+0.0328",
            "Hong et al. (2020), Table 2, and Awan et al. (2024), Table 2; initial pressure remains inconsistent",
        ),
        (
            "CVR",
            "2.487e-5",
            "1.6782231e-5",
            "217.1 J/(mol K) for pure alpha-RDX from Cawkwell et al. (2016), p. 4, converted with NIST molar mass and rho0=1.717 g/cm3; a proxy only",
        ),
    ],
    "ultrafine-tatb(i&g)": [
        ("R3", "2.22e-5", "0.8938 × 2.487e-5", "published omega and heat capacity"),
        ("AR1", "0.667", "1.0", "published exponent d"),
        ("ES1", "1.0", "0.667", "published exponent c"),
    ],
    "lx-17(i&g)": [
        ("R3", "2.22e-5", "0.8938 × 2.487e-5", "published omega and heat capacity"),
        ("AR1", "0.667", "1.0", "published exponent d"),
        ("ES1", "1.0", "0.667", "published exponent c"),
    ],
}


def _number(value: float) -> str:
    return f"{value:.8g}"


def _eos_table(source: LeeTarverSet, reacted: bool) -> str:
    eos = source.product if reacted else source.unreacted
    fields = ("A", "B", "R1", "R2", "ω", "Cv", "ωCv")
    values = (eos.a, eos.b, eos.r1, eos.r2, eos.omega, eos.cv, eos.thermal)
    cards = (
        ("A", "B", "XP1", "XP2", "G/CVP", "CVP", "G")
        if reacted
        else ("R1", "R2", "R5", "R6", "R3/CVR", "CVR", "R3")
    )
    rows = [
        "| Model | LS-DYNA | Raw (Mbar, Mbar/K) | mm–mg–µs (GPa, GPa/K) |",
        "|---|---|---:|---:|",
    ]
    for name, card, value in zip(fields, cards, values):
        if value is None:
            rows.append(
                f"| {name} | {card} | not published | inferred from legacy card |"
            )
        else:
            factor = 1 if name in ("R1", "R2", "ω") else 100
            rows.append(
                f"| {name} | {card} | {_number(value)} | {_number(value * factor)} |"
            )
    return "\n".join(rows)


def _kinetics_table(source: LeeTarverSet) -> str:
    r = source.rates
    tnt = source.material_id == "tnt(i&g)"
    fields = (
        ("I", "FREQ", r.i, 0),
        ("µc" if tnt else "a", "CCRIT", r.a, 0),
        ("a" if tnt else "b", "FRER", r.b, 0),
        ("x", "EETAL", r.x, 0),
        ("F_ig,max", "FMXIG", r.ignition_limit, 0),
        ("G1", "GROW1", r.g1, r.y),
        ("c", "ES1", r.c, 0),
        ("d", "AR1", r.d, 0),
        ("y", "EM", r.y, 0),
        ("F_g1,max", "FMXGR", r.growth_limit, 0),
        ("G1 (FOI)" if tnt else "G2", "GROW2", r.g2, r.z),
        ("b (FOI)" if tnt else "e", "ES2", r.e, 0),
        ("c (FOI)" if tnt else "g", "AR2", r.g, 0),
        ("y (FOI)" if tnt else "z", "EN", r.z, 0),
        ("F_g2,min", "FMNGR", r.completion_start, 0),
    )
    rows = ["| Model | LS-DYNA | Raw | mm–mg–µs |", "|---|---|---:|---:|"]
    for name, card, value, power in fields:
        target = value / 100**power if power else value
        rows.append(f"| {name} | {card} | {_number(value)} | {_number(target)} |")
    return "\n".join(rows)


def render_report(source: LeeTarverSet) -> str:
    audit = audit_set(source)
    citation = (
        f"[{source.source}]({source.source_url})"
        if source.source_url
        else source.source
    )
    density = _number(source.rho0) if source.rho0 is not None else "not established"
    crossing = (
        f"V≈{audit.first_nonpositive_bulk[0]:.2f}, T={audit.first_nonpositive_bulk[1]:.1f} K"
        if audit.first_nonpositive_bulk
        else "none on scanned grid"
    )
    negative = next(
        (
            0.5 + j * 0.01
            for j in range(151)
            if unreacted_pressure(source, 0.5 + j * 0.01, source.tmp0) < 0
        ),
        None,
    )
    negative_text = (
        f"starts by V≈{negative:.2f}"
        if negative is not None
        else "none on scanned grid"
    )
    pressure_range = [
        unreacted_pressure(source, 0.5 + j * 0.01, source.tmp0) for j in range(151)
    ]
    changed = CORRECTIONS.get(source.material_id, [])
    calibrated_density = density if source.source_url else "not established"
    kinetics_density = calibrated_density
    mat_density = density if source.rho0 is not None else "no MAT section"
    density_label = (
        "calibration density" if source.source_url else "legacy MAT density only"
    )
    confirmed = (
        "published EOS, rates, T0 and density"
        if source.source_url
        else "no complete source set"
    )
    corrected = ", ".join(field for field, _, _, _ in changed) or "none"
    unconfirmed = (
        "tensile and extrapolation limits"
        if source.source_url
        else "EOS, kinetics, calibration density and model limits"
    )
    changes = (
        "\n".join(
            f"| {field} | {old} | {new} | {reason}; {citation} |"
            for field, old, new, reason in changed
        )
        or "| — | — | — | no numerical change |"
    )
    status_note = "Published ω and Cv determine G and R3."
    disputed = (
        "no conflicting source for the same identified calibration has been established"
    )
    flags = ", ".join(audit.issues) or "none"
    origin = "literature" if source.source_url else "untraced legacy card"
    enq_note = (
        "published E0 per reference volume"
        if source.source_url
        else "legacy E0 with unverified provenance, interpreted per reference volume"
    )
    conflict_note = ""
    if source.status == "source_conflict":
        calibrated_density = "product 1.667; reactant 1.717"
        kinetics_density = "1.717"
        density_label = "reported reactant/kinetics density; product differs"
        confirmed = "reactant A, B, R1/R2, ω and rates published for 8701/JH-2; the separate Zhu product EOS/E0 is published at 1.667 g/cm³"
        disputed = "the +0.0328 Mbar reactant B from Hong/Awan gives a 1.89 GPa initial pressure with the pure-RDX CVR proxy in LS-DYNA; the same-density product and complete initial-state calibration are absent"
        unconfirmed = "JH-2 CVR calibration, target product CVP and product EOS at the reactant density, TMP0, FMXIG, FMXGR, FMNGR, explicit G1/G2 pressure units and LS-DYNA shock-initiation validation"
        status_note = (
            "This is an experimental composite card, not a verified calibration."
        )
        origin = "mixed literature and pre-audit kunit card"
        enq_note = (
            "Zhu et al. E0 at 1.667 g/cm³, applied here to a different MAT density"
        )
        conflict_note = """## Parameter provenance and conflict

- Product A, B, XP1, XP2, ω and ENQ: [Zhu et al. (2022), Table 2](https://www.sciengine.com/parse/pdf/2096-2304/B0290F3EBF5E4846B7046AB9E2778AD4.pdf), 8701 at 1.667 g/cm³.
- [Hong et al. (2020), Tables 1–3](https://doi.org/10.1016/j.dt.2019.04.007) report an I&G model for 8701 in AUTODYN at 1.72 g/cm³. Table 1 has a different product JWL (A=8.524, B=0.1802 Mbar, R1=4.6, R2=1.3, ω=0.38); Tables 2–3 report the reactant EOS and rates. Hong does not provide CVP, CVR or the temperature reference needed to transfer that I&G set to LS-DYNA.
- [Awan et al., Aerospace (2024)](https://www.researchgate.net/publication/381763413_Application_of_Lee-Tarver_Model_for_Energetic_Materials_Safety_Assessment_Utilized_in_Aerospace_Applications), Table 2, gives **A=6.184, B=0.069 Mbar, R1=4.3, R2=0.87, ω=0.38 at 1.72 g/cm³** for the JH-2 *threat shaped charge* modeled with JWL/high-explosive burn. Its Tables 4–5 describe the JH-2 *target* reactant and I&G rates. Table 2 is not identified as the target I&G product branch and does not supply CVP; inserting it into this card would still leave an incomplete target calibration.
- Reactant R1, R2, R5, R6, ω and I, G1, G2, a, b, c, d, e, g, x, y, z: [Hong et al. (2020), Tables 2–3](https://doi.org/10.1016/j.dt.2019.04.007), [Awan et al., Aerospace (2024), Tables 4–5](https://www.researchgate.net/publication/381763413_Application_of_Lee-Tarver_Model_for_Energetic_Materials_Safety_Assessment_Utilized_in_Aerospace_Applications) and [Awan et al., CEJEM (2024), Tables 2–3](https://wydawnictwa.ipo.lukasiewicz.gov.pl/wp-content/uploads/2024/11/CEJEM-1327-v0-Huang.pdf), at 1.72 or 1.717 g/cm³ depending on publication.
- Awan labels EOS pressure in Mbar but does not label the units of G1/G2 in its rate table. Their Mbar pressure basis is inferred from the article's EOS and the pre-audit card; the 140→0.014 and 1000→0.001 conversions therefore inherit this uncertainty.
- Reactant R2=**+0.0328 Mbar** follows Hong and Awan. CVR is computed from the **pure α-RDX, 300 K, model Cᵥ=217.1 J/(mol K)** in [Cawkwell et al. (2016), p. 4](https://www.osti.gov/servlets/purl/1498045), [RDX molar mass 222.1163 g/mol, NIST](https://webbook.nist.gov/cgi/cbook.cgi?Name=RDX), and reference density 1.717 g/cm³: CVR=ρ₀ Cᵥ/M/10¹¹=1.6782231·10⁻⁵ Mbar/K. This is a pure-RDX proxy, **not** a measured or calibrated JH-2 CVR. R3 is computed as 0.8938×CVR.
- CVP=10⁻⁵ Mbar/K, TMP0=298 K and FMXIG/FMXGR/FMNGR=0.022/1/0 retain the [pre-audit kunit card](source_search.md) values; no JH-2 source was found for them. CVP describes reaction products and cannot be inferred from solid RDX heat capacity.
- With published positive R2 and pure-RDX CVR, the LS-DYNA temperature form gives **p₀≈+1.89 GPa at 298 K**. This is an inconsistent initial state for ambient material; neither Hong nor Awan publishes the missing temperature/energy reference for direct transfer. Do not use this card as a validated initiation threshold.

"""
    pressure_warning = (
        "Warning: residual initial pressure exceeds 1 MPa; published initial-state conditions are needed before use."
        if "large initial pressure residual" in audit.issues
        else "Initial pressure residual is below 1 MPa."
    )
    table_note = (
        "The tables combine literature values and the legacy assumptions listed above; the displayed card is"
        if source.status == "source_conflict"
        else "The source values in the tables determine the card coefficients; the displayed card is"
    )
    rate_units_note = (
        "are assumed to have"
        if source.status == "source_conflict"
        else "have"
    )
    tnt_note = (
        " TNT uses only its ignition and one growth term, placed in the GROW2 card slot. The FOI paper calls its ignition depletion exponent *a* (FRER here), critical compression *µc* (CCRIT), and its growth exponents *b*, *c* (ES2, AR2)."
        if source.material_id == "tnt(i&g)"
        else ""
    )
    return f"""# {source.title}: Lee–Tarver audit

## Identification

- Calibration: {source.note}
- Initial density: {density} g/cm³ ({density_label}); temperature: {_number(source.tmp0)} K.
- Source: {citation}. Raw values: {origin}; stored units: cm–g–µs (Mbar, µs).
- Status: **{source.status}**. {status_note}

## Density consistency

| EOS calibration ρ0 | Kinetic calibration ρ0 | *MAT RO | Library output |
|---:|---:|---:|---|
| {calibrated_density} | {kinetics_density} | {mat_density} | stored density is enforced when a MAT card exists |

Changing RO requires a separately identified calibration; the material loader rejects silent density edits to these source-backed cards.

{conflict_note}
## Product EOS

p_p = A exp(−XP1 V_p) + B exp(−XP2 V_p) + G T_p/V_p, where G=ω_p CVP.

{_eos_table(source, True)}

## Unreacted EOS

p_e = R1 exp(−R5 V_e) + R2 exp(−R6 V_e) + R3 T_e/V_e, where R3=ω_e CVR for a sourced ω_e.

{_eos_table(source, False)}

At V=1, T=T0: source p0={_number(audit.p0)} Mbar; **card p0={_number(audit.card_p0)} Mbar = {_number(audit.card_p0 * 100)} GPa**.
Expected initial pressure: {(_number(source.expected_p0) + " Mbar (nominal ambient state)") if source.expected_p0 is not None else "not established for this untraced calibration"}.
Source G/CVP={_number(audit.omega_p)}, R3/CVR={_number(audit.omega_e)}; card G/CVP={_number(audit.card_omega_p)}, R3/CVR={_number(audit.card_omega_e)}.
{pressure_warning}
Automated flags: {flags}. A ratio outside [0, 2] requires manual review; a residual over 1 MPa is flagged, without imposing p0=0 on every calibration.
{table_note} [here]({source.material_id.replace("(i&g)", "")}.k).

## Ignition and Growth kinetics

The LS-DYNA equation is dF/dt = I(1−F)^b(1/V_e−1−a)^x + G1(1−F)^c F^d p^y + G2(1−F)^e F^g p^z, with each term restricted by its listed F limits. Pressure p is in the active unit system.{tnt_note}

Field definitions follow the [LS-DYNA R13 EOS 7 manual](https://ftp.lstc.com/anonymous/outgoing/jday/manuals/LS-DYNA_Manual_Volume_II_R13.pdf).

{_kinetics_table(source)}

FREQ has unit µs⁻¹. GROW1 and GROW2 {rate_units_note} units Mbar⁻ʸ µs⁻¹ and Mbar⁻ᶻ µs⁻¹. Conversion to GPa pressure units divides them by 100^y and 100^z. This keeps each Gp^n unchanged. The same µs time unit needs no rate multiplier.

## Dimensions and ENQ

The working base units are mm, mg, µs. Derived units: density mg/mm³ = 1000 kg/m³; speed mm/µs = 1000 m/s; acceleration mm/µs² = 10⁹ m/s²; force mg·mm/µs² = 10³ N; pressure mg/(mm·µs²) = 1 GPa; energy mg·mm²/µs² = 1 J; specific energy mm²/µs² = 10⁶ J/kg. Card CVP, CVR, G and R3 are heat capacity or thermal pressure coefficients **per reference volume**, in GPa/K; mass-specific heat instead has dimension J/(kg·K). ENQ maps to {enq_note}, so {_number(source.enq)} Mbar becomes {_number(source.enq * 100)} GPa; it is not treated as mass-specific energy. This mapping is documented in an [LS-DYNA Users Conference paper](https://lsdyna.ansys.com/wp-content/uploads/attachments/blast-impact13-d.pdf). I has dimension T⁻¹; Gi has dimension P⁻ⁿT⁻¹.

## Applicability and EOS scan

![Unreacted p(V) at three temperatures]({source.material_id.replace("(i&g)", "")}.svg)

![Unreacted p(V), release view]({source.material_id.replace("(i&g)", "")}-release.svg)

Scan: 0.5≤V≤2.0, T=0.75T0, T0, 1.25T0. At T0, pressure ranges from {_number(min(pressure_range))} to {_number(max(pressure_range))} Mbar. Negative p at T0: {negative_text}. First nonpositive adiabatic bulk modulus: {crossing}; this also flags potential c²≤0 because c²=V K_S/ρ0. K_S=V(A_e R1e exp(−R1e V)+B_e R2e exp(−R2e V))+ω_e(1+ω_e)Cv,e T/V. Nonfinite values: {audit.nonfinite}. The scan diagnoses extrapolation only; it does not establish a valid tensile range. Published tensile limits, pressure cutoffs, phase-mixing rules and AUTODYN-to-LS-DYNA equivalence are **not established** for this set.

- Published pressure and compression calibration ranges: not established from the cited table.
- Tensile calibration range, maximum unreacted V, pressure cutoff and temperature bounds: not established.
- AUTODYN and LS-DYNA mixture or extrapolation equivalence: not established; no such rule is silently transferred.

## Changes from the legacy card

| Field | Old | New | Reason and source |
|---|---:|---:|---|
{changes}

## Confirmed / corrected / disputed / unconfirmed

- Confirmed: {confirmed}.
- Corrected: {corrected}.
- Disputed: {disputed}.
- Unconfirmed: {unconfirmed}.
"""


def render_summary() -> str:
    rows = [
        "# Lee–Tarver library audit",
        "",
        "| Composition | Source | ρ0 g/cm³ | T0 K | Product EOS | Unreacted EOS | Kinetics | Units | p0 Mbar | Status |",
        "|---|---|---:|---:|---|---|---|---|---:|---|",
    ]
    for source in SETS.values():
        audit = audit_set(source)
        link = f"[{source.material_id}]({source.material_id.replace('(i&g)', '')}.md)"
        citation = (
            f"[source]({source.source_url})"
            if source.source_url
            else "[mixed sources](jh-2.md)"
        )
        label = "confirmed" if source.source_url else "conflicting/partial"
        density = _number(source.rho0) if source.rho0 is not None else "unknown"
        rows.append(
            f"| {link} | {citation} | {density} | {_number(source.tmp0)} | {label} | {label} | {label} | checked | {_number(audit.card_p0)} | {source.status} |"
        )
    rows.extend(
        (
            "",
            "Regenerate the source-specific cards, reports and plots with `python -m kunit.lee_tarver_report`.",
            "",
            "Status rule: verified means a traceable source and no corrections; verified_with_corrections means a traceable source and documented corrections; source_conflict means an experimental card assembled from incompatible calibrations. [Source search](source_search.md) records the unresolved JH-2 and PBXN-109 evidence. [Catalog changes](catalog_changes.md) records the JWL-only 8701 calibration and experimental JH-2 restoration. Correction tables and EOS plots are in each report. See [LS-DYNA R13 keyword manual](https://ftp.lstc.com/anonymous/outgoing/jday/manuals/LS-DYNA_Manual_Volume_II_R13.pdf) for the EOS 7 field meanings and [LS-DYNA Users Conference mapping](https://lsdyna.ansys.com/wp-content/uploads/attachments/blast-impact13-d.pdf) for ENQ=E0 per reference volume.",
            "",
        )
    )
    return "\n".join(rows)


def plot_svg(source: LeeTarverSet, *, release: bool = False) -> str:
    temperatures = (0.75 * source.tmp0, source.tmp0, 1.25 * source.tmp0)
    start = 1 if release else 0.5
    volumes = [start + i * (2 - start) / 150 for i in range(151)]
    curves = [[unreacted_pressure(source, v, t) for v in volumes] for t in temperatures]
    minimum, maximum = min(map(min, curves)), max(map(max, curves))
    if maximum == minimum:
        maximum += 1

    def xy(v: float, p: float) -> tuple[float, float]:
        return 70 + 580 * (v - start) / (2 - start), 335 - 275 * (p - minimum) / (
            maximum - minimum
        )

    colors = ("#2563eb", "#d97706", "#b91c1c")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="410" viewBox="0 0 700 410">',
        '<rect width="700" height="410" fill="white"/>',
        '<path d="M70 60 V335 H650" fill="none" stroke="#333"/>',
    ]
    for t, curve, color in zip(temperatures, curves, colors):
        points = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in (xy(v, p) for v, p in zip(volumes, curve))
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
    for v in (1, 1.25, 1.5, 1.75, 2) if release else (0.5, 1, 1.5, 2):
        x, _ = xy(v, minimum)
        parts.append(
            f'<text x="{x:.1f}" y="355" font-size="13" text-anchor="middle">{v:g}</text>'
        )
    for p in (minimum, 0, maximum):
        if minimum <= p <= maximum:
            _, y = xy(start, p)
            parts.append(
                f'<text x="63" y="{y + 4:.1f}" font-size="11" text-anchor="end">{p:.3g}</text>'
            )
    parts.append(
        '<text x="350" y="385" font-size="14" text-anchor="middle">Relative volume V</text>'
    )
    parts.append(
        '<text x="25" y="205" font-size="14" transform="rotate(-90 25 205)" text-anchor="middle">p (Mbar)</text>'
    )
    for i, (t, color) in enumerate(zip(temperatures, colors)):
        parts.append(
            f'<text x="{100 + 180 * i}" y="35" font-size="13" fill="{color}">T={t:g} K</text>'
        )
    parts.append(f"<title>{escape(source.title)} unreacted EOS pressure</title></svg>")
    return "\n".join(parts)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "docs/lee_tarver"
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.md").write_text(render_summary(), encoding="utf-8")
    for source in SETS.values():
        stem = source.material_id.replace("(i&g)", "")
        (root / f"{stem}.md").write_text(render_report(source), encoding="utf-8")
        (root / f"{stem}.svg").write_text(plot_svg(source), encoding="utf-8")
        (root / f"{stem}-release.svg").write_text(
            plot_svg(source, release=True), encoding="utf-8"
        )
        (root / f"{stem}.k").write_text(render_eos(source), encoding="utf-8")


if __name__ == "__main__":
    main()

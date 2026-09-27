"""Source-valued Lee–Tarver sets; pressure and energy density are in Mbar."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite

from kunit.core.fixed import join_fixed, format_lsdyna_10
from kunit.models.eos_ignition_growth import CARDS

# Alpha-RDX at 300 K: Cv=217.1 J/(mol K), Cawkwell et al. (2016), p. 4:
# https://www.osti.gov/servlets/purl/1498045
# M(RDX)=222.1163 g/mol, NIST: https://webbook.nist.gov/cgi/cbook.cgi?Name=RDX
# Converted using the JH-2 reactant reference density 1.717 g/cm3.
RDX_CVR_MBAR_PER_K = (217.1 / 0.2221163) * (1.717 * 1000) / 1e11


@dataclass(frozen=True)
class EOS:
    a: float
    b: float
    r1: float
    r2: float
    cv: float  # Mbar/K, heat capacity per reference volume
    omega: float | None = None
    legacy_thermal: float | None = None  # Mbar/K, used only without sourced omega

    @property
    def thermal(self) -> float:
        if self.omega is not None:
            return self.omega * self.cv
        if self.legacy_thermal is None:
            raise ValueError("Missing thermal coefficient")
        return self.legacy_thermal


@dataclass(frozen=True)
class Rates:
    ignition_limit: float
    i: float  # us^-1
    b: float
    x: float
    a: float
    g1: float  # Mbar^-y us^-1
    c: float
    d: float
    y: float
    growth_limit: float
    g2: float  # Mbar^-z us^-1
    e: float
    g: float
    z: float
    completion_start: float


@dataclass(frozen=True)
class LeeTarverSet:
    material_id: str
    title: str
    eosid: int
    rho0: float | None  # g/cm3; legacy MAT value if this calibration is untraced
    tmp0: float  # K
    product: EOS
    unreacted: EOS
    rates: Rates
    enq: float  # Mbar = energy per reference volume
    source: str
    source_url: str | None
    status: str
    note: str = ""
    expected_p0: float | None = None  # Mbar; None if calibration state is untraced
    units: str = "cm-g-us"


SETS = {
    item.material_id: item
    for item in (
        LeeTarverSet(
            "tnt(i&g)",
            "tnt",
            11,
            1.61,
            298,
            EOS(3.712, 0.032306, 4.15, 0.95, 1e-5, 0.3),
            EOS(17.98, -0.931, 6.2, 3.1, 2.05e-5, 0.8926),
            Rates(1, 50, 0.222, 4, 0, 0, 0, 0, 0, 1, 40, 0.222, 0.667, 1.2, 0),
            0.070,
            "FOI-R--0151--SE, Table 1 (cast TNT); DRDC TM 2013-4015 for Bp precision",
            "https://www.foi.se/rest-api/report/FOI-R--0151--SE",
            "verified_with_corrections",
            "Two-term calibration from Lee and Tarver (1980, doi:10.1063/1.862940); G2 card slot carries its sole growth term. DRDC reports Bp=0.032306 Mbar: https://publications.gc.ca/collections/collection_2019/rddc-drdc/D68-6-401-2014-eng.pdf",
            expected_p0=0,
        ),
        LeeTarverSet(
            "pbx-9501(i&g)",
            "pbx 9501",
            91,
            1.838,
            298,
            EOS(16.689, 0.5969, 5.9, 2.1, 1e-5, 0.45),
            EOS(7320, -0.052654, 14.1, 1.41, 2.7806e-5, 0.8867),
            Rates(
                0.3,
                1.4e11,
                0.667,
                20,
                0,
                130,
                0.667,
                0.277,
                2,
                0.5,
                400,
                0.333,
                1,
                2,
                0.5,
            ),
            0.095,
            "Tarver et al., Manganin Gauge and Reactive Flow Modeling Study of PBX 9501, Table 1, 25 C",
            "https://digital.library.unt.edu/ark:/67531/metadc1407555/",
            "verified_with_corrections",
            "The 50 C and 150 C calibrations have different unreacted B and must remain separate.",
            expected_p0=0,
        ),
        # Murphy et al. (1993), Table 1, LANL Comp B column; no parameters from
        # its distinct Military Comp B (rho=1.630) column are mixed into this set.
        LeeTarverSet(
            "comp-b-lanl(i&g)",
            "LANL Comp B",
            1114,
            1.712,
            298,
            EOS(5.242, 0.07678, 4.2, 1.1, 1e-5, 0.34),
            EOS(778.1, -0.05031, 11.3, 1.13, 2.487e-5, 0.8938),
            Rates(0.3, 44, 2 / 9, 4, 0.01, 414, 2 / 9, 2 / 3, 2, 1, 0, 0, 0, 0, 1),
            0.085,
            "Murphy, Lee, Weston and Williams (1993), Modeling Shock Initiation in Composition B, Table 1, LANL Comp B column",
            "https://www.osti.gov/servlets/purl/10175213",
            "verified",
            "Two-term rate law: the second growth term is zero. Distinct from Military Comp B at rho=1.630 in the adjacent column; neither tensile limits nor mixture algorithm were published in Table 1.",
            expected_p0=0,
        ),
        # Murphy et al. (1993), Table 1, PBX-9404 column. This is the
        # two-term G1=850 variant, not the later G2=495 variant (Hussain et al.).
        LeeTarverSet(
            "pbx-9404(i&g)",
            "PBX 9404",
            1115,
            1.842,
            298,
            EOS(8.524, 0.1802, 4.6, 1.3, 1e-5, 0.38),
            EOS(9522, -0.05944, 14.1, 1.41, 2.781e-5, 0.8867),
            Rates(0.3, 44, 2 / 9, 4, 0.01, 850, 2 / 9, 2 / 3, 2, 1, 0, 0, 0, 0, 1),
            0.102,
            "Murphy, Lee, Weston and Williams (1993), Modeling Shock Initiation in Composition B, Table 1, PBX-9404 column",
            "https://www.osti.gov/servlets/purl/10175213",
            "verified",
            "Published unreacted omega=0.8867. A later reprint gives 0.3 and G2=495 for a different rate variant; those values are inconsistent with this initial state and are not mixed here.",
            expected_p0=0,
        ),
        # Experimental legacy card, not a single published calibration:
        # Zhu et al. (2022), Table 2: product JWL/E0 at rho=1.667;
        # https://www.sciengine.com/parse/pdf/2096-2304/B0290F3EBF5E4846B7046AB9E2778AD4.pdf
        # Awan et al. (2024), Tables 2-3: reactant omega and rates at rho=1.717;
        # https://wydawnictwa.ipo.lukasiewicz.gov.pl/wp-content/uploads/2024/11/CEJEM-1327-v0-Huang.pdf
        # Awan et al., Aerospace (2024), Tables 4-5 repeat the reactant/rates.
        # Table 2 is JWL for the threat shaped charge, not the target I&G EOS:
        # https://www.researchgate.net/publication/381763413_Application_of_Lee-Tarver_Model_for_Energetic_Materials_Safety_Assessment_Utilized_in_Aerospace_Applications
        # Hong et al. (2020), Table 2, independently prints B=+0.0328 Mbar:
        # https://doi.org/10.1016/j.dt.2019.04.007
        # CVR uses the pure-RDX room-temperature estimate above, not a JH-2
        # calibration. CVP, T0 and reaction limits retain legacy values.
        # G1/G2 pressure units are inferred from the article's Mbar EOS and
        # the legacy card; the rate table does not label their units.
        LeeTarverSet(
            "jh-2(i&g)",
            "jh2",
            1111,
            1.717,
            298,
            EOS(6.125, 0.1395, 4.5, 1.4, 1e-5, 0.25),
            EOS(310, 0.0328, 11.3, 1.13, RDX_CVR_MBAR_PER_K, 0.8938),
            Rates(
                0.022,
                4e6,
                0.667,
                7,
                0.022,
                140,
                0.667,
                0.329,
                2,
                1,
                1000,
                0.067,
                0.333,
                3,
                0,
            ),
            0.09,
            "Composite experimental card: [Zhu et al. (2022), Table 2](https://www.sciengine.com/parse/pdf/2096-2304/B0290F3EBF5E4846B7046AB9E2778AD4.pdf); [Hong et al. (2020), Tables 1-3](https://doi.org/10.1016/j.dt.2019.04.007); [Awan et al., Aerospace (2024), Tables 4-5](https://www.researchgate.net/publication/381763413_Application_of_Lee-Tarver_Model_for_Energetic_Materials_Safety_Assessment_Utilized_in_Aerospace_Applications); [Cawkwell et al. (2016), p. 4](https://www.osti.gov/servlets/purl/1498045) for pure RDX CVR; pre-audit kunit card for remaining fields",
            None,
            "source_conflict",
            "Product EOS and ENQ are from a 1.667 g/cm3 8701 calibration; unreacted EOS and kinetics are reported at 1.717 g/cm3. Hong et al. report a different product JWL for 8701 at 1.72 g/cm3, but no CVP/CVR. Reactant B now follows Hong and Awan (+0.0328 Mbar). CVR is a pure-RDX room-temperature estimate, not a JH-2 calibration; CVP, T0 and reaction limits retain legacy values. This combination produces about 1.89 GPa initial pressure at 298 K and is not a validated initiation card.",
        ),
        LeeTarverSet(
            "ultrafine-tatb(i&g)",
            "ultrafine tatb",
            1112,
            1.80,
            298,
            EOS(12.05026, 0.602513, 6.2, 2.2, 1e-5, 0.5),
            EOS(632.07, -0.04472, 11.3, 1.13, 2.487e-5, 0.8938),
            Rates(
                0.071,
                4e6,
                0.667,
                7,
                0.22,
                2200,
                0.667,
                1,
                2,
                1,
                60,
                0.667,
                0.667,
                1,
                0.8,
            ),
            0.069,
            "LLNL, Ignition and Growth parameters for LX-17 and ultrafine TATB, Table 1B",
            "https://www.osti.gov/servlets/purl/15016041",
            "verified_with_corrections",
            "Published source gives omega_e=0.8938; R3 is calculated from omega_e Cv.",
            expected_p0=0,
        ),
        LeeTarverSet(
            "lx-17(i&g)",
            "lx17",
            1113,
            1.905,
            298,
            EOS(14.8105, 0.6379, 6.2, 2.2, 1e-5, 0.5),
            EOS(778.1, -0.05031, 11.3, 1.13, 2.487e-5, 0.8938),
            Rates(
                0.02,
                4e6,
                0.667,
                7,
                0.22,
                4600,
                0.667,
                1,
                3,
                0.8,
                30,
                0.667,
                0.667,
                1,
                0.8,
            ),
            0.069,
            "LLNL, Ignition and Growth parameters for LX-17 and ultrafine TATB, Table 1A",
            "https://www.osti.gov/servlets/purl/15016041",
            "verified_with_corrections",
            "25 C LX-17; do not substitute the older LX-17/PBX-9502 calibration at rho=1.895.",
            expected_p0=0,
        ),
    )
}


def card_fields(source: LeeTarverSet) -> dict[str, float | int]:
    p, e, r = source.product, source.unreacted, source.rates
    return {
        "eosid": source.eosid,
        "a": p.a,
        "b": p.b,
        "xp1": p.r1,
        "xp2": p.r2,
        "frer": r.b,
        "g": p.thermal,
        "r1": e.a,
        "r2": e.b,
        "r3": e.thermal,
        "r5": e.r1,
        "r6": e.r2,
        "fmxig": r.ignition_limit,
        "freq": r.i,
        "grow1": r.g1,
        "em": r.y,
        "ar1": r.d,
        "es1": r.c,
        "cvp": p.cv,
        "cvr": e.cv,
        "eetal": r.x,
        "ccrit": r.a,
        "enq": source.enq,
        "tmp0": source.tmp0,
        "grow2": r.g2,
        "ar2": r.g,
        "es2": r.e,
        "en": r.z,
        "fmxgr": r.growth_limit,
        "fmngr": r.completion_start,
    }


def render_eos(source: LeeTarverSet) -> str:
    values = card_fields(source)
    lines = ["*EOS_IGNITION_AND_GROWTH_OF_REACTION_IN_HE_TITLE\n", f"{source.title}\n"]
    for row in CARDS:
        lines.append(
            "$#"
            + "".join(f"{name if name != '_' else '':>10}" for name in row).rstrip()
            + "\n"
        )
        lines.append(
            join_fixed(
                [
                    (
                        str(values[name])
                        if name == "eosid"
                        else format_lsdyna_10(values[name]) if name != "_" else ""
                    )
                    for name in row
                ]
            )
        )
    return "".join(lines)


@dataclass(frozen=True)
class Audit:
    p0: float
    card_p0: float
    omega_p: float
    omega_e: float
    card_omega_p: float
    card_omega_e: float
    first_nonpositive_bulk: tuple[float, float] | None
    nonfinite: bool
    issues: tuple[str, ...]


def unreacted_pressure(
    source: LeeTarverSet, volume: float, temperature: float
) -> float:
    e = source.unreacted
    return (
        e.a * exp(-e.r1 * volume)
        + e.b * exp(-e.r2 * volume)
        + e.thermal * temperature / volume
    )


def adiabatic_bulk(source: LeeTarverSet, volume: float, temperature: float) -> float:
    e = source.unreacted
    omega = e.thermal / e.cv
    return (
        volume * (e.a * e.r1 * exp(-e.r1 * volume) + e.b * e.r2 * exp(-e.r2 * volume))
        + omega * (1 + omega) * e.cv * temperature / volume
    )


def audit_set(source: LeeTarverSet) -> Audit:
    first = None
    nonfinite = False
    for step in range(31):
        v = 0.5 + step * 0.05
        for t in (0.75 * source.tmp0, source.tmp0, 1.25 * source.tmp0):
            p = unreacted_pressure(source, v, t)
            bulk = adiabatic_bulk(source, v, t)
            nonfinite |= not (isfinite(p) and isfinite(bulk))
            if bulk <= 0 and first is None:
                first = (v, t)
    p0 = unreacted_pressure(source, 1, source.tmp0)
    omega_p = source.product.thermal / source.product.cv
    omega_e = source.unreacted.thermal / source.unreacted.cv
    card = {
        name: float(format_lsdyna_10(value))
        for name, value in card_fields(source).items()
    }
    card_p0 = (
        card["r1"] * exp(-card["r5"])
        + card["r2"] * exp(-card["r6"])
        + card["r3"] * card["tmp0"]
    )
    card_omega_p = card["g"] / card["cvp"]
    card_omega_e = card["r3"] / card["cvr"]
    issues = []
    if not 0 <= card_omega_p <= 2:
        issues.append("product omega outside plausible range")
    if not 0 <= card_omega_e <= 2:
        issues.append("unreacted omega outside plausible range")
    if (
        source.product.omega is not None
        and abs(card_omega_p - source.product.omega) > 1e-3
    ):
        issues.append("product omega differs from source")
    if (
        source.unreacted.omega is not None
        and abs(card_omega_e - source.unreacted.omega) > 1e-3
    ):
        issues.append("unreacted omega differs from source")
    if abs(card_p0 - (source.expected_p0 or 0)) > 1e-5:
        issues.append("large initial pressure residual")
    if nonfinite:
        issues.append("nonfinite EOS value")
    return Audit(
        p0,
        card_p0,
        omega_p,
        omega_e,
        card_omega_p,
        card_omega_e,
        first,
        nonfinite,
        tuple(issues),
    )

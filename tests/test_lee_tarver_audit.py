import math
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from kunit.api import convert_string
from kunit.core.fixed import split_fixed
from kunit.core.units import BASE_SYSTEMS, scale_factor
from kunit.lee_tarver import SETS, adiabatic_bulk, audit_set, render_eos
from kunit.materials_store import MaterialStore
from kunit.lee_tarver_report import CORRECTIONS, render_report, render_summary, plot_svg


ROOT = Path(__file__).resolve().parents[1] / "kunit/web/materials"
REPORTS = Path(__file__).resolve().parents[1] / "docs/lee_tarver"


def _cards(text):
    rows = []
    for line in text.splitlines():
        try:
            float(split_fixed(line)[0])
        except ValueError:
            continue
        rows.append(split_fixed(line))
    return rows


class LeeTarverAuditTests(unittest.TestCase):
    def test_catalog_replaces_untraced_sets_with_sourced_calibrations(self):
        records = {
            record.material_id: record
            for record in MaterialStore(ROOT).list_materials()
        }
        for removed in ("pbxn-109(i&g)",):
            self.assertNotIn(removed, records)
            self.assertNotIn(removed, SETS)
        # Zhu et al. (2022), Table 2 and Awan et al. (2024), Tables 2-3:
        # different-density branches must remain flagged as source_conflict.
        jh2 = records["jh-2(i&g)"]
        self.assertEqual(jh2.eos.payload, render_eos(SETS["jh-2(i&g)"]))
        self.assertEqual(SETS["jh-2(i&g)"].status, "source_conflict")
        self.assertAlmostEqual(SETS["jh-2(i&g)"].rho0, 1.717)
        self.assertIn(
            "large initial pressure residual", audit_set(SETS["jh-2(i&g)"]).issues
        )
        self.assertIn("source_conflict", render_report(SETS["jh-2(i&g)"]))
        self.assertIn("Zhu", render_report(SETS["jh-2(i&g)"]))
        self.assertIn("Awan", render_report(SETS["jh-2(i&g)"]))
        # Awan et al., Aerospace 2024, Tables 2/4/5: Table 2 is for the
        # threat shaped charge, not a complete I&G product branch for the target.
        self.assertIn("381763413", str(jh2.references))
        self.assertIn("threat shaped charge", render_report(SETS["jh-2(i&g)"]))
        for material_id, density in (
            ("comp-b-lanl(i&g)", 1.712),
            ("pbx-9404(i&g)", 1.842),
        ):
            self.assertIn(material_id, records)
            self.assertEqual(
                records[material_id].eos.payload, render_eos(SETS[material_id])
            )
            self.assertAlmostEqual(SETS[material_id].rho0, density)
            self.assertTrue(SETS[material_id].source_url)
            self.assertFalse(audit_set(SETS[material_id]).issues)
        rdx = records["rdx-8701"]
        self.assertEqual(rdx.eos.model, "eos-jwl")
        self.assertAlmostEqual(
            float(split_fixed(rdx.material.payload.splitlines()[-1])[1]), 1.667
        )
        self.assertTrue(rdx.reference.startswith("https://"))
        # Zhu et al. (2022), Table 2: rho, D, PCJ and product JWL.
        self.assertEqual(
            [float(value) for value in _cards(rdx.material.payload)[0][:4]],
            [1111, 1.667, 0.8425, 0.2966],
        )
        self.assertEqual(
            [float(value) for value in _cards(rdx.eos.payload)[0][:7]],
            [1111, 6.125, 0.1395, 4.5, 1.4, 0.25, 0.09],
        )
        converted_mat = convert_string(
            rdx.material.payload, src="cm-g-us", dst="mm-mg-us", models="mat-he-burn"
        )
        self.assertEqual(float(_cards(converted_mat)[0][2]), 8.425)
        self.assertEqual(float(_cards(converted_mat)[0][3]), 29.66)
        converted = convert_string(
            rdx.eos.payload, src="cm-g-us", dst="mm-mg-us", models="eos-jwl"
        )
        self.assertEqual(float(_cards(converted)[0][1]), 612.5)
        self.assertEqual(float(_cards(converted)[0][6]), 9)
        # LANL LA-UR-14-24860 confirms the RDX/wax composition, not this JWL.
        comp_a3 = records["comp_a3"]
        self.assertEqual(comp_a3.eos.model, "eos-jwl")
        self.assertIn("LA-UR-14-24860", str(comp_a3.references))
        self.assertIn("не установлен", comp_a3.comment)
        # Existing JWL card is a separate, untraced legacy variant; Murphy's
        # 1.712 g/cm3 LANL calibration must not overwrite its 1.717 g/cm3 RO.
        comp_b = records["comp_b"]
        self.assertEqual(
            [float(value) for value in _cards(comp_b.material.payload)[0][:4]],
            [1, 1.717, 0.7989, 0.295],
        )
        self.assertEqual(
            [float(value) for value in _cards(comp_b.eos.payload)[0][:7]],
            [1, 5.2413, 0.07678, 4.2, 1.1, 0.34, 0.085],
        )
        self.assertIsNone(comp_b.reference)

    def test_every_library_set_has_source_and_generated_card(self):
        records = {
            record.material_id: record
            for record in MaterialStore(ROOT).list_materials()
            if record.eos and record.eos.model == "eos-ignition-growth"
        }
        self.assertEqual(set(records), set(SETS))
        for material_id, record in records.items():
            source = SETS[material_id]
            self.assertTrue(source.source_url or source.status == "source_conflict")
            self.assertIsNotNone(source.product.omega)
            self.assertIsNotNone(source.unreacted.omega)
            self.assertEqual(record.eos.payload, render_eos(source))
            self.assertEqual(record.eos.units, source.units)
            self.assertTrue(
                all(
                    len(line) == 80
                    for line in record.eos.payload.splitlines()
                    if _cards(line)
                )
            )
            if record.sections[0].kind == "material":
                density = float(
                    split_fixed(record.material.payload.splitlines()[-1])[1]
                )
                self.assertAlmostEqual(density, source.rho0)

    def test_verified_thermodynamics_and_initial_state(self):
        for source in SETS.values():
            result = audit_set(source)
            self.assertTrue(math.isfinite(result.p0))
            if source.status != "source_conflict":
                self.assertLess(abs(result.p0), 2e-4)
            self.assertFalse(result.nonfinite)
            self.assertGreater(adiabatic_bulk(source, 1, source.tmp0), 0)
            if source.status != "source_conflict":
                self.assertIsNotNone(result.first_nonpositive_bulk)
            if source.product.omega is not None:
                self.assertAlmostEqual(result.omega_p, source.product.omega, places=6)
            if source.unreacted.omega is not None:
                self.assertAlmostEqual(result.omega_e, source.unreacted.omega, places=6)
        self.assertAlmostEqual(SETS["tnt(i&g)"].unreacted.omega, 0.8926)
        self.assertEqual(SETS["pbx-9501(i&g)"].rho0, 1.838)
        self.assertEqual(SETS["pbx-9501(i&g)"].tmp0, 298.0)

    def test_jh2_literature_sign_and_rdx_heat_capacity_flag_initial_pressure(self):
        # Hong et al. (2020), Table 2: B=+0.0328 Mbar for 8701.
        # Cawkwell et al. (2016), p. 4: alpha-RDX Cv=217.1 J/(mol K).
        # NIST: RDX molar mass 222.1163 g/mol.
        source = SETS["jh-2(i&g)"]
        self.assertEqual(source.unreacted.b, 0.0328)
        rdx_cv_mbar_per_k = 217.1 / 0.2221163 * (source.rho0 * 1000) / 1e11
        self.assertAlmostEqual(source.unreacted.cv, rdx_cv_mbar_per_k)
        audit = audit_set(source)
        self.assertGreater(audit.card_p0, 0.018)
        self.assertIn("large initial pressure residual", audit.issues)

    def test_card_coefficients_follow_published_omega_and_exponents(self):
        for source in SETS.values():
            rows = _cards(render_eos(source))
            self.assertAlmostEqual(
                float(rows[0][6]) / float(rows[2][2]),
                source.product.thermal / source.product.cv,
                delta=2e-5,
            )
            self.assertAlmostEqual(
                float(rows[1][1]) / float(rows[2][3]),
                source.unreacted.thermal / source.unreacted.cv,
                delta=2e-5,
            )
            p0 = (
                float(rows[0][7]) * math.exp(-float(rows[1][2]))
                + float(rows[1][0]) * math.exp(-float(rows[1][3]))
                + float(rows[1][1]) * float(rows[2][7])
            )
            self.assertAlmostEqual(p0, audit_set(source).p0, delta=2e-7)
            self.assertAlmostEqual(p0, audit_set(source).card_p0, delta=1e-12)
        self.assertEqual(float(_cards(render_eos(SETS["pbx-9501(i&g)"]))[2][0]), 0.277)
        for material_id in ("ultrafine-tatb(i&g)", "lx-17(i&g)"):
            row = _cards(render_eos(SETS[material_id]))[2]
            self.assertEqual((float(row[0]), float(row[1])), (1, 0.667))

    def test_source_units_round_trip_and_kinetic_invariance(self):
        src = BASE_SYSTEMS["cm-g-us"]
        dst = BASE_SYSTEMS["mm-mg-us"]
        pressure_scale = scale_factor(src, dst, (1, -1, -2))
        for source in SETS.values():
            original = render_eos(source)
            forward = convert_string(
                original, src=source.units, dst="mm-mg-us", models="eos-ignition-growth"
            )
            backward = convert_string(
                forward, src="mm-mg-us", dst=source.units, models="eos-ignition-growth"
            )
            old_rows = _cards(original)
            new_rows = _cards(forward)
            back_rows = _cards(backward)
            self.assertEqual(len(old_rows), 4)
            for old, back in zip(old_rows, back_rows):
                for left, right in zip(old, back):
                    if left.strip():
                        self.assertAlmostEqual(
                            float(left),
                            float(right),
                            delta=max(1e-7, abs(float(left)) * 3e-5),
                        )
            self.assertAlmostEqual(
                float(new_rows[2][2]),
                float(old_rows[2][2]) * pressure_scale,
                delta=1e-7,
            )
            self.assertAlmostEqual(
                float(new_rows[2][3]),
                float(old_rows[2][3]) * pressure_scale,
                delta=1e-7,
            )
            for rate, exponent, row, column in (
                (source.rates.g1, source.rates.y, 1, 6),
                (source.rates.g2, source.rates.z, 3, 0),
            ):
                converted = float(new_rows[row][column])
                self.assertAlmostEqual(
                    rate * 0.1**exponent,
                    converted * (0.1 * pressure_scale) ** exponent,
                    delta=max(1e-7, abs(rate) * 1e-6),
                )

    def test_time_and_pressure_rate_conversion(self):
        source = SETS["lx-17(i&g)"]
        rows = _cards(
            convert_string(
                render_eos(source),
                src="cm-g-us",
                dst="mm-mg-ms",
                models="eos-ignition-growth",
            )
        )
        old = BASE_SYSTEMS["cm-g-us"]
        new = BASE_SYSTEMS["mm-mg-ms"]
        pressure = scale_factor(old, new, (1, -1, -2))
        frequency = scale_factor(old, new, (0, 0, -1))
        self.assertAlmostEqual(float(rows[1][5]), source.rates.i * frequency)
        self.assertAlmostEqual(
            float(rows[1][6]),
            source.rates.g1 * frequency / pressure**source.rates.y,
            delta=1e-12,
        )
        self.assertAlmostEqual(
            float(rows[3][0]),
            source.rates.g2 * frequency / pressure**source.rates.z,
            delta=1e-12,
        )
        self.assertAlmostEqual(float(rows[2][6]), source.enq * pressure)

    def test_changed_density_is_rejected(self):
        source = (ROOT / "high_explosives.toml").read_text()
        with TemporaryDirectory() as directory:
            Path(directory, "high_explosives.toml").write_text(
                source.replace("        11      1.61", "        11      1.63")
            )
            with self.assertRaisesRegex(
                ValueError, "differs from Lee-Tarver calibration"
            ):
                MaterialStore(directory).list_materials()

    def test_nonstring_source_id_is_rejected(self):
        source = (ROOT / "high_explosives.toml").read_text()
        with TemporaryDirectory() as directory:
            Path(directory, "high_explosives.toml").write_text(
                source.replace('source_id = "tnt(i&g)"', 'source_id = ["tnt(i&g)"]')
            )
            with self.assertRaisesRegex(ValueError, "Unknown Lee-Tarver source"):
                MaterialStore(directory).list_materials()

    def test_reference_cards(self):
        expected = (
            Path(__file__).parent / "fixtures/lee_tarver_reference.k"
        ).read_text()
        self.assertEqual(
            expected, "".join(render_eos(source) for source in SETS.values())
        )

    def test_published_reports_match_source_data(self):
        self.assertEqual((REPORTS / "summary.md").read_text(), render_summary())
        for source in SETS.values():
            stem = source.material_id.replace("(i&g)", "")
            self.assertEqual(
                (REPORTS / f"{stem}.md").read_text(), render_report(source)
            )
            self.assertEqual((REPORTS / f"{stem}.k").read_text(), render_eos(source))
            self.assertEqual((REPORTS / f"{stem}.svg").read_text(), plot_svg(source))
            self.assertEqual(
                (REPORTS / f"{stem}-release.svg").read_text(),
                plot_svg(source, release=True),
            )

    def test_status_matches_evidence(self):
        for source in SETS.values():
            status = (
                "source_conflict"
                if source.material_id == "jh-2(i&g)"
                else (
                    "verified_with_corrections"
                    if source.material_id in CORRECTIONS
                    else "verified"
                )
            )
            self.assertEqual(source.status, status)

    def test_unphysical_thermal_ratio_is_flagged(self):
        source = SETS["tnt(i&g)"]
        broken = replace(source, product=replace(source.product, omega=3.0))
        self.assertIn("product omega outside plausible range", audit_set(broken).issues)

    def test_reports_include_provenance_mapping_and_domain_warning(self):
        report = render_report(SETS["tnt(i&g)"])
        self.assertIn("FOI-R--0151--SE", report)
        self.assertIn("R3/CVR", report)
        self.assertIn("0.8926", report)
        self.assertIn("GROW2", report)
        self.assertIn("c²", report)
        self.assertIn("17.98", report)
        self.assertIn("p_p =", report)
        self.assertIn("p_e =", report)
        self.assertIn("Automated flags", report)
        self.assertIn("card p0", report)
        self.assertIn("Density consistency", report)
        self.assertIn("Confirmed / corrected / disputed / unconfirmed", report)
        self.assertIn("verified_with_corrections", render_summary())
        self.assertIn("comp-b-lanl(i&g)", render_summary())
        self.assertIn("pbx-9404(i&g)", render_summary())
        svg = plot_svg(SETS["tnt(i&g)"])
        self.assertEqual(svg.count("<polyline"), 3)
        ElementTree.fromstring(svg)
        self.assertEqual(plot_svg(SETS["tnt(i&g)"], release=True).count("<polyline"), 3)
        self.assertNotIn("TNT uses", render_report(SETS["lx-17(i&g)"]))


if __name__ == "__main__":
    unittest.main()

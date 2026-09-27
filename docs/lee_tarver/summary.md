# Lee–Tarver library audit

| Composition | Source | ρ0 g/cm³ | T0 K | Product EOS | Unreacted EOS | Kinetics | Units | p0 Mbar | Status |
|---|---|---:|---:|---|---|---|---|---:|---|
| [tnt(i&g)](tnt.md) | [source](https://www.foi.se/rest-api/report/FOI-R--0151--SE) | 1.61 | 298 | confirmed | confirmed | confirmed | checked | 1.1594122e-06 | verified_with_corrections |
| [pbx-9501(i&g)](pbx-9501.md) | [source](https://digital.library.unt.edu/ark:/67531/metadc1407555/) | 1.838 | 298 | confirmed | confirmed | confirmed | checked | -7.6880897e-08 | verified_with_corrections |
| [comp-b-lanl(i&g)](comp-b-lanl.md) | [source](https://www.osti.gov/servlets/purl/10175213) | 1.712 | 298 | confirmed | confirmed | confirmed | checked | -1.8876251e-07 | verified |
| [pbx-9404(i&g)](pbx-9404.md) | [source](https://www.osti.gov/servlets/purl/10175213) | 1.842 | 298 | confirmed | confirmed | confirmed | checked | 8.418545e-07 | verified |
| [jh-2(i&g)](jh-2.md) | [mixed sources](jh-2.md) | 1.717 | 298 | conflicting/partial | conflicting/partial | conflicting/partial | checked | 0.018901097 | source_conflict |
| [ultrafine-tatb(i&g)](ultrafine-tatb.md) | [source](https://www.osti.gov/servlets/purl/15016041) | 1.8 | 298 | confirmed | confirmed | confirmed | checked | -1.2509891e-06 | verified_with_corrections |
| [lx-17(i&g)](lx-17.md) | [source](https://www.osti.gov/servlets/purl/15016041) | 1.905 | 298 | confirmed | confirmed | confirmed | checked | -1.8876251e-07 | verified_with_corrections |

Regenerate the source-specific cards, reports and plots with `python -m kunit.lee_tarver_report`.

Status rule: verified means a traceable source and no corrections; verified_with_corrections means a traceable source and documented corrections; source_conflict means an experimental card assembled from incompatible calibrations. [Source search](source_search.md) records the unresolved JH-2 and PBXN-109 evidence. [Catalog changes](catalog_changes.md) records the JWL-only 8701 calibration and experimental JH-2 restoration. Correction tables and EOS plots are in each report. See [LS-DYNA R13 keyword manual](https://ftp.lstc.com/anonymous/outgoing/jday/manuals/LS-DYNA_Manual_Volume_II_R13.pdf) for the EOS 7 field meanings and [LS-DYNA Users Conference mapping](https://lsdyna.ansys.com/wp-content/uploads/attachments/blast-impact13-d.pdf) for ENQ=E0 per reference volume.

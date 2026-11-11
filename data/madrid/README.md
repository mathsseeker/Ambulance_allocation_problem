# Madrid instance: district Fuencarral – El Pardo (SAMUR-Protección Civil)

One Madrid district for the ambulance relocation model. Areas `V` are the 8 official barrios of the
district. Bases `J` are the official SAMUR-PC bases in the district **and in its neighbouring
districts** (`BASES = "distrito_y_limitrofes"`). Same index convention as `data/edmonton/`:
`j` = base (1..8), `v` = area (1..8), times in minutes.

## Why this district

The user asked for "the district that best fits the project scope". The project uses T = 30 min (with
T in {10, 15, 20, 30} for sensitivity) and the pip Gurobi licence (≤ 2000 variables/constraints).
All 21 districts were screened with the same pipeline (barrio centroids, district + neighbour bases, OSRM):

| District | barrios | bases | % areas covered T = 8 / 15 / 30 | mean share of bases within 15 min |
|---|---|---|---|---|
| **Fuencarral – El Pardo** | 8 | 9* | 62.5 / 75 / 100 | **0.44** |
| Moncloa – Aravaca | 7 | 10 | 71 / 100 / 100 | 0.73 |
| Latina | 7 | 9 | 71 / 86 / 100 | 0.62 |
| the other 18 districts | 3–9 | 3–11 | ≥ 67 / ≥ 67 / 100 | 0.67–1.00 |

\*The screening counted Ciudad Lineal as a neighbour; see "Neighbouring districts" below (final: 8 bases).

Fuencarral – El Pardo is the largest district (238 km²) and the least trivial one: travel times spread
from 2 to 30 min, so coverage depends on which bases are occupied. Every compact central district is
covered by almost every base within 15 min.

## Sources

All downloads on **2026-11-11** (UTC). Exact URLs, HTTP status and timestamps are in `download_log.txt`.
Originals are in `raw/` and have not been modified.

| Raw file | Dataset / page | URL | Licence |
|---|---|---|---|
| `Barrios.zip` (SHP), `Barrios.csv` | *Barrios municipales de Madrid* (datos.madrid.es 300496-0); files dated 2026-09-18 | https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Barrios/Barrios.zip | CC BY 4.0 |
| `Distritos.zip` (SHP) | *Límites administrativos actuales*, districts (900012-0); limits as in BOCM 12-07-2021 | https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Distritos/Distritos.zip | CC BY 4.0 |
| `poblacion_distrito_barrio.csv` + `_estructura.pdf` | *Población por distrito y barrio a 1 de enero* (300557-0), padrón municipal; latest date **1 Jan 2026** | https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio | CC BY 4.0 |
| `samur_activaciones_2025.csv` + `samur_activaciones_estructura.pdf` | *Activaciones del SAMUR-Protección Civil* (300178-0), year **2025** (latest complete year; 2026 is Jan–Jun only) | https://datos.madrid.es/dataset/300178-0-samur-activaciones | CC BY 4.0 |
| `samur_bases_madrid_es.json` | madrid.es page *Bases operativas* (list + map with coordinates) and page *Bases operativas en Madrid* (table with district) | see `source_*` keys inside the file | No licence stated on the pages (madrid.es web content) |
| `nominatim_base26.json` | OpenStreetMap Nominatim search, 1 query | https://nominatim.openstreetmap.org/ | ODbL (© OpenStreetMap contributors) |
| `osrm_table_08.json` | OSRM demo server `table` service, car profile, 1 query (2026-11-11T18:36:34Z) | https://router.project-osrm.org/ | OSM data ODbL; demo server for light use only |

Cite: Ayuntamiento de Madrid, Portal de Datos Abiertos (datos.madrid.es), CC BY 4.0.

**Open data check for bases:** datos.madrid.es has **no** dataset with the SAMUR bases. Searches for
`samur`, `bases samur`, `proteccion civil`, `emergencias`, `ambulancia` and `sedes` find only activations,
vehicles, surveys and training. The vehicles dataset (300597-0) has no base field (columns: Nº Municipal,
Tipo, Propietario, Fecha Matriculación). The official base list with **coordinates** is on madrid.es (the
`Bases operativas` page has `data-latitude`/`data-longitude` for each of its 25 bases). madrid.es answers
HTTP 403 to scripted downloads, so the values were read from the page in a browser and saved verbatim in
`samur_bases_madrid_es.json` (the page HTML itself is not stored).

## Real format of the raw files

| File | Format |
|---|---|
| `Barrios.zip` | ESRI shapefile, polygons, 131 barrios, CRS **ETRS89 / UTM 30N (EPSG:25830)**, metres, `.cpg` = UTF-8. Fields: CODDIS, NOMDIS, COD_BAR (e.g. `81` = district 8, barrio 1), NOMBRE, COD_DIS_TX, BARRIO_MAY, COD_DISBAR, NUM_BAR, BARRIO_MT, AREA (m²). |
| `Barrios.csv` | Same attributes without geometry, `;` separator, UTF-8 with BOM, CRLF, decimal comma in AREA. 131 rows. |
| `Distritos.zip` | ESRI shapefile, 21 districts, EPSG:25830, UTF-8. Fields: COD_DIS, COD_DIS_TX, NOMBRE, DISTRI_MAY, DISTRI_MT, AREA. |
| `poblacion_distrito_barrio.csv` | `;` separator, UTF-8 with BOM, CRLF. Columns: fecha (text, `1 de enero de 2026`), cod_municipio, municipio, cod_distrito, distrito (leading space), cod_barrio (same code as COD_BAR), barrio, num_personas, num_personas_hombres, num_personas_mujeres. **Counts use `.` as thousands separator** (`23.410` = 23,410). 131 barrios × 9 years (2018–2026). |
| `samur_activaciones_2025.csv` | `;` separator, UTF-8 with BOM, CRLF, 150,643 rows. Columns: Año, Mes (Spanish month name, upper case), Hora Solicitud (`H:MM:SS`, time the resource was activated), Hora Intervención (`H:MM:SS`, arrival at the incident; blank = cancelled activation), Código (incident type, text), Distrito (upper case, no accents, e.g. `FUENCARRAL - EL PARDO`), Hospital (blank = no transport). **No day and no location below district.** 1,044 rows have no district; 206 are outside the municipality. |
| `samur_bases_madrid_es.json` | Written for this project: one object per base with the page's `data-name`, `data-direction`, `data-latitude`, `data-longitude` (WGS84 degrees, as text) plus the address and district from the second page's table. |
| `osrm_table_08.json` | OSRM response: `durations` (s) and `distances` (m), 8 sources (bases) × 16 destinations (8 bases, then 8 area centroids); `destinations[].distance` = snapping distance (m). `_request` / `_points` store the URL, time and input points. |

## Processed files (`processed/`)

| File | Column | How it was obtained | Original / derived |
|---|---|---|---|
| `areas.csv` | `v` | 1..8, barrios in COD_BAR order (81..88) | index |
| | `barrio`, `cod_barrio` | NOMBRE, COD_BAR from the shapefile | original |
| | `population` | `num_personas` at 1 Jan 2026 | original |
| | `d_v` | population / district total (256,037) | **derived** |
| | `lat`, `lon` | area centroid of the official polygon, computed in EPSG:25830, converted to WGS84 | **derived** |
| | `area_km2` | polygon area | derived |
| | `osrm_snap_m` | distance OSRM moved the centroid to reach a road | from OSRM |
| | `method` | text stating the above | — |
| `bases.csv` | `j` | 1 = the base inside the district, then neighbours by SAMUR number | index |
| | `name`, `samur_base`, `address` | `data-name`, number, `data-direction` from madrid.es | original |
| | `district` | district from the madrid.es table | original |
| | `C_j` | **estimate** = 5 for every base (see "Capacity" below) | **estimated** (`C_j_method`) |
| | `C_j_method` | text of the estimate rule | — |
| | `lat`, `lon` | madrid.es `data-latitude` / `data-longitude` | original (`method = official_coordinates_madrid_es`) |
| | `in_district` | 1 if `district` = Fuencarral – El Pardo | derived |
| | `district_point_in_polygon` | district polygon that contains (lat, lon), as a check | derived |
| | `osrm_snap_m` | OSRM snapping distance (5.8–21.1 m for all bases) | from OSRM |
| `t_base_area.csv` | `t_min` | OSRM car duration base → area centroid, s / 60 | **derived** (`method = osrm_driving_demo_server_free_flow_no_sirens`) |
| | `dist_km` | OSRM road distance | derived |
| `g_base_base.csv` | `g_min` | OSRM car duration base → base, s / 60; `g(j,j) = 0` | **derived** (`method` as above, `zero_diagonal` on the diagonal) |
| `demand_profile.csv` | `dimension, key, label` | `month` 1–12 or `hour` 0–23 (hour of *Hora Solicitud*) | — |
| | `activations` | number of 2025 records with Distrito = `FUENCARRAL - EL PARDO` | original counts |
| | `activations_with_arrival` | same, with non-blank *Hora Intervención* (not cancelled) | original counts |
| | `share` | activations / total of that dimension | derived |
| `params.json` | | district, neighbours, `n_areas` = 8, `n_bases` = 8, population date, SAMUR year and summary, OSRM query time | — |

`checks.json` (next to this README) holds every number in the checks section. `scripts/build_madrid.py`
rebuilds `processed/` from `raw/`. It needs `shapely`, `pyshp`, `pyproj` and `pandas`, which are **not**
in the project venv. It reuses the cached OSRM response unless the points change.

### Areas (1 Jan 2026)

| v | barrio | population | d_v | nearest base (min) |
|---|---|---|---|---|
| 1 | El Pardo | 3,472 | 0.0136 | 20.5 |
| 2 | Fuentelarreina | 3,567 | 0.0139 | 4.7 |
| 3 | Peñagrande | 45,120 | 0.1762 | 2.1 |
| 4 | Pilar | 46,659 | 0.1822 | 2.4 |
| 5 | La Paz | 31,835 | 0.1243 | 5.0 |
| 6 | Valverde | 67,737 | 0.2646 | 13.2 |
| 7 | Mirasierra | 37,918 | 0.1481 | 5.1 |
| 8 | El Goloso | 19,729 | 0.0771 | 16.6 |

Barrio names in the shapefile and in the population file match exactly (codes 81–88).

### Bases

Neighbouring districts = districts that share **more than 50 m** of border with Fuencarral – El Pardo:
Moncloa – Aravaca (13.4 km), Hortaleza (3.5 km), Tetuán (2.6 km), Chamartín (2.0 km).
Ciudad Lineal touches the district at a single point (2 m of common boundary) and is **not** counted.

| j | SAMUR base | district | method |
|---|---|---|---|
| 1 | Base 16 – Isla Tabarca | Fuencarral – El Pardo | official_coordinates_madrid_es |
| 2 | Base 0 – Base Central y Casa de Córdoba | Moncloa – Aravaca | official_coordinates_madrid_es |
| 3 | Base 3 – Federico Salmón | Chamartín | official_coordinates_madrid_es |
| 4 | Base 6 – Pirineos | Moncloa – Aravaca | official_coordinates_madrid_es |
| 5 | Base 7 – La Estrella | Moncloa – Aravaca | official_coordinates_madrid_es |
| 6 | Base 10 – Infanta Mercedes | Tetuán | official_coordinates_madrid_es |
| 7 | Base 11 – Arequipa | Hortaleza | official_coordinates_madrid_es |
| 8 | Base 13 – Avenida de Valladolid | Moncloa – Aravaca | official_coordinates_madrid_es |

**Number of bases:** `solo_distrito` → **1** base (Base 16). `distrito_y_limitrofes` → **8** bases (used).

**Capacity `C_j` (estimated, not official).** No source gives the number of ambulances per base:
madrid.es lists the unit types (USVA, USVB, USVB-PC, UPSQ) and crews but not where they are parked,
and the vehicles dataset has no base field. Web search (2026-11-11) found only city-wide figures:

| Figure | Value | Source |
|---|---|---|
| Operational fleet, 31 Dec 2024 | **51 SVA + 68 SVB = 119 ambulances** (+ 2 UPSQ, 32 VIR, ...) | madrid.es, *Parque de vehículos. Ambulancias* (official): https://www.madrid.es/portales/munimadrid/es/Inicio/Seguridad-y-emergencias/SAMUR-Proteccion-Civil/?vgnextfmt=default&vgnextoid=c88fcdb1bfffa010VgnVCM100000d90ca8c0RCRD&vgnextchannel=f9cd31d3b28fe410VgnVCM1000000b205a0aRCRD&idCapitulo=10269430 |
| New supply contract (until 2030) | 52 SVB + 28 SVA (99 vehicles incl. 18 VIR, 1 UPSQ) | diario.madrid.es press release: https://diario.madrid.es/blog/notas-de-prensa/la-junta-de-gobierno-autoriza-el-nuevo-contrato-de-suministro-de-ambulancias-de-samur-proteccion-civil-con-99-nuevos-vehiculos-nueve-mas-que-ahora/ |
| Official bases | 25 | madrid.es *Bases operativas* (above) |
| Base 0 | 7,500 m², hosts "el parque operativo de ambulancias" | svasamur.com (unofficial): https://svasamur.com/samur-pc/bases-operativas/ |

**Rule:** `C_j = round(119 / 25) = round(4.76) = 5` for every base (`C_j_method =
estimated_uniform: ...`). It spreads the official operational fleet evenly over the official bases.
It is an upper-bound-style figure: the fleet includes vehicles in reserve or maintenance, so fewer
units are on duty at any time. Base 0 is clearly larger than the others, but no number is published,
so it was **not** given a larger value. The experiments also run with the project default `C_j = 2`
as a tight-capacity sensitivity case.

## Demand

`d_v` = barrio population / district population, as in van Buuren et al. (population-based demand).

SAMUR activations, 2025, Fuencarral – El Pardo (district level only; **not** used to split demand
between barrios):

- 6,648 activations (4.4 % of the city's 150,643); 531 cancelled (blank *Hora Intervención*); 57 with blank *Hora Solicitud* (left out of the hourly profile).
- By month: from 403 (August, 6.1 %) to 653 (October, 9.8 %).
- By hour: lowest 04:00–05:59 (55 per hour, 0.8 %), highest 13:00–13:59 (520, 7.9 %); 10:00–20:59 each at least 5.3 %.
- **Response time** = *Hora Intervención* − *Hora Solicitud* (activation → arrival), n = 6,117 non-cancelled records with both times. The file has no date, so 28 negative differences are taken as crossing midnight (+24 h). This is an assumption (`method` noted in `params.json`).
  min 0, p10 4.55, p25 6.85, **median 9.25**, mean 10.12, p75 11.93, p90 15.12, p95 18.0, p99 29.13, max 425.7 min (7 records > 120 min, probably data errors, kept).
  Share ≤ 8 min: 36.5 %; ≤ 15 min: 89.6 %; ≤ 30 min: 99.1 %.

## Checks

**Demand:** Σ d_v = 1.000000. No missing values in `areas.csv`, `t_base_area.csv` or `g_base_base.csv`.

| | min | median | max |
|---|---|---|---|
| `t_min` (64 pairs) | 2.06 | 14.99 | 29.94 |
| `g_min` (56 off-diagonal pairs) | 0.89 | 11.38 | 23.00 |

`g` is not symmetric (largest |g(j,j2) − g(j2,j)| = 1.68 min, one-way streets). It has no triangle
inequality violations. The smallest g (0.89 min) is Base 0 ↔ Base 7, two bases about 300 m apart.

**Deterministic coverage, `t_min ≤ T`** (8 bases):

| T (min) | % areas with ≥ 1 base | % demand with ≥ 1 base | mean # bases covering an area | areas covered by all 8 bases |
|---|---|---|---|---|
| 8 | 62.5 % | 64.5 % | 1.25 | 0 |
| 10 | 62.5 % | 64.5 % | 2.38 | 0 |
| 15 | 75.0 % | 90.9 % | 4.00 | 0 |
| 20 | 87.5 % | 98.6 % | 6.13 | 5 |
| 30 | 100 % | 100 % | **8.00** | **8** |

Uncovered areas: at T = 8 and 10, El Pardo, Valverde and El Goloso; at T = 15, El Pardo and El Goloso;
at T = 20, El Pardo (20.5 min).

**Triviality warning: at T = 30 the instance is trivial.** Every area is covered by every base, so any
placement gives full coverage. The 2T = 60 min bound can never bind either. The instance is useful for
T = 10, 15 or 20 min. T = 15 is the best balance: 2 uncovered areas, 4 of 8 bases per area on average,
no area covered by all bases. Remember that these are free-flow car times without sirens, and that the
observed SAMUR median response time in the district is 9.25 min (activation to arrival).

**Size:** 8 areas, 8 bases. 1 base inside the district: with `solo_distrito` there would be fewer
than 3 bases and relocation would be pointless. With neighbours there are 8.

## Oddities and decisions

- **Base 26 (Buenos Aires)** has *exactly* the coordinates of Base 2 (San Bernardo, Centro) on madrid.es,
  and its postcode 28015 is San Bernardo's (Av. de Buenos Aires is in 28018, Puente de Vallecas). This looks
  like a copy error on the page. The build replaces it with the Nominatim result (40.3842604, −3.6532300,
  street-level match, no house number; `method = geocoded_street_level_nominatim`). **Base 26 is not in
  this instance** (Puente de Vallecas does not border Fuencarral – El Pardo). It matters only if another
  district is built.
- The two madrid.es pages differ on some addresses: Base 9 (Antonio López 142 vs. Hermenegildo Bielsa 1),
  Base 12 (Brujas 38 vs. 34), Base 14 (Casuarina 10 vs. 4), Base 17 (Las Santeras 39 vs. La Huerta de los
  Rueda 37), Base 0 (Ronda de las Provincias 4-6-7 vs. 7), Base 6 (Francos Rodríguez 77 / entrance
  Pirineos 1). The coordinates come from the page that has them. None of these bases except 0 and 6 is in this instance.
- Base 15 (Colón) is listed in Salamanca, but its point falls just inside Centro (Plaza de Colón is on the
  border). The official district is kept. It is not in this instance.
- Numbers 18 and 24 are missing in the official list (25 bases, numbered 0–26).
- **El Pardo centroid**: the barrio is 188 km², mostly the Monte de El Pardo. Its polygon centroid lies in
  the forest, and OSRM snaps it **1,571 m** to an unnamed track (−3.7803, 40.5427), probably a restricted
  forest road. The El Pardo times (20.5–29.9 min) are therefore only rough. The village of El Pardo, where
  the population lives, is elsewhere in the polygon. Valverde (28.9 m) and El Goloso (2.3 m) also snap to
  unnamed roads, but close by. A population-weighted point (e.g. from the census-section layer) would be
  better. It was **not** done, to stick to the requested definition.

## Limitations

1. **Demand is population, not calls.** SAMUR data exist only by district, so `d_v` reflects residents, not
   where emergencies happen. Commuters, traffic accidents and night-life are not represented.
2. **Travel times are free-flow car times** from OSRM on OpenStreetMap (demo server): no sirens, no traffic,
   no time of day, no dispatch or turnout delay. **No standard deviation** is available, and none was invented.
3. **SAMUR-PC covers only public roads and public places** in the municipality of Madrid. Home emergencies
   are handled by SUMMA 112 (Comunidad de Madrid). Population-based demand therefore over-weights
   residential barrios relative to SAMUR's real workload.
4. Centroids are geometric, not population-weighted (see the El Pardo note).
5. Base coordinates come from a madrid.es web page with no stated licence and one visible error (Base 26).
6. `C_j` is an estimate (uniform 5, from the city-wide fleet), not an official per-base figure.
7. The SAMUR file has no day of the month, so response times across midnight are inferred.

## Model R on this instance

Code: `src/ambulance/madrid.py` (`load_madrid`, `generate_madrid_instance`, same generator rules as
Fez-Meknes) and `scripts/madrid_robust.py` (Base / H / E / R grid). Results:
`results/madrid_robust.csv`, `_summary.csv`, `_report.txt`. Tests: `tests/test_madrid.py`.

Grid: T ∈ {10, 15, 20, 30}, α ∈ {.95, .97, .99}, cv ∈ {.1, .2, .3}, |I| ∈ {2, 4, 6, 8, 12, 16},
|S| ∈ {0, 2}, M ∈ {2, |I|}, C ∈ {5 (estimate), 2}, 10 seeds → 17,280 instances × 4 models in 31.5 s.
Largest model: 265 variables, 41 constraints (well inside the pip licence). No time-limit hits.

| | Base / H / E | Model R |
|---|---|---|
| plan found, M = 2 | 77.1 % | **95.8 %** (= every instance meeting the capacity guarantee) |
| plan found, M = \|I\| | 95.8 % | 95.8 % |
| mean extra moves above M (M = 2) | — | 0.43 |
| overtime minutes | 0 | 0 |
| 2T violations (H, E, R) | 0 | 0 |

- All 1,620 instances that strict E cannot solve at M = 2 fail because more than M ambulances are
  forced to move (sleeping base or shift rule). Model R solves them with the minimum extra moves
  (in 90 % of its plans, extra moves = forced moves − M exactly; the rest come from C = 2).
- Where both have a plan, R and E give the same coverage (max difference 1·10⁻⁵).
- **The 2T rule never conflicts with anything here**: H is feasible whenever Base is. At T = 10, 2 of
  8 areas (El Pardo, El Goloso) are outside V2 (no base reaches them within 20 min with prob. α); at
  T = 15, 0.44 on average; at T ≥ 20, none. So in Madrid, f1 and f2 are always 0 and Model R's only
  effect is the soft move limit.
- 720 instances fail the capacity guarantee, all with |I| = 16, C = 2 and |S| = 2 (6 awake bases × 2
  = 12 free places < 16); every model refuses them, as expected. With the estimate C = 5 none fails.
- Coverage (Model R, M = 2): 0.63 at T = 10, 0.87 at T = 15, 0.98 at T = 20, 0.99 at T = 30 —
  confirming that T = 30 is nearly trivial on this instance.

## Not included

No scenario data (ambulance positions, home bases, shift minutes, sleeping crews). These come from the
instance generator.

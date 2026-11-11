"""Build the Madrid (one district) instance from the files in data/madrid/raw/.

Usage (needs shapely, pyshp, pyproj, pandas; not in the project venv):
    python data/madrid/scripts/build_madrid.py [--district "Fuencarral - El Pardo"]

The OSRM response is cached in raw/osrm_table_<code>.json. If it is missing the
script queries the public OSRM demo server once (router.project-osrm.org).
"""
import argparse, io, json, statistics as st, time, urllib.request, zipfile
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import Transformer
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "raw", ROOT / "processed"
UA = "opti3-ambulance-relocation-student-project/1.0"
MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
          "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
POP_DATE = "1 de enero de 2026"
SAMUR_YEAR = 2025
# Base 26: the official page repeats the coordinates of Base 2 (see README).
# Nominatim result for "17 Avenida de Buenos Aires, Madrid" (street-level match, no house number).
BASE26_GEOCODE = (40.3842604, -3.6532300)
# Capacity C_j: NO per-base official figure exists. Estimate = official operational fleet of
# ambulances (madrid.es "Parque de vehículos. Ambulancias", 31 Dec 2024: 51 SVA + 68 SVB = 119)
# divided by the 25 official bases, rounded: 119 / 25 = 4.76 -> 5, the same for every base.
FLEET_SVA, FLEET_SVB, N_BASES_OFFICIAL = 51, 68, 25
C_EST = round((FLEET_SVA + FLEET_SVB) / N_BASES_OFFICIAL)
C_METHOD = (f"estimated_uniform: round(({FLEET_SVA} SVA + {FLEET_SVB} SVB operational on 2024-12-31) "
            f"/ {N_BASES_OFFICIAL} bases)")

to_wgs = Transformer.from_crs(25830, 4326, always_xy=True)
to_utm = Transformer.from_crs(4326, 25830, always_xy=True)


def read_shp(zip_path, stem):
    z = zipfile.ZipFile(zip_path)
    files = {ext: io.BytesIO(z.read(f"{stem}.{ext}")) for ext in ("shp", "shx", "dbf")}
    r = shapefile.Reader(shp=files["shp"], shx=files["shx"], dbf=files["dbf"], encoding="utf-8")
    flds = [f[0] for f in r.fields[1:]]
    return [(dict(zip(flds, sr.record)), shape(sr.shape.__geo_interface__)) for sr in r.shapeRecords()]


def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return " ".join(s.replace("-", " - ").split())


def hms_to_min(s):
    if not isinstance(s, str) or not s.strip():
        return None
    h, m, sec = (int(x) for x in s.strip().split(":"))
    return h * 60 + m + sec / 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--district", default="Fuencarral - El Pardo")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    # ---------- districts, adjacency ----------
    dis = read_shp(RAW / "Distritos.zip", "DISTRITOS")
    dgeom = {int(a["COD_DIS"]): g for a, g in dis}
    dname = {int(a["COD_DIS"]): a["NOMBRE"] for a, _ in dis}
    code = [k for k, v in dname.items() if norm(v) == norm(args.district)]
    assert len(code) == 1, args.district
    code = code[0]
    # Neighbour = shares more than 50 m of border (a single touching corner does not count:
    # Fuencarral - El Pardo and Ciudad Lineal meet in one point, 2 m of common boundary).
    def border_m(a, b):
        return dgeom[a].boundary.intersection(dgeom[b].buffer(1)).length
    neigh = sorted(e for e in dgeom if e != code and dgeom[code].buffer(5).intersects(dgeom[e])
                   and border_m(code, e) > 50)
    keep = {norm(dname[code])} | {norm(dname[e]) for e in neigh}

    # ---------- areas ----------
    bar = [(a, g) for a, g in read_shp(RAW / "Barrios.zip", "BARRIOS") if int(a["CODDIS"]) == code]
    bar.sort(key=lambda x: int(x[0]["COD_BAR"]))
    pop = pd.read_csv(RAW / "poblacion_distrito_barrio.csv", sep=";", encoding="utf-8-sig", dtype=str)
    pop = pop[(pop["fecha"] == POP_DATE) & (pop["cod_distrito"].str.strip() == str(code))]
    pop_by = {int(r.cod_barrio): int(r.num_personas.replace(".", "")) for r in pop.itertuples()}
    pop_name = {int(r.cod_barrio): r.barrio.strip() for r in pop.itertuples()}
    areas = []
    for v, (a, g) in enumerate(bar, start=1):
        cb = int(a["COD_BAR"])
        c = g.centroid
        lon, lat = to_wgs.transform(c.x, c.y)
        areas.append(dict(v=v, barrio=a["NOMBRE"], cod_barrio=cb, population=pop_by[cb],
                          lat=lat, lon=lon, centroid_inside=g.contains(c),
                          area_km2=g.area / 1e6, pop_name=pop_name[cb]))
    total_pop = sum(x["population"] for x in areas)
    for x in areas:
        x["d_v"] = x["population"] / total_pop

    # ---------- bases ----------
    braw = json.loads((RAW / "samur_bases_madrid_es.json").read_text())["bases"]
    bases = []
    for b in braw:
        lat, lon = float(b["data-latitude"]), float(b["data-longitude"])
        method = "official_coordinates_madrid_es"
        if b["base"] == 26:
            lat, lon = BASE26_GEOCODE
            method = "geocoded_street_level_nominatim"
        x, y = to_utm.transform(lon, lat)
        pip = [dname[k] for k, gg in dgeom.items() if gg.contains(Point(x, y))]
        d_off = norm(b["table_district"])
        if d_off in keep:
            bases.append(dict(samur_base=b["base"], name=b["data-name"], district=b["table_district"],
                              address=b["data-direction"], lat=lat, lon=lon, method=method,
                              in_district=d_off == norm(dname[code]),
                              district_point_in_polygon=pip[0] if pip else ""))
    bases.sort(key=lambda b: (not b["in_district"], b["samur_base"]))
    for j, b in enumerate(bases, start=1):
        b["j"] = j

    # ---------- OSRM ----------
    cache = RAW / f"osrm_table_{code:02d}.json"
    nb = len(bases)
    pts = [(b["lat"], b["lon"]) for b in bases] + [(a["lat"], a["lon"]) for a in areas]
    if cache.exists() and json.loads(cache.read_text()).get("_points") != [list(p) for p in pts]:
        cache.unlink()  # base or area set changed
    if not cache.exists():
        coords = ";".join(f"{lon:.7f},{lat:.7f}" for lat, lon in pts)
        url = (f"https://router.project-osrm.org/table/v1/driving/{coords}?sources="
               + ";".join(map(str, range(nb))) + "&annotations=duration,distance")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = json.load(urllib.request.urlopen(req, timeout=60))
        assert resp["code"] == "Ok", resp
        resp["_request"] = {"url": url, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        resp["_points"] = [list(p) for p in pts]
        cache.write_text(json.dumps(resp, indent=1))
    resp = json.loads(cache.read_text())
    dur, dist = resp["durations"], resp["distances"]
    for i, w in enumerate(resp["destinations"]):
        (bases[i] if i < nb else areas[i - nb])["osrm_snap_m"] = w["distance"]

    tm = "osrm_driving_demo_server_free_flow_no_sirens"
    t_rows = [dict(j=b["j"], v=a["v"], t_min=dur[b["j"] - 1][nb + a["v"] - 1] / 60, method=tm,
                   dist_km=dist[b["j"] - 1][nb + a["v"] - 1] / 1000) for b in bases for a in areas]
    g_rows = []
    for b in bases:
        for b2 in bases:
            same = b["j"] == b2["j"]
            g_rows.append(dict(j=b["j"], j2=b2["j"], g_min=0.0 if same else dur[b["j"] - 1][b2["j"] - 1] / 60,
                               method="zero_diagonal" if same else tm,
                               dist_km=0.0 if same else dist[b["j"] - 1][b2["j"] - 1] / 1000))

    # ---------- SAMUR ----------
    sm = pd.read_csv(RAW / f"samur_activaciones_{SAMUR_YEAR}.csv", sep=";", encoding="utf-8-sig", dtype=str)
    sd = sm[sm["Distrito"].fillna("").map(norm) == norm(dname[code])].copy()
    sd["sol"] = sd["Hora Solicitud"].map(hms_to_min)
    sd["itv"] = sd["Hora Intervención"].map(hms_to_min)
    sd["hour"] = sd["sol"].map(lambda m: None if m is None or pd.isna(m) else int(m // 60))
    sd["month"] = sd["Mes"].map(lambda m: MONTHS.index(m.strip().upper()) + 1)
    sd["arrived"] = sd["itv"].notna()
    prof = []
    n_all = len(sd)
    for m in range(1, 13):
        s = sd[sd["month"] == m]
        prof.append(dict(dimension="month", key=m, label=MONTHS[m - 1].capitalize(), activations=len(s),
                         activations_with_arrival=int(s["arrived"].sum()), share=len(s) / n_all,
                         method="count_of_records"))
    with_h = sd[sd["hour"].notna()]
    for h in range(24):
        s = with_h[with_h["hour"] == h]
        prof.append(dict(dimension="hour", key=h, label=f"{h:02d}:00-{h:02d}:59", activations=len(s),
                         activations_with_arrival=int(s["arrived"].sum()), share=len(s) / len(with_h),
                         method="count_of_records_by_hour_of_Hora_Solicitud"))
    rt = sd[sd["sol"].notna() & sd["itv"].notna()].copy()
    rt["rt"] = rt["itv"] - rt["sol"]
    n_wrap = int((rt["rt"] < 0).sum())
    rt.loc[rt["rt"] < 0, "rt"] += 1440  # crossed midnight (no date in the file)
    r = rt["rt"].sort_values().tolist()
    q = lambda p: r[min(len(r) - 1, int(p * (len(r) - 1)))]
    samur = dict(year=SAMUR_YEAR, district_label=sd["Distrito"].iloc[0], activations=n_all,
                 city_activations=len(sm), blank_hora_solicitud=int(sd["sol"].isna().sum()),
                 blank_hora_intervencion_cancelled=int((~sd["arrived"]).sum()),
                 response_time_min=dict(n=len(r), n_midnight_wrap=n_wrap, min=r[0], p10=q(.1), p25=q(.25),
                                        median=q(.5), mean=sum(r) / len(r), p75=q(.75), p90=q(.9),
                                        p95=q(.95), p99=q(.99), max=r[-1],
                                        share_le_8=sum(x <= 8 for x in r) / len(r),
                                        share_le_15=sum(x <= 15 for x in r) / len(r),
                                        share_le_30=sum(x <= 30 for x in r) / len(r),
                                        n_gt_120=sum(x > 120 for x in r)))

    # ---------- write ----------
    pd.DataFrame([dict(v=a["v"], barrio=a["barrio"], population=a["population"], d_v=f"{a['d_v']:.10f}",
                       lat=f"{a['lat']:.7f}", lon=f"{a['lon']:.7f}", cod_barrio=a["cod_barrio"],
                       area_km2=f"{a['area_km2']:.3f}", osrm_snap_m=f"{a['osrm_snap_m']:.1f}",
                       method="lat/lon=centroid of official barrio polygon (EPSG:25830->4326); "
                              "d_v=population/district total")
                  for a in areas]).to_csv(OUT / "areas.csv", index=False)
    pd.DataFrame([dict(j=b["j"], name=b["name"], district=b["district"], C_j=C_EST,
                       lat=f"{b['lat']:.7f}", lon=f"{b['lon']:.7f}", method=b["method"],
                       C_j_method=C_METHOD,
                       samur_base=b["samur_base"], address=b["address"], in_district=int(b["in_district"]),
                       district_point_in_polygon=b["district_point_in_polygon"],
                       osrm_snap_m=f"{b['osrm_snap_m']:.1f}") for b in bases]).to_csv(OUT / "bases.csv", index=False)
    pd.DataFrame(t_rows).to_csv(OUT / "t_base_area.csv", index=False, float_format="%.6f")
    pd.DataFrame(g_rows).to_csv(OUT / "g_base_base.csv", index=False, float_format="%.6f")
    pd.DataFrame(prof).to_csv(OUT / "demand_profile.csv", index=False, float_format="%.6f")
    params = dict(city="Madrid", district=dname[code], district_code=code,
                  neighbour_districts=[dname[e] for e in neigh], bases_scope="distrito_y_limitrofes",
                  n_areas=len(areas), n_bases=nb, n_bases_in_district=sum(b["in_district"] for b in bases),
                  population_date=POP_DATE.replace("1 de enero de ", "") + "-01-01", population_total=total_pop,
                  samur_year=SAMUR_YEAR, samur=samur, time_unit="minutes",
                  travel_time_source="OSRM demo server (router.project-osrm.org), car profile, OSM data",
                  osrm_query_utc=resp["_request"]["utc"],
                  capacity_C_j=dict(value=C_EST, method=C_METHOD, official_per_base="not available",
                                    source="https://www.madrid.es/portales/munimadrid/es/Inicio/Seguridad-y-emergencias/"
                                           "SAMUR-Proteccion-Civil/?vgnextfmt=default&vgnextoid=c88fcdb1bfffa010VgnVCM100000d90ca8c0RCRD"
                                           "&vgnextchannel=f9cd31d3b28fe410VgnVCM1000000b205a0aRCRD&idCapitulo=10269430",
                                    accessed="2026-11-11"))
    (OUT / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False))

    # ---------- checks ----------
    T = {(r["j"], r["v"]): r["t_min"] for r in t_rows}
    tv = [r["t_min"] for r in t_rows]
    gv = [r["g_min"] for r in g_rows if r["j"] != r["j2"]]
    asym = max(abs(dur[i][k] - dur[k][i]) / 60 for i in range(nb) for k in range(nb))
    tri = sum(1 for a in range(nb) for b in range(nb) for c in range(nb)
              if len({a, b, c}) == 3 and dur[a][c] > dur[a][b] + dur[b][c] + 1e-6)
    cov = {}
    for Tm in (8, 10, 15, 20, 30):
        n = {a["v"]: sum(T[(b["j"], a["v"])] <= Tm for b in bases) for a in areas}
        cov[Tm] = dict(pct_areas=100 * sum(c > 0 for c in n.values()) / len(areas),
                       pct_demand=100 * sum(a["d_v"] for a in areas if n[a["v"]] > 0),
                       mean_bases_per_area=sum(n.values()) / len(areas),
                       areas_covered_by_all=sum(c == nb for c in n.values()),
                       per_area=n)
    near = {a["barrio"]: min(T[(b["j"], a["v"])] for b in bases) for a in areas}
    checks = dict(sum_d_v=sum(a["d_v"] for a in areas),
                  missing=dict(areas=int(pd.read_csv(OUT / "areas.csv")[["population", "d_v", "lat", "lon"]].isna().sum().sum()),
                               t=sum(x is None for x in tv), g=sum(x is None for x in gv)),
                  t_min=dict(min=min(tv), median=st.median(tv), max=max(tv)),
                  g_min=dict(min=min(gv), median=st.median(gv), max=max(gv), max_asym=asym, triangle_violations=tri),
                  coverage=cov, nearest_base_min=near,
                  pop_names_match={a["barrio"]: a["pop_name"] for a in areas})
    (ROOT / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(dict(params=params, checks=checks), indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

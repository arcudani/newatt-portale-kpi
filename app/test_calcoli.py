"""
Test del motore KPI (bp_calcoli), dei formati (formato) e della coerenza
catalogo <-> calcoli <-> registro viste. Offline, su dati FITTIZI.

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_calcoli.py
"""
from __future__ import annotations

import bp_calcoli as bc
import bp_import as bi
import dati_prova as dp
import formato as fmt
import registro_moduli

_BP = bi.leggi_bp(dp.workbook_bp())
D = bc.Dati(_BP.ce, _BP.driver)


def test_formato():
    assert fmt.eur_compatto(147115717.7) == "147 M€"
    assert fmt.eur_compatto(20893943.7) == "20,9 M€"
    assert fmt.eur_compatto(4057997.6) == "4,06 M€"
    assert fmt.eur_compatto(591039.96) == "591 k€"
    assert fmt.eur_compatto(-0.2) == "0 €"
    assert fmt.numero(-0.0001) == "0" and fmt.numero(1234567.891, 2) == "1.234.567,89"
    assert fmt.pct(0.194) == "19,4%" and fmt.pct(None) == "n.d." and fmt.pct(float("nan")) == "n.d."
    assert fmt.formatta_delta(1.2e6, 0.058, "€") == "+1,20 M€ · +5,8%"
    assert fmt.formatta_delta(-0.021, None, "%") == "-2,1 pp"
    assert fmt.formatta(None, "€") == ("n.d.", "")
    assert fmt.formatta(158.4, "€/PdP") == ("158", "€/PdP")
    assert fmt.formatta_hero(20893943.7, "€") == ("20,9", "M€")
    assert fmt.formatta_hero(591039.96, "€") == ("591", "k€")
    assert fmt.formatta_hero(0.386, "%") == ("38,6", "%")
    assert fmt.formatta_hero(42.3, "€/PdP") == ("42", "€ / PdP")
    assert fmt.segno(0.004, fmt.numero(0.4, 1)) == "+0,4", "il + serve anche sotto l'unità"
    assert fmt.segno(0.0, fmt.numero(0.0, 1)) == "0,0", "niente + su uno zero"
    assert fmt.mese_label(2027, 3) == "mar 27"
    assert fmt.periodo_label(2027, 1, 12) == "anno 2027"
    assert fmt.periodo_label(2027, 1, 6) == "gen–giu 2027"
    print("OK - formati italiani (M€/k€, %, pp, n.d., mai -0)")


def test_semaforo_direzionale():
    assert bc.confronta(100, 103, "€", 1, 5, 10).stato == "ok"
    assert bc.confronta(100, 93, "€", 1, 5, 10).stato == "warn"
    assert bc.confronta(100, 88, "€", 1, 5, 10).stato == "crit"
    assert bc.confronta(100, 120, "€", 1, 5, 10).stato == "ok", "favorevole = ok"
    assert bc.confronta(30, 32.5, "€/PdP", -1, 5, 10).stato == "warn", "CtS che sale"
    assert bc.confronta(30, 27, "€/PdP", -1, 5, 10).stato == "ok", "CtS che scende"
    assert bc.confronta(0.40, 0.36, "%", 1, 3, 6).stato == "warn", "-4 punti"
    assert bc.confronta(0.40, 0.33, "%", 1, 3, 6).stato == "crit", "-7 punti"
    assert bc.confronta(0.80, 0.86, "%", 0, 3, 6).stato == "warn", "neutro: conta lo scarto"
    assert bc.confronta(None, 1, "€", 1, 5, 10).stato == "neutral"
    # voci CE: i costi sono negativi, un costo che scende è favorevole
    assert bc.stato_voce(-100, -90).stato == "ok"
    assert bc.stato_voce(-100, -112).stato == "crit"
    print("OK - semaforo con soglia e direzione (no ±10% unico)")


def test_kpi_fittizi():
    p = bc.Periodo(2028)
    m = bc.calcola("L3_RICAVI", D, p)
    assert abs(m.valore - dp._annuo(dp.RICAVI, 2028)) < 1e-6 and len(m.serie) == 12
    m26 = bc.calcola("L3_CTS", D, bc.Periodo(2026))
    assert m26.valore is None and "avviamento" in m26.motivo, "2026 = avviamento -> n.d."
    costi = -sum(dp._annuo(f, 2028) for f in (dp.MKT, dp.SRV, dp.SOFT, dp.PERS))
    medi = sum(dp.PDP_TOT(2028, mm) for mm in range(1, 13)) / 12
    assert abs(bc.calcola("L3_CTS", D, p).valore - costi / medi) < 1e-6
    assert abs(bc.calcola("L3_PDP", D, bc.Periodo(2028, 6)).valore - dp.PDP_TOT(2028, 6)) < 1e-6
    retail = sum(dp.STOCK[("Retail", c)](2028, 12) for c in ("Power", "Gas"))
    assert abs(bc.calcola("L3_MIX", D, p).valore - retail / dp.PDP_TOT(2028, 12)) < 1e-9
    assert bc.calcola("V3_AVANZAMENTO", D, bc.Periodo(2028, 6)).valore < 1
    assert abs(bc.calcola("V3_AVANZAMENTO", D, p).valore - 1) < 1e-9
    pen = bc.calcola("V4_PENETRAZIONE", D, p).valore
    assert abs(pen - dp.VAS_TOT(2028, 12) / dp.PDP_TOT(2028, 12)) < 1e-9
    churn = bc.calcola("L3_CHURN", D, p)
    assert churn.valore > 0 and "ipotesi" in churn.sub
    assert bc.calcola("V5_RECLAMI", D, p) is None, "segnaposto senza calcolo"
    assert bc.calcola("L3_RICAVI", bc.dati_vuoti(), p).valore is None
    assert bc.anno_default(D, 2026) == 2027, "2026 senza ricavi -> primo anno con ricavi"
    print("OK - KPI su dati fittizi (CtS su PdP medi, mix, penetrazione, avviamento n.d.)")


def test_kpi_primo_livello():
    """I 12 KPI del Cruscotto fissati da Migliora (bp004)."""
    p = bc.Periodo(2028)
    medi = sum(dp.PDP_TOT(2028, mm) for mm in range(1, 13)) / 12
    # Costo per cliente = tutto ciò che separa il primo margine lordo dall'EBITDA
    costo = bc.calcola("L3_COSTO_CLIENTE", D, p)
    assert abs(costo.valore - (D.voce("pm_lordo", p) - D.voce("ebitda", p)) / medi) < 1e-6
    assert costo.valore > bc.calcola("L3_CTS", D, p).valore and "Cost-to-Serve" in costo.sub
    assert not costo.nota, "la riga BP è quella del Cost-to-Serve, non del costo per cliente"
    # Sales plan: un solo KPI; senza consuntivo niente percentuale ma l'obiettivo
    # del BP, totale nel motivo e per commodity nel dettaglio
    s = bc.calcola("L3_SALES", D, p)
    obiettivi = {com: D.flusso("produzione", p, canale="Agenti", commodity=com)
                 for com in ("Power", "Gas")}
    assert s.valore is None and all(v > 0 for v in obiettivi.values())
    assert f"obiettivo BP {fmt.numero(sum(obiettivi.values()))} contratti" in s.rif, s.rif
    assert s.commodity_valori == {"Power": None, "Gas": None}, "percentuale con il consuntivo"
    assert s.commodity == {"Power": f"{fmt.numero(obiettivi['Power'])} POD",
                           "Gas": f"{fmt.numero(obiettivi['Gas'])} PDR"}, s.commodity
    assert "non prevede" in bc.calcola("L3_SALES", D, bc.Periodo(2026)).motivo
    # Churn: un solo KPI (tutti i clienti) con il dettaglio LTM per commodity
    churn = bc.calcola("L3_CHURN", D, p)
    assert set(churn.commodity) == {"Power", "Gas"}
    for com in ("Power", "Gas"):
        cessati = D.flusso("switch_out", p, canale="Agenti", commodity=com)
        base = sum(D.stock("pdp_attivi", 2028, mm, canale="Agenti", commodity=com)
                   for mm in range(1, 13)) / 12
        assert churn.commodity[com] == fmt.pct(cessati / base), (com, churn.commodity)
        assert abs(churn.commodity_valori[com] - cessati / base) < 1e-9, "valore per lo slicer"
    m26 = bc.calcola("L3_CHURN", D, bc.Periodo(2026))
    assert "avviamento" in m26.motivo and not m26.commodity, "nel 2026 niente dettaglio"
    # CLT: un solo KPI, il dettaglio divide le commodity (dati dal CRM, fase 4)
    clt = bc.calcola("L3_CLT", D, p)
    assert clt.valore is None and set(clt.commodity) == {"Power", "Gas"}
    divisi = {"L3_CHURN_EE", "L3_CHURN_GAS", "L3_SALES_EE", "L3_SALES_GAS"}
    assert divisi.isdisjoint(bc.CALCOLI), "nessun KPI per singola commodity: sta nel dettaglio"
    print("OK - KPI di primo livello: costo per cliente, sales plan (obiettivo BP), "
          "churn e CLT unici con dettaglio per commodity")


def test_badge_e_avvisi():
    """Badge sotto il numero e pillole: sono ciò che fa risaltare il KPI."""
    t = bc.tendenza("L3_RICAVI", D, bc.Periodo(2028), "€", 1)
    assert t and t.testo.startswith("▲") and t.tono == "buono" and "vs 2027" in t.testo
    assert bc.tendenza("L3_RICAVI", D, bc.Periodo(2027), "€", 1).testo == "primo anno operativo"
    # benchmark del catalogo: Cost-to-Serve oltre l'intervallo sano
    b = bc.avviso_benchmark(42.0, "€/PdP", -1, 10, 15)
    assert b.tono == "cattivo" and "×" in b.testo and "10–15 €" in b.testo
    assert bc.avviso_benchmark(12.0, "€/PdP", -1, 10, 15).tono == "buono"
    # obiettivo minimo su una percentuale (penetrazione VAS)
    b = bc.avviso_benchmark(0.395, "%", 1, 0.45, None)
    assert b.tono == "cattivo" and "5,5 pt" in b.testo and "45%" in b.testo
    # target con due estremi e direzione neutra (mix Retail/Business)
    assert bc.avviso_benchmark(0.947, "%", 0, 0.75, 0.85).tono == "attenzione"
    assert bc.avviso_benchmark(None, "%", 1, 0.45, None) is None
    assert bc.avviso_benchmark(1.0, "%", 1, None, None) is None, "senza benchmark niente pillola"
    # trend: solo cali consecutivi su KPI dove più alto è meglio
    giu = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, .5, .2]
    assert "in calo da" in bc.avviso_trend(giu, 2028, 12, 1).testo
    assert bc.avviso_trend(giu, 2028, 12, -1) is None, "sui costi la crescita non è un allarme"
    assert bc.avviso_trend(list(range(1, 13)), 2028, 12, 1) is None
    # gap FTE: avviso portato dal KPI stesso
    fte = bc.calcola("V5_FTE_CC", D, bc.Periodo(2028))
    assert fte.avvisi and fte.avvisi[0].tono in ("cattivo", "attenzione")
    print("OK - badge di tendenza, avvisi da benchmark, trend in calo, gap FTE")


def test_aggregazioni():
    w = bc.waterfall(D, bc.Periodo(2029))
    assert abs(w.iloc[-2]["fine"] - w.iloc[-1]["valore"]) < 1e-6, "il ponte arriva all'utile"
    t = bc.ce_sintetico(D, None, bc.Periodo(2028), 1)
    assert (t["livello"] == 1).all() and "ebitda" in set(t["codice"])
    b = bc.Dati(_BP.ce.assign(importo=_BP.ce["importo"] * 0.85), _BP.driver)
    t2 = bc.ce_sintetico(D, b, bc.Periodo(2028), 1).set_index("codice")
    assert t2.loc["ricavi", "stato"] == "crit", "ricavi -15% = critico"
    assert t2.loc["costi_appr", "stato"] == "ok", "costi -15% = favorevole"
    m = bc.matrice_scostamenti(D, D, 2026, 1)
    assert set(m["mese"]) == {10, 11, 12}, "nel 2026 solo ott-dic"
    vuota = bc.matrice_scostamenti(D, None, 2026, 1)
    assert vuota.empty and "codice" in vuota.columns, "vuota ma con le colonne"
    f = bc.cts_per_famiglia(D, [2028])
    assert {"Personale", "IT", "Contratto NeWatt", "Marketing"} <= set(f["famiglia"])
    print("OK - ponte, CE sintetico con semaforo, heatmap, CtS per famiglia")


def test_catalogo_coerente():
    cat = dp.catalogo_seed()
    assert len(cat) >= 40 and cat["codice"].is_unique
    mancanti = [c for c in cat[cat["stato"] == "attivo"]["codice"] if c not in bc.CALCOLI]
    assert not mancanti, f"KPI attivi senza calcolo: {mancanti}"
    assert set(cat["vista"]) <= set(registro_moduli.PER_CODICE)
    assert set(cat[cat["drill"] != ""]["drill"]) <= set(registro_moduli.PER_CODICE)
    v1 = cat[cat["vista"] == "V1"]
    assert len(v1) == 9, "il Cruscotto ha i 9 KPI di primo livello (bp004-bp007)"
    assert v1.groupby("ambito").size().to_dict() == {
        "Economico-finanziario": 3, "Commerciale": 2, "Cliente e servizio": 4}
    unici = {"L3_SALES", "L3_CHURN", "L3_CLT"}
    assert unici <= set(v1["codice"]), "sales plan, churn e CLT: un solo KPI (bp005-bp007)"
    assert not v1["codice"].str.endswith(("_EE", "_GAS")).any(), \
        "nessuna tessera per singola commodity: la divisione sta nel dettaglio"
    assert "dettaglio" in cat.set_index("codice").loc["L3_CHURN", "definizione"]
    assert (v1["livello"] == 3).all() and not (cat[cat["vista"] != "V1"]["livello"] == 3).any()
    assert {"L3_RICAVI", "L3_PDP"}.isdisjoint(cat["codice"]), "duplicati di V2/V3 cancellati"
    # chi esce dal Cruscotto resta nelle viste 30" di dettaglio
    sposti = cat.set_index("codice").loc[["L3_UTILE", "L3_FORECAST", "L3_MIX"]]
    assert list(sposti["vista"]) == ["V2", "V2", "V3"] and (sposti["livello"] == 30).all()
    assert "dell'anno" in cat.set_index("codice").loc["L3_FORECAST", "definizione"], \
        "apici SQL raddoppiati non decodificati"
    print(f"OK - catalogo seme ({len(cat)} KPI) coerente con calcoli e viste")


def test_registro_ruoli():
    bp = {m.codice for m in registro_moduli.MODULI if m.bp}
    assert bp == {f"V{i}" for i in range(1, 12)} | {"CAT"}
    admin = {m.codice for m in registro_moduli.moduli_visibili("admin")}
    assert bp <= admin, "nel portale NeWatt il BP Migliora è degli admin"
    for ruolo in ("caricatore", "lettore"):
        assert not bp & {m.codice for m in registro_moduli.moduli_visibili(ruolo)}
    assert sum(m.default for m in registro_moduli.MODULI) == 1
    print("OK - viste BP Migliora solo per gli admin del portale")


if __name__ == "__main__":
    test_formato()
    test_semaforo_direzionale()
    test_kpi_fittizi()
    test_kpi_primo_livello()
    test_badge_e_avvisi()
    test_aggregazioni()
    test_catalogo_coerente()
    test_registro_ruoli()
    print("\nTutti i test calcoli OK.")

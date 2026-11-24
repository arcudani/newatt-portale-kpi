"""
Test dell'import del BP Excel (bp_import) — offline, su un workbook FITTIZIO
con la stessa struttura del BP v5 (dati_prova.workbook_bp) e, se il file è
raggiungibile, sul BP reale (solo esito della quadratura: nessun numero di
Migliora nel repo).

Esecuzione (da dentro app\\):  .venv\\Scripts\\python.exe test_import.py
"""
from __future__ import annotations

from pathlib import Path

import bp_import as bi
import dati_prova as dp

BP_REALE = Path(r"G:\Drive condivisi\Migliora Energia in NeWatt\BP"
                r"\Bozza_2026.08_Business_Plan_Migliora_v5_FTE.xlsx")


def test_norm():
    assert bi.norm("N° POD fatturati") == bi.norm("N\ufffd POD fatturati") == "n pod fatturati"
    assert bi.norm("Primo Margine Lordo ") == "primo margine lordo"
    assert bi.norm("IRES 24%") == "ires 24%"
    print("OK - normalizzazione etichette (°, encoding, spazi)")


def test_ce_fittizio():
    bp = bi.leggi_bp(dp.workbook_bp())
    assert bp.quadratura_ok, [q for q in bp.quadratura if not q["ok"]]
    assert not bp.avvisi, bp.avvisi
    ce = bp.ce
    assert int((ce["anno"] * 100 + ce["mese"]).min()) == 202610, "il piano parte da ott 2026"
    assert set(ce["voce"]) == {v.codice for v in bi.VOCI}, "voci mancanti o in più"
    tot = ce.groupby(["voce", "anno"])["importo"].sum()
    assert abs(tot[("ricavi", 2028)] - dp._annuo(dp.RICAVI, 2028)) < 1e-6
    # imposte annuali imputate a dicembre, gli altri mesi a zero
    ires = ce[(ce["voce"] == "ires") & (ce["anno"] == 2027)].set_index("mese")["importo"]
    assert abs(ires[12] - dp.ires(2027)) < 1e-6
    assert (ires.drop(12).abs() < 1e-9).all()
    # risultato netto: somma dei mesi = totale annuo (dicembre rettificato)
    atteso = dp._annuo(dp.EBIT, 2027) + dp.ires(2027) + dp.irap(2027)
    assert abs(tot[("risultato_netto", 2027)] - atteso) < 1e-6
    # voci calcolate come somma dei figli
    assert abs(tot[("imposte", 2029)] - (dp.ires(2029) + dp.irap(2029))) < 1e-6
    assert abs(tot[("perdite_crediti", 2028)] + 2.0) < 1e-9
    print(f"OK - CE fittizio: {len(ce)} righe, quadratura {len(bp.quadratura)}/"
          f"{len(bp.quadratura)}, imposte a dicembre, voci calcolate")


def test_driver_fittizio():
    bp = bi.leggi_bp(dp.workbook_bp())
    d = bp.driver
    assert set(d["driver"]) == {s.driver for s in bi.SPEC_DRIVER}
    assert (d[d["driver"] == "switch_out"]["valore"] >= 0).all(), "cessazioni positive"
    # righe VAS gas etichettate "Power" nel BP v5: lette dopo l'ancora del gas
    riga = d[(d["driver"] == "margine_vas") & (d["commodity"] == "Gas")
             & (d["prodotto_vas"] == "Assicurazione") & (d["anno"] == 2028) & (d["mese"] == 6)]
    assert abs(riga["valore"].iloc[0] - 10 * dp.VAS_PRODOTTO[("Gas", "Assicurazione")](2028, 6)) < 1e-6
    # fogli FTE: mesi da ottobre 2026, senza colonne annue
    fte = d[d["driver"] == "fte_necessari"]
    assert int((fte["anno"] * 100 + fte["mese"]).min()) == 202610
    # "Apprendistato" e "Tirocinio" senza prefisso "Liv." nel Riepilogo Livelli
    assert set(d[d["driver"] == "organico_livello"]["ruolo"]) == {
        "Alto", "Medio", "Apprendistato", "Tirocinio"}
    # provvigioni: "Provvigioni Power Retail" letta due volte, sezioni diverse
    ut = d[(d["driver"] == "provvigioni_una_tantum") & (d["segmento"] == "Retail")
           & (d["commodity"] == "Power")]["valore"].sum()
    ric = d[(d["driver"] == "provvigioni_ricorrenti") & (d["segmento"] == "Retail")
            & (d["commodity"] == "Power")]["valore"]
    assert ut < 0, "gettoni = costo"
    assert (ric > 0).any() and (ric < 0).any(), "rinnovi: mesi di costo e mesi positivi"
    print(f"OK - driver fittizi: {d['driver'].nunique()} driver, sezioni e ancore rispettate")


def test_quadratura_ko():
    bp = bi.leggi_bp(dp.workbook_bp(variazioni={("EBITDA", 2028): 1.01}))
    ko = [q for q in bp.quadratura if not q["ok"]]
    assert not bp.quadratura_ok
    assert [(q["grandezza"], q["anno"]) for q in ko] == [("EBITDA", 2028)], ko
    print("OK - quadratura KO rilevata (EBITDA 2028 +1% nel Riepilogo)")


def test_struttura_inattesa():
    try:
        bi.leggi_bp(dp.workbook_bp(escludi={"Spese Point"}))
    except bi.StrutturaInattesa as e:
        assert "Spese Point" in str(e), str(e)
    else:
        raise AssertionError("riga mancante non segnalata")
    print("OK - riga mancante -> StrutturaInattesa con messaggio leggibile")


def test_bp_reale_se_presente():
    if not BP_REALE.exists():
        print("SKIP - BP reale non raggiungibile (Drive non montato)")
        return
    bp = bi.leggi_bp(BP_REALE.read_bytes())
    ko = [(q["grandezza"], q["anno"]) for q in bp.quadratura if not q["ok"]]
    assert bp.quadratura_ok, f"quadratura KO sul BP reale: {ko}"
    assert not bp.avvisi, bp.avvisi
    print(f"OK - BP reale v5: quadratura {len(bp.quadratura)}/{len(bp.quadratura)}, "
          "nessun avviso di gerarchia")


if __name__ == "__main__":
    test_norm()
    test_ce_fittizio()
    test_driver_fittizio()
    test_quadratura_ko()
    test_struttura_inattesa()
    test_bp_reale_se_presente()
    print("\nTutti i test import OK.")

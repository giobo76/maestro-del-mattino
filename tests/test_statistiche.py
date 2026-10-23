import pandas as pd
import pytest

from agente.config import carica_config
from agente.operazione import Operazione, avanza
from agente.statistiche import calcola_statistiche, costo_ordine, simula_conto

CFG = carica_config("config.yaml")
COSTI = CFG.costi
ZERO = {k: 0 for k in COSTI}


def op(giorni, mercato="ITA", studio=False, inizio="2026-10-01"):
    """giorni: lista di (o, h, l, c, sma20). Riferimento 100, r 4: stop 96, pareggio 104, +2R 108."""
    o = Operazione(f"{inizio}-{mercato}", mercato, "X", "X", inizio, 100.0, 4.0, 96.0, 104.0, 108.0,
                   studio, 0.2, 100)
    for i, g in enumerate(giorni):
        avanza(o, str((pd.Timestamp(inizio) + pd.Timedelta(days=i + 1)).date()), *g)
    return o


STOP = [(100, 101, 95, 96, 0)]                                         # −1R, −4%
PAREGGIO = [(100, 105, 99, 104, 0), (103, 103, 99, 100, 0)]            # 0R
COMPLETA = [(100, 105, 99, 104, 101), (104, 109, 103, 108, 101), (106, 106, 104.5, 105, 106), (104, 104, 103, 104, 106)]
# metà a 108 (+2R), resto chiuso a 104 (+1R): rendimento medio 6%


def test_costo_ordine_ita_minimo():
    assert costo_ordine("ITA", 100, 25, COSTI, 1.1) == pytest.approx(1.25)


def test_costo_usa_piccolo():
    assert costo_ordine("USA", 100, 200, COSTI, 1.10) == pytest.approx(0.35 / 1.10 + 0.03)


def test_conto_con_meta():
    conto = simula_conto([op(COMPLETA)], {"ITA": 100}, ZERO, {}, 0)
    assert conto["finale_lordo"] == pytest.approx(106)


def test_conto_costi_ordini():
    conto = simula_conto([op(COMPLETA)], {"ITA": 100}, COSTI, {}, 0)
    assert conto["finale_lordo"] == pytest.approx(106 - 1.25 * 3)  # ingresso + due uscite
    conto = simula_conto([op(STOP)], {"ITA": 100}, COSTI, {}, 0)
    assert conto["finale_lordo"] == pytest.approx(96 - 1.25 * 2)


def test_conto_esclude_studio_e_aperte():
    aperta = op([(100, 101, 99, 100, 0)])
    conto = simula_conto([op(STOP, studio=True), aperta], {"ITA": 100}, ZERO, {}, 0.26)
    assert conto["finale_netto"] == pytest.approx(100) and conto["andamento"] == []


def test_tasse_sul_guadagno():
    conto = simula_conto([op(COMPLETA)], {"ITA": 100}, ZERO, {}, 0.26)
    assert conto["tasse"] == pytest.approx(1.56) and conto["finale_netto"] == pytest.approx(104.44)


def test_statistiche_vuote():
    stat = calcola_statistiche([], CFG, {}, {})
    assert stat["consigli"]["chiuse"] == 0 and stat["consigli"]["resa_media"] is None
    assert stat["aperte"] == 0 and stat["conto_simulato"]["finale_netto"] == pytest.approx(1000)


def test_percentuali_esiti():
    ops = [op(STOP), op(PAREGGIO, inizio="2026-10-05"), op(COMPLETA, inizio="2026-10-10"),
           op(STOP, studio=True, inizio="2026-10-20"), op([(100, 101, 99, 100, 0)], inizio="2026-10-25")]
    stat = calcola_statistiche(ops, CFG, {}, {})
    c = stat["consigli"]
    assert c["chiuse"] == 3 and c["somma_r"] == pytest.approx(-1 + 0 + 1.5)
    assert c["resa_media"] == pytest.approx(0.5 / 3)
    assert c["pct_stop"] == pytest.approx(1 / 3) and c["pct_pareggio"] == pytest.approx(1 / 3)
    assert c["pct_2r"] == pytest.approx(1 / 3)
    assert stat["studio"]["chiuse"] == 1 and stat["aperte"] == 1


def test_quantita():
    from agente.statistiche import quantita
    assert quantita("ITA", 100, 6.62, 1.1) == 15
    assert quantita("ITA", 100, 400, 1.1) == 0
    assert quantita("USA", 100, 200, 1.1) == pytest.approx(0.55)


def test_conto_ibkr_esclude_le_non_eseguite():
    fatta, saltata = op(COMPLETA), op(STOP, inizio="2026-10-10")
    saltata.eseguita = False
    stat = calcola_statistiche([fatta, saltata], CFG, {}, {})
    assert stat["consigli"]["chiuse"] == 2          # il metodo conta tutte le operazioni
    solo_fatta = calcola_statistiche([fatta], CFG, {}, {})
    assert stat["conto_ibkr"]["finale_lordo"] == pytest.approx(solo_fatta["conto_ibkr"]["finale_lordo"])
    assert stat["conto_simulato"]["finale_lordo"] != pytest.approx(solo_fatta["conto_simulato"]["finale_lordo"])

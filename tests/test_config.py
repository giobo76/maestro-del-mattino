from agente.config import carica_config


def test_carica_config():
    cfg = carica_config("config.yaml")
    assert cfg.soglia_prob == 0.55
    assert cfg.casi_minimi == 30
    assert set(cfg.mercati) == {"ITA", "USA"}
    assert cfg.mercati["ITA"].calendario == "XMIL"
    assert len(cfg.mercati["USA"].titoli) >= 90
    assert "ENI.MI" in cfg.mercati["ITA"].titoli

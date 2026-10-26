from agente.config import carica_config


def test_email_letta_dal_secret(monkeypatch):
    monkeypatch.setenv("EMAIL_DESTINATARIO", "x@y.it")
    assert carica_config("config.yaml").email_destinatario == "x@y.it"


def test_email_assente_senza_secret(monkeypatch):
    monkeypatch.delenv("EMAIL_DESTINATARIO", raising=False)
    assert carica_config("config.yaml").email_destinatario == ""


def test_carica_config():
    cfg = carica_config("config.yaml")
    assert cfg.soglia_r == 0.10 and cfg.atr_mult == 2.0
    assert cfg.modalita_studio is True
    assert cfg.casi_minimi == 30
    assert set(cfg.mercati) == {"ITA", "USA"}
    assert cfg.mercati["ITA"].calendario == "XMIL"
    assert len(cfg.mercati["USA"].titoli) >= 90
    assert "ENI.MI" in cfg.mercati["ITA"].titoli

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nome import analizza_nome, normalizza_username  # noqa: E402


def marchi_di(r):
    return {i["marchio"] for i in r["imitazioni"]}


def test_normalizza_varianti():
    varianti = ["@MetamasksAppWebEsempioBot", "t.me/MetamasksAppWebEsempioBot",
                "https://t.me/MetamasksAppWebEsempioBot?start=abc", "metamasksappwebesempiobot",
                "https://telegram.me/MetamasksAppWebEsempioBot/", "  @MetamasksAppWebEsempioBot  "]
    assert {normalizza_username(x).lower() for x in varianti} == {"metamasksappwebesempiobot"}


def test_normalizza_mantiene_maiuscole():
    assert normalizza_username("@MetamasksAppWebEsempioBot") == "MetamasksAppWebEsempioBot"


def test_plurale_imita_il_marchio():
    r = analizza_nome("MetamasksAppWebEsempioBot")
    imit = [i for i in r["imitazioni"] if i["marchio"] == "metamask"]
    assert imit and imit[0]["tipo"] == "contiene"
    assert "metamask+s" in imit[0]["dettaglio"]
    assert "app" in r["parole_esca"] and "web" in r["parole_esca"]
    assert r["ufficiale"] is False


def test_wallet_ufficiale():
    r = analizza_nome("wallet")
    assert r["ufficiale"] is True
    assert r["imitazioni"] == []


def test_omoglifo():
    assert "binance" in marchi_di(analizza_nome("B1nanceSupportBot"))


def test_variante_levenshtein():
    r1 = analizza_nome("MetamaskkBot")
    r2 = analizza_nome("CoinbseBot")
    assert "metamask" in marchi_di(r1)
    tipi = {i["tipo"] for i in r2["imitazioni"] if i["marchio"] == "coinbase"}
    assert tipi == {"variante"}
    det = [i["dettaglio"] for i in r2["imitazioni"] if i["marchio"] == "coinbase"][0]
    assert det == "lettera mancante"


def test_nome_pulito():
    r = analizza_nome("WeatherForecastBot")
    assert r["imitazioni"] == []
    assert r["parole_esca"] == []


def test_commenti_in_marchi_ignorati(tmp_path):
    f = tmp_path / "marchi.txt"
    f.write_bytes("# commento metamask\nzorro\n\n".encode("utf-8"))
    assert analizza_nome("MetamasksAppWebEsempioBot", f)["imitazioni"] == []
    assert marchi_di(analizza_nome("ZorroxBot", f)) == {"zorro"}


# --- M5: marchi corti attaccati a parole esca, marchi generici ("wallet") ---

def test_marchio_corto_attaccato_a_parola_esca():
    assert "okx" in marchi_di(analizza_nome("OKXofficialbot"))
    assert "ton" in marchi_di(analizza_nome("freetonbot"))
    assert "okx" in marchi_di(analizza_nome("0KXsupport"))


def test_marchio_corto_dentro_parola_comune_non_conta():
    assert "ton" not in marchi_di(analizza_nome("TonnoFrescoBot"))
    assert "ton" not in marchi_di(analizza_nome("tonerstore"))


def test_wallet_generico_nessun_falso_positivo():
    for nome in ("MyWalletTrackerBot", "CryptoWalletNewsBot", "walletmanager"):
        assert "wallet" not in marchi_di(analizza_nome(nome)), nome


def test_wallet_con_sole_parole_esca_imita():
    for nome in ("WalletOfficialBot", "wallet_support_bot", "Wa11etHelpBot", "OfficialWallet"):
        assert "wallet" in marchi_di(analizza_nome(nome)), nome


def test_wallet_variante_con_parola_esca():
    imit = [i for i in analizza_nome("WalIetSupportBot")["imitazioni"] if i["marchio"] == "wallet"]
    assert imit and imit[0]["tipo"] == "variante"


def test_marchio_generico_dichiarato_in_marchi(tmp_path):
    f = tmp_path / "marchi.txt"
    f.write_bytes("zorro||generico\n".encode("utf-8"))
    assert analizza_nome("ZorroFanClubBot", f)["imitazioni"] == []
    assert marchi_di(analizza_nome("ZorroOfficialBot", f)) == {"zorro"}


# --- M1: tutti i formati di link Telegram che un utente può incollare ---
from nome import e_link_invito  # noqa: E402


def test_normalizza_formati_telegram():
    casi = {
        "https://t.me/s/MetamasksAppWebEsempioBot": "MetamasksAppWebEsempioBot",
        "t.me/MetamasksAppWebEsempioBot/123": "MetamasksAppWebEsempioBot",
        "https://t.me/MetamasksAppWebEsempioBot?startapp=abc": "MetamasksAppWebEsempioBot",
        "tg://resolve?domain=MetamasksAppWebEsempioBot&start=ref123": "MetamasksAppWebEsempioBot",
        "TG://RESOLVE?DOMAIN=wallet": "wallet",
        "https://web.telegram.org/k/#@MetamasksAppWebEsempioBot": "MetamasksAppWebEsempioBot",
        "https://web.telegram.org/a/#MetamasksAppWebEsempioBot": "MetamasksAppWebEsempioBot",
        "web.telegram.org/k/#@wallet": "wallet",
        "  @wallet  ": "wallet",
    }
    for testo, atteso in casi.items():
        assert normalizza_username(testo) == atteso, testo


def test_link_che_non_indicano_un_bot_danno_vuoto():
    for testo in ("https://t.me/+AbCdEf123", "t.me/joinchat/AbCdEf", "https://t.me/s/",
                  "https://web.telegram.org/a/#-1001234567890", "https://web.telegram.org/k/",
                  "tg://user?id=12345", "tg://join?invite=AbCd"):
        assert normalizza_username(testo) == "", testo


def test_riconosce_link_invito():
    for testo in ("https://t.me/+AbCdEf123", "t.me/joinchat/AbCdEf", "tg://join?invite=AbCd",
                  "https://telegram.me/+xyz"):
        assert e_link_invito(testo), testo
    for testo in ("@wallet", "https://t.me/wallet", "+39 333 1234567", "tg://resolve?domain=wallet"):
        assert not e_link_invito(testo), testo

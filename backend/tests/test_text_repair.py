"""Reparo de acentuação duplicada vinda de OFX UTF-8 lido como Windows-1252."""
import pytest

from utils.text_repair import looks_like_mojibake, repair_mojibake


def broken(text: str, codec: str = "cp1252") -> str:
    """Reproduz o defeito: bytes UTF-8 interpretados em outra codificação."""
    return text.encode("utf-8").decode(codec, errors="strict")


def broken_latin1(text: str) -> str:
    return text.encode("utf-8").decode("latin-1")


@pytest.mark.parametrize("original", [
    "Compra no débito - JL PRODUTOS ALIMEMTICI",
    "Transferência enviada pelo Pix - MARCELIZA",
    "Agência: 2962 Conta: 3021091-5",
    "ÇÃO E AÇÃO",
    "Pagamento recebido – São João",
])
def test_repara_texto_cp1252(original):
    assert repair_mojibake(broken(original)) == original


@pytest.mark.parametrize("original", [
    "•••.129.716-••",
    "Compra no débito",
    "Transferência ••• Agência",
])
def test_repara_texto_latin1_com_caracteres_de_controle(original):
    assert repair_mojibake(broken_latin1(original)) == original


def test_amostra_real_de_producao():
    # Texto como gravado no banco, com o byte de controle \x80 preservado.
    stored = "TransferÃªncia enviada pelo Pix - â\x80¢â\x80¢â\x80¢.129.716-â\x80¢â\x80¢"
    assert repair_mojibake(stored) == "Transferência enviada pelo Pix - •••.129.716-••"


@pytest.mark.parametrize("correct", [
    "Compra no débito - já correto",
    "SÃO PAULO",
    "PADARIA SÃO JOÃO",
    "CAFÉ À BEIRA",
    "Pagamento de fatura",
    "",
    None,
])
def test_texto_correto_nao_muda(correct):
    assert repair_mojibake(correct) == correct
    assert not looks_like_mojibake(correct)


def test_dupla_camada():
    original = "Compra no débito"
    assert repair_mojibake(broken(broken(original))) == original

import os

from integracion_aplifisa import comando_aplifisa, localizar_aplifisa


def test_comando_pasa_pdf_como_import_absoluto(tmp_path):
    exe = tmp_path / "FacturasAplifisa.exe"
    pdf = tmp_path / "lote facturas.pdf"
    exe.write_bytes(b"")
    pdf.write_bytes(b"%PDF")
    assert comando_aplifisa(str(exe), str(pdf)) == [
        str(exe.resolve()), "--import", str(pdf.resolve())]


def test_localiza_ejecutable_configurado(tmp_path):
    exe = tmp_path / "FacturasAplifisa.exe"
    exe.write_bytes(b"")
    assert localizar_aplifisa(str(exe)) == os.path.abspath(exe)

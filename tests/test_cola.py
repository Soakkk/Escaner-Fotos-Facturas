from cola import rutas_unicas_en_orden, siguiente_de_cola, texto_cola

def test_siguiente_saca_el_primero():
    assert siguiente_de_cola(["a", "b", "c"]) == ("a", ["b", "c"])

def test_siguiente_de_cola_vacia():
    assert siguiente_de_cola([]) == (None, [])

def test_texto_sin_cola():
    assert texto_cola(1, 1) == ""
    assert texto_cola(0, 0) == ""

def test_texto_en_mitad_de_la_tanda():
    assert texto_cola(1, 5) == "📥 Foto 1 de 5"
    assert texto_cola(3, 5) == "📥 Foto 3 de 5"

def test_texto_ultima_de_la_tanda():
    assert texto_cola(5, 5) == "✓ Última de la tanda"


def test_rutas_unicas_conserva_la_primera_posicion():
    assert rutas_unicas_en_orden(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

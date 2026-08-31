import numpy as np
import cv2
from imagen import igualar_iluminacion

def test_igualar_iluminacion_conserva_forma_y_tipo():
    img = (np.random.rand(80, 100, 3) * 255).astype(np.uint8)
    out = igualar_iluminacion(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8

def test_igualar_iluminacion_uniformiza_un_gradiente():
    h, w = 100, 200
    grad = np.tile(np.linspace(120, 255, w).astype(np.uint8), (h, 1))
    img = cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR)
    out = igualar_iluminacion(img)
    g_in = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std()
    g_out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).std()
    assert g_out < g_in


from imagen import buffer_rgb_a_cv

def test_buffer_rgb_a_cv_respeta_padding_y_orden_bgr():
    w, h = 2, 2
    bpl = w * 3 + 2
    fila0 = bytes([255, 0, 0,  0, 255, 0]) + bytes([0, 0])
    fila1 = bytes([0, 0, 255,  9, 9, 9]) + bytes([0, 0])
    buf = fila0 + fila1
    out = buffer_rgb_a_cv(buf, w, h, bpl)
    assert out.shape == (2, 2, 3)
    assert tuple(int(x) for x in out[0, 0]) == (0, 0, 255)
    assert tuple(int(x) for x in out[0, 1]) == (0, 255, 0)


from imagen import aplicar_pipeline

def test_pipeline_cuatro_modos_conservan_tamano():
    img = (np.random.rand(120, 90, 3) * 255).astype(np.uint8)
    for modo in (0, 1, 2, 3):
        out = aplicar_pipeline(img, modo, 0, 0, 0)
        assert out.shape == img.shape, f"modo {modo}"
        assert out.dtype == np.uint8


from imagen import binarizar_sauvola, filtro_bn_escaner

def test_sauvola_solo_da_0_y_255_y_conserva_tamano():
    gris = (np.random.rand(70, 90) * 255).astype(np.uint8)
    out = binarizar_sauvola(gris)
    assert out.shape == gris.shape
    assert out.dtype == np.uint8
    assert set(np.unique(out).tolist()).issubset({0, 255})

def test_sauvola_texto_fino_negro_sobre_fondo_con_sombra():
    h, w = 80, 160
    gris = np.tile(np.linspace(150, 255, w).astype(np.uint8), (h, 1)).copy()
    for y in (20, 30, 40, 50, 60):
        gris[y:y + 2, 30:130] = 15
    out = binarizar_sauvola(gris)
    assert out[20:22, 30:130].mean() < 60
    assert out[24:28, 30:130].mean() > 180


def _prop_negros(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float((g < 128).mean())


def _documento_sintetico(w=2800, h=2100, lineas=True):
    """Foto sintética: 'papel' blanco con texto sobre fondo oscuro."""
    img = np.full((h, w, 3), 60, dtype=np.uint8)
    esquinas = np.array([[w * 0.2, h * 0.15], [w * 0.85, h * 0.2],
                         [w * 0.8, h * 0.9], [w * 0.15, h * 0.85]],
                        dtype=np.int32)
    cv2.fillPoly(img, [esquinas], (235, 235, 235))
    if lineas:
        for y in range(int(h * 0.3), int(h * 0.7), int(h * 0.06)):
            cv2.line(img, (int(w * 0.3), y), (int(w * 0.7), y), (30, 30, 30), 4)
    return img, esquinas.astype(np.float32)


def test_filtro_bn_intensidad_oscurece():
    doc, _ = _documento_sintetico(1200, 900)
    baja = filtro_bn_escaner(doc, intensidad=10)
    alta = filtro_bn_escaner(doc, intensidad=90)
    assert baja.shape == doc.shape and baja.dtype == np.uint8
    assert _prop_negros(alta) >= _prop_negros(baja)


def test_filtro_bn_consistente_entre_resoluciones():
    """La vista previa (reducida) y el guardado (tamaño real) deben dar
    una proporción de negro parecida gracias al escalado de parámetros."""
    grande, _ = _documento_sintetico(2800, 2100)
    r = 1400.0 / 2800.0
    pequena = cv2.resize(grande, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
    p_grande = _prop_negros(filtro_bn_escaner(grande))
    p_pequena = _prop_negros(filtro_bn_escaner(pequena))
    assert abs(p_grande - p_pequena) < 0.03, (p_grande, p_pequena)


def _foto_texto_debil(w=1300, h=900):
    """Página con sombra y líneas de texto finas y tenues (el caso que el
    filtro antiguo destrozaba)."""
    img = np.full((h, w), 235, dtype=np.float32)
    for y in range(200, 700, 50):
        img[y:y + 2, 150:1100] = 150       # trazos finos, poco contraste
    xx = np.tile(np.linspace(1.0, 0.55, w, dtype=np.float32), (h, 1))
    img = (img * xx)
    img = cv2.GaussianBlur(img, (0, 0), 0.8)
    return cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_GRAY2BGR)


def test_filtro_bn_nitido_rescata_texto_debil_y_fondo_blanco():
    out = cv2.cvtColor(filtro_bn_escaner(_foto_texto_debil(), 50),
                       cv2.COLOR_BGR2GRAY)
    # el fondo queda blanco puro (sin gris ni motas)...
    assert out[100:180, 200:1000].mean() > 250
    # ...y las líneas tenues sobreviven claramente más oscuras
    assert out[200:202, 200:1000].mean() < 140


from imagen import filtro_bn_puro, _quitar_motas

def test_filtro_bn_puro_es_binario_y_conserva_texto():
    doc, _ = _documento_sintetico(1200, 900)
    out = filtro_bn_puro(doc, 50)
    g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    assert set(np.unique(g).tolist()).issubset({0, 255})
    assert _prop_negros(out) > 0.005   # las líneas de texto están

def test_quitar_motas_borra_aisladas_y_conserva_puntos_cercanos():
    bn = np.full((200, 200), 255, dtype=np.uint8)
    bn[100:103, 40:120] = 0      # trazo grande (texto)
    bn[95:97, 60:62] = 0         # "tilde" pequeña pegada al trazo
    bn[20:22, 170:172] = 0       # mota aislada del mismo tamaño
    out = _quitar_motas(bn, area_min=12, escala=1.0)
    assert (out[100:103, 40:120] == 0).all()   # el trazo queda
    assert (out[95:97, 60:62] == 0).all()      # la tilde sobrevive
    assert (out[20:22, 170:172] == 255).all()  # la mota aislada se borra


from imagen import detectar_documento, ordenar_puntos

def test_detectar_documento_cuadrilatero_sintetico():
    img, esperadas = _documento_sintetico()
    pts = detectar_documento(img)
    assert pts is not None
    detectadas = ordenar_puntos(np.array(pts, dtype=np.float32))
    esperadas = ordenar_puntos(esperadas)
    diagonal = (img.shape[0] ** 2 + img.shape[1] ** 2) ** 0.5
    for d, e in zip(detectadas, esperadas):
        assert np.linalg.norm(d - e) < diagonal * 0.02, (d, e)

def test_detectar_documento_imagen_plana_devuelve_none():
    img = np.full((600, 800, 3), 128, dtype=np.uint8)
    assert detectar_documento(img) is None

def test_detectar_documento_de_color_sobre_fondo_de_brillo_parecido():
    # Documento azulado sobre fondo beige con brillo casi idéntico: en gris
    # no hay borde, solo cambio de color. Debe detectarse igual.
    W, H = 1200, 900
    img = np.full((H, W, 3), (180, 200, 212), np.uint8)        # beige (BGR)
    esquinas = np.array([[W * 0.18, H * 0.14], [W * 0.84, H * 0.17],
                         [W * 0.80, H * 0.88], [W * 0.14, H * 0.85]], np.int32)
    cv2.fillPoly(img, [esquinas], (225, 205, 170))             # documento azul
    for i, y in enumerate(range(int(H * 0.4), int(H * 0.8), 40)):
        col = [(40, 40, 160), (40, 120, 40), (120, 60, 20)][i % 3]
        cv2.line(img, (int(W * 0.22), y), (int(W * 0.74), y), col, 6)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    assert abs(int(gris[450, 480]) - int(gris[5, 5])) < 12     # casi sin borde en gris
    pts = detectar_documento(img)
    assert pts is not None
    det = ordenar_puntos(np.array(pts, np.float32))
    esp = ordenar_puntos(esquinas.astype(np.float32))
    diag = (H ** 2 + W ** 2) ** 0.5
    for d, e in zip(det, esp):
        assert np.linalg.norm(d - e) < diag * 0.04, (d, e)


from imagen import miniatura_archivo

def test_miniatura_archivo(tmp_path):
    ruta = str(tmp_path / "foto.png")
    cv2.imwrite(ruta, (np.random.rand(800, 1200, 3) * 255).astype(np.uint8))
    mini = miniatura_archivo(ruta, 64)
    assert mini is not None and mini.dtype == np.uint8
    assert max(mini.shape[:2]) <= 64 and mini.shape[2] == 3

def test_miniatura_archivo_ruta_invalida():
    assert miniatura_archivo("/no/existe/foto.jpg") is None


from imagen import es_bilevel, cv_a_pil_pdf

def test_es_bilevel():
    bn = np.zeros((40, 60, 3), dtype=np.uint8)
    bn[10:20, 10:30] = 255
    assert es_bilevel(bn)
    color = bn.copy()
    color[0, 0] = (10, 20, 30)
    assert not es_bilevel(color)
    grises = cv2.cvtColor((np.random.rand(40, 60) * 255).astype(np.uint8),
                          cv2.COLOR_GRAY2BGR)
    assert not es_bilevel(grises)

def test_cv_a_pil_pdf_modo_1_para_bn_puro_y_rgb_para_color():
    doc, _ = _documento_sintetico(1200, 900)
    assert cv_a_pil_pdf(filtro_bn_puro(doc)).mode == "1"
    assert cv_a_pil_pdf(doc).mode == "RGB"

def test_cv_a_pil_pdf_conserva_el_contenido():
    bn = np.zeros((40, 60, 3), dtype=np.uint8)
    bn[10:20, 10:30] = 255
    pil = cv_a_pil_pdf(bn)
    arr = np.array(pil.convert("L"))
    assert arr[15, 15] == 255 and arr[0, 0] == 0


from imagen import codificar_pagina, decodificar_pagina

def test_codificar_pagina_bn_es_pequena_y_sin_perdida():
    doc, _ = _documento_sintetico(1200, 900)
    bn = filtro_bn_puro(doc)
    datos = codificar_pagina(bn)
    assert len(datos) < bn.nbytes / 10
    assert np.array_equal(decodificar_pagina(datos), bn)

def test_codificar_pagina_color_recupera_aproximado():
    img = np.full((50, 80, 3), (200, 120, 40), dtype=np.uint8)
    out = decodificar_pagina(codificar_pagina(img))
    assert out.shape == img.shape
    assert np.abs(out.astype(int) - img.astype(int)).mean() < 3


from imagen import balance_blancos_scb, filtro_color_mejorado

def _quemado_pct(img):
    """% de píxeles blanco puro (los 3 canales >= 250): mide el 'quemado'."""
    return float((img.min(axis=2) >= 250).mean() * 100)

def test_scb_estira_el_contraste_y_conserva_forma():
    # Imagen de bajo contraste (valores 100..150): SCB debe ampliarlo.
    img = (100 + np.random.rand(80, 120, 3) * 50).astype(np.uint8)
    out = balance_blancos_scb(img, recorte=0.5)
    assert out.shape == img.shape and out.dtype == np.uint8
    g_in = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g_out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    assert g_out.std() > g_in.std()      # más contraste

def test_scb_corrige_la_dominante_de_color():
    # Gris neutro con un velo azul (canal B alto): tras el balance, los tres
    # canales deben quedar mucho más parecidos en media.
    img = np.full((60, 60, 3), 128, dtype=np.uint8)
    img[:, :, 0] = 190                     # dominante azul
    img[20:40, 20:40] = (210, 150, 150)    # algo de variación para los percentiles
    out = balance_blancos_scb(img, recorte=0.5)
    medias = [float(out[:, :, c].mean()) for c in range(3)]
    assert max(medias) - min(medias) < 40  # la dominante se ha reducido

def test_filtro_color_no_quema_con_reflejo_fuerte():
    # Documento claro con un reflejo casi blanco: el filtro NO debe reventar
    # la imagen a blanco (el problema del filtro antiguo).
    img = np.full((200, 320, 3), (205, 200, 195), dtype=np.uint8)
    yy, xx = np.mgrid[0:200, 0:320]
    reflejo = np.exp(-(((xx - 230) ** 2 + (yy - 70) ** 2) / (2 * 60.0 ** 2)))
    for c in range(3):
        img[:, :, c] = np.clip(img[:, :, c] + reflejo * 45, 0, 255)
    for intensidad in (25, 50, 100):
        out = filtro_color_mejorado(img, intensidad)
        assert out.shape == img.shape and out.dtype == np.uint8
        assert _quemado_pct(out) < 2.0, (intensidad, _quemado_pct(out))

def test_filtro_color_intensidad_realza_el_contraste():
    img = (110 + np.random.rand(120, 160, 3) * 40).astype(np.uint8)
    suave = cv2.cvtColor(filtro_color_mejorado(img, 10), cv2.COLOR_BGR2GRAY)
    fuerte = cv2.cvtColor(filtro_color_mejorado(img, 100), cv2.COLOR_BGR2GRAY)
    assert fuerte.std() >= suave.std()


from imagen import componer_dni, A4_ANCHO_200DPI, A4_ALTO_200DPI

def test_componer_dni_dos_caras_en_una_hoja():
    cara_a = np.full((300, 480, 3), (50, 60, 200), dtype=np.uint8)
    cara_b = np.full((300, 480, 3), (200, 60, 50), dtype=np.uint8)
    hoja = componer_dni(cara_a, cara_b)
    assert hoja.shape == (A4_ALTO_200DPI, A4_ANCHO_200DPI, 3)
    mitad = A4_ALTO_200DPI // 2
    arriba = hoja[:mitad]
    abajo = hoja[mitad:]
    # Cada mitad contiene el color de su cara y no el de la contraria
    assert np.all(arriba == (50, 60, 200), axis=2).any()
    assert not np.all(arriba == (200, 60, 50), axis=2).any()
    assert np.all(abajo == (200, 60, 50), axis=2).any()
    assert not np.all(abajo == (50, 60, 200), axis=2).any()

def test_componer_dni_no_deforma_la_proporcion():
    cara = np.zeros((300, 480, 3), dtype=np.uint8)   # negro puro, ratio 1.6
    hoja = componer_dni(cara, cara)
    ys, xs = np.where(hoja[:, :, 0] < 10)
    mitad = ys < A4_ALTO_200DPI // 2
    alto = ys[mitad].max() - ys[mitad].min() + 1
    ancho = xs[mitad].max() - xs[mitad].min() + 1
    assert abs((ancho / alto) - 1.6) < 0.05


from imagen import (
    detectar_orientacion_texto, auto_orientar_documento,
    detectar_multiples_documentos, rotar_imagen,
)

def test_detectar_orientacion_y_auto_orientar_sintetico():
    doc0 = np.full((1200, 800, 3), 255, dtype=np.uint8)
    cv2.rectangle(doc0, (100, 60), (700, 160), (30, 30, 30), -1)
    for y in range(250, 950, 40):
        cv2.line(doc0, (100, y), (700, y), (40, 40, 40), 4)

    for deg in (0, 90, 180, 270):
        rot = rotar_imagen(doc0, deg) if deg != 0 else doc0
        rotada, aplicado = auto_orientar_documento(rot)
        assert rotada.shape == doc0.shape
        diff = np.mean(np.abs(rotada.astype(float) - doc0.astype(float)))
        assert diff < 1.0, f"Fallo al restaurar rotación de {deg}°, diff={diff}"


def test_detectar_multiples_documentos_en_mesa():
    mesa = np.full((1200, 1600, 3), 50, dtype=np.uint8)
    # Ticket 1 (izquierda)
    cv2.rectangle(mesa, (100, 150), (650, 1050), (230, 230, 230), -1)
    # Ticket 2 (derecha)
    cv2.rectangle(mesa, (850, 200), (1450, 1000), (240, 240, 240), -1)

    docs = detectar_multiples_documentos(mesa)
    assert len(docs) == 2
    # El primero está a la izquierda / más arriba
    assert docs[0][0][0] < docs[1][0][0] or docs[0][0][1] < docs[1][0][1]


"""Lógica pura de la cola de fotos (sin Qt)."""


def rutas_unicas_en_orden(rutas):
    """Elimina repeticiones exactas sin cambiar el orden elegido."""
    vistas = set()
    unicas = []
    for ruta in rutas:
        if ruta not in vistas:
            vistas.add(ruta)
            unicas.append(ruta)
    return unicas


def siguiente_de_cola(cola):
    """Saca el primer elemento: devuelve (siguiente, resto).
    Con la cola vacía devuelve (None, [])."""
    if not cola:
        return None, []
    return cola[0], list(cola[1:])


def texto_cola(pos, total):
    """Texto del indicador de cola. pos=foto actual (1-based), total=tamaño de la tanda."""
    if total <= 1:
        return ""
    if pos < total:
        return f"📥 Foto {pos} de {total}"
    return "✓ Última de la tanda"

# Escáner de Fotos — Suite de oficina Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar la interfaz y automatizar cola, recuperación, clientes y actualizaciones sin cambiar un solo píxel producido por los algoritmos actuales.

**Architecture:** La lógica nueva se divide en módulos puros de almacenamiento, sesión y vigilancia; `VentanaPrincipal` solo coordina esos servicios. El motor de imagen permanece sin cambios y las propuestas anticipadas llaman a las funciones existentes.

**Tech Stack:** Python 3.11+, PySide6, OpenCV, Pillow, pytest, Inno Setup, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-suite-oficina-unificada-design.md`

## Global Constraints

- Plataforma: Windows 10/11.
- No modificar `EscanerFotos/imagen.py` salvo pruebas de caracterización; mismas entradas y ajustes deben producir bytes/píxeles idénticos.
- Paleta y tipografía deben coincidir con los valores exactos de la especificación.
- El repositorio `Facturas-a-Aplifisa` es solo lectura.
- Toda escritura de estado usa temporal, `flush`, `os.fsync` y `os.replace`.

---

### Task 1: Caracterizar las salidas actuales

**Files:**
- Create: `tests/test_regresion_salida.py`
- Test: `tests/test_imagen.py`

**Interfaces:**
- Consumes: `aplicar_pipeline`, `codificar_pagina`, `componer_dni` de `EscanerFotos/imagen.py`.
- Produces: fixtures deterministas y hashes SHA-256 que protegen el motor actual.

- [ ] **Step 1: Escribir pruebas de caracterización**

```python
def test_pipeline_actual_no_cambia(foto_documento):
    salida = aplicar_pipeline(foto_documento, 0, 0, 0, 0, 50)
    assert hashlib.sha256(salida.tobytes()).hexdigest() == HASH_BN_ACTUAL
```

- [ ] **Step 2: Ejecutar las pruebas y registrar únicamente hashes obtenidos del commit base**

Run: `python -m pytest tests/test_regresion_salida.py -v`
Expected: FAIL hasta fijar los hashes de la rama base; PASS sin tocar el motor.

- [ ] **Step 3: Ejecutar toda la batería**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_regresion_salida.py
git commit -m "test: proteger las salidas del escaner"
```

### Task 2: Almacenamiento común de clientes y sesión

**Files:**
- Create: `EscanerFotos/suite_storage.py`
- Create: `EscanerFotos/sesion_trabajo.py`
- Create: `tests/test_suite_storage.py`
- Create: `tests/test_sesion_trabajo.py`

**Interfaces:**
- Produces: `normalizar_nif(valor: str) -> str`, `leer_clientes() -> dict`, `fusionar_cliente(cliente: dict, origen: str) -> dict`, `guardar_sesion(datos: dict) -> None`, `leer_sesion() -> dict | None`, `borrar_sesion() -> None`.

- [ ] **Step 1: Probar normalización, fusión sin pisar conflictos y escritura atómica**

```python
def test_conflicto_conserva_valor_y_propone_alternativa(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fusionar_cliente({"nif": "B-12345678", "nombre": "Uno"}, "escaner")
    r = fusionar_cliente({"nif": "B12345678", "nombre": "Dos"}, "escaner")
    assert r["conflictos"]["nombre"] == ["Uno", "Dos"]
```

- [ ] **Step 2: Verificar el fallo inicial**

Run: `python -m pytest tests/test_suite_storage.py tests/test_sesion_trabajo.py -v`
Expected: FAIL por módulos inexistentes.

- [ ] **Step 3: Implementar un JSON versionado y reemplazo atómico**

```python
def guardar_json_atomico(ruta: Path, datos: dict) -> None:
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(temporal, ruta)
```

- [ ] **Step 4: Pasar pruebas y commit**

Run: `python -m pytest tests/test_suite_storage.py tests/test_sesion_trabajo.py -v`
Expected: PASS.

```bash
git add EscanerFotos/suite_storage.py EscanerFotos/sesion_trabajo.py tests/test_suite_storage.py tests/test_sesion_trabajo.py
git commit -m "feat: guardar clientes y sesiones de forma recuperable"
```

### Task 3: Cola recuperable y vigilancia estable

**Files:**
- Create: `EscanerFotos/vigilancia.py`
- Create: `EscanerFotos/precalculo.py`
- Modify: `EscanerFotos/escaner_fotos.py`
- Modify: `EscanerFotos/cola.py`
- Create: `tests/test_vigilancia.py`
- Create: `tests/test_precalculo.py`
- Modify: `tests/test_ventana.py`

**Interfaces:**
- Produces: `ArchivoObservado.actualizar(size: int, mtime_ns: int) -> bool`, `identidad_archivo(path: str) -> str`, `PrecalculoResultado(ruta, miniatura, puntos, rotacion)`, `VentanaPrincipal._guardar_sesion_actual()` y `_restaurar_sesion()`.

- [ ] **Step 1: Probar estabilidad de dos observaciones, deduplicación y restauración del orden**

```python
def test_archivo_solo_esta_listo_tras_dos_observaciones_iguales():
    a = ArchivoObservado()
    assert not a.actualizar(100, 1)
    assert a.actualizar(100, 1)
```

- [ ] **Step 2: Confirmar fallo**

Run: `python -m pytest tests/test_vigilancia.py tests/test_ventana.py -v`
Expected: FAIL antes de crear el servicio y conectar la ventana.

- [ ] **Step 3: Implementar servicio puro y conectar guardado en cada mutación de cola/PDF**

```python
@dataclass
class ArchivoObservado:
    firma: tuple[int, int] | None = None
    repeticiones: int = 0
    def actualizar(self, size, mtime_ns):
        nueva = (size, mtime_ns)
        self.repeticiones = self.repeticiones + 1 if nueva == self.firma else 1
        self.firma = nueva
        return self.repeticiones >= 2
```

- [ ] **Step 4: Calcular miniatura, puntos y rotación de la siguiente foto en un `QThread`; aplicar la propuesta únicamente cuando el usuario use la acción normal**

```python
@dataclass(frozen=True)
class PrecalculoResultado:
    ruta: str
    miniatura: object
    puntos: object | None
    rotacion: int
```

- [ ] **Step 5: Pasar pruebas y commit**

Run: `python -m pytest tests/test_vigilancia.py tests/test_precalculo.py tests/test_ventana.py -v`
Expected: PASS.

```bash
git add EscanerFotos/vigilancia.py EscanerFotos/precalculo.py EscanerFotos/cola.py EscanerFotos/escaner_fotos.py tests/test_vigilancia.py tests/test_precalculo.py tests/test_ventana.py
git commit -m "feat: recuperar la cola y esperar archivos completos"
```

### Task 4: Perfiles, cliente y flujo de finalización

**Files:**
- Create: `EscanerFotos/perfiles.py`
- Modify: `EscanerFotos/escaner_fotos.py`
- Create: `tests/test_perfiles.py`
- Modify: `tests/test_ventana.py`

**Interfaces:**
- Produces: `PerfilEscaneo(nombre, filtro, intensidad, brillo, contraste, nitidez, destino)`, `cargar_perfiles()`, `guardar_perfil()`.

- [ ] **Step 1: Probar perfiles iniciales y que el perfil Factura reproduce los valores base**
- [ ] **Step 2: Ejecutar `python -m pytest tests/test_perfiles.py -v` y observar FAIL**
- [ ] **Step 3: Implementar perfiles y selector de cliente sin modificar el pipeline**

```python
@dataclass(frozen=True)
class PerfilEscaneo:
    nombre: str
    filtro: int
    intensidad: int = 50
    brillo: int = 0
    contraste: int = 0
    nitidez: int = 0
    destino: str = ""
```
- [ ] **Step 4: Añadir “Deshacer última página” y estado final Exportar/Enviar**
- [ ] **Step 5: Ejecutar `python -m pytest tests/test_perfiles.py tests/test_ventana.py tests/test_regresion_salida.py -v` y obtener PASS**
- [ ] **Step 6: Commit**

```bash
git add EscanerFotos/perfiles.py EscanerFotos/escaner_fotos.py tests/test_perfiles.py tests/test_ventana.py
git commit -m "feat: añadir perfiles y cierre guiado del lote"
```

### Task 5: Actualizador automático y publicación

**Files:**
- Modify: `EscanerFotos/actualizador_core.py`
- Modify: `EscanerFotos/actualizador.py`
- Modify: `EscanerFotos/escaner_fotos.py`
- Modify: `.github/workflows/build.yml`
- Modify: `tests/test_actualizador_core.py`

**Interfaces:**
- Produces: estados `checking`, `downloading`, `ready`, `installing`, `error`; `programar_instalacion(ruta: str) -> None`.

- [ ] **Step 1: Probar selección estricta de Setup + SHA, periodicidad y transición a ready**
- [ ] **Step 2: Ejecutar `python -m pytest tests/test_actualizador_core.py -v`; Expected: FAIL en casos nuevos**
- [ ] **Step 3: Descargar automáticamente en segundo plano y guardar sesión antes de `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`**

```python
def instalar_actualizacion_lista(self):
    self._guardar_sesion_actual()
    actualizador.lanzar_instalador(self._ruta_update_lista)
    QApplication.quit()
```
- [ ] **Step 4: Actualizar workflow para ejecutar tests, construir instalador, generar `.sha256` y adjuntarlo a tags `v*`**
- [ ] **Step 5: Ejecutar `python -m pytest -q`; Expected: PASS**
- [ ] **Step 6: Commit**

```bash
git add EscanerFotos/actualizador_core.py EscanerFotos/actualizador.py EscanerFotos/escaner_fotos.py .github/workflows/build.yml tests/test_actualizador_core.py
git commit -m "feat: automatizar actualizaciones y releases"
```

### Task 6: Sistema visual e icono de suite

**Files:**
- Modify: `EscanerFotos/estilo.py`
- Modify: `EscanerFotos/escaner_fotos.py`
- Modify: `EscanerFotos/recursos/icono.png`
- Modify: `EscanerFotos/recursos/icono.ico`
- Modify: `tests/test_estilo.py`

**Interfaces:**
- Consumes: tokens exactos de la especificación.
- Produces: barra clara, jerarquía adaptable e icono escáner de la familia.

- [ ] **Step 1: Probar tokens, nombres de objeto y presencia de las acciones principales**
- [ ] **Step 2: Ejecutar `python -m pytest tests/test_estilo.py tests/test_ventana.py -v`; Expected: FAIL en reglas nuevas**
- [ ] **Step 3: Reemplazar únicamente QSS y composición del shell; no tocar `imagen.py`**

```python
PAGE = "#F5F8FC"; CARD = "#FFFFFF"; INK = "#24384D"
MUTED = "#5D7084"; BORDER = "#DCE5F0"; ACCENT = "#326FA6"
SUCCESS = "#19724E"; WARNING = "#86500A"; DANGER = "#B43737"
```
- [ ] **Step 4: Generar el icono desde `assets/app.png` de la referencia: rombo azul, documento/foto blanco y acento dorado; exportar PNG 512 e ICO multirresolución**
- [ ] **Step 5: Capturar ventana amplia y portátil, corregir en una sola ronda y confirmar en una segunda**
- [ ] **Step 6: Ejecutar `python -m pytest -q`; Expected: PASS y hashes sin cambios**
- [ ] **Step 7: Commit**

```bash
git add EscanerFotos/estilo.py EscanerFotos/escaner_fotos.py EscanerFotos/recursos/icono.png EscanerFotos/recursos/icono.ico tests/test_estilo.py
git commit -m "feat: integrar el escaner en la identidad de la suite"
```

### Task 7: Verificación final

- [ ] **Step 1: Ejecutar `python -m pytest -q` y conservar la salida completa**
- [ ] **Step 2: Ejecutar `python -m compileall -q EscanerFotos`**
- [ ] **Step 3: Ejecutar el detector visual una vez sobre `EscanerFotos/estilo.py EscanerFotos/escaner_fotos.py`**
- [ ] **Step 4: Revisar `git diff --check` y `git status --short`**
- [ ] **Step 5: Commit de documentación/versionado final si procede**

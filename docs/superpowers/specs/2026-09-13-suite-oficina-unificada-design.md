# Escáner de Fotos dentro de la suite de oficina

Estado: aprobado por el usuario el 13 de septiembre de 2026.

## Objetivo

Integrar Escáner de Fotos en la misma familia visual que Facturas a Aplifisa y reducir el trabajo manual del flujo foto → documento → lote → Aplifisa. La aplicación seguirá siendo una herramienta de escritorio Windows en PySide6.

## Límites

- Facturas a Aplifisa es una referencia de solo lectura.
- FocusNotch y los repositorios históricos de instaladores quedan fuera.
- No se cambiarán los algoritmos de detección, recorte, orientación, filtros, composición de DNI ni codificación de imágenes/PDF.
- Con los mismos archivos y ajustes, la salida seguirá siendo idéntica.
- No se añaden trabajos de seguridad que no sean necesarios para evitar archivos incompletos o actualizaciones corruptas.

## Sistema visual compartido

La interfaz de trabajo adopta los tokens de Facturas a Aplifisa: fondo `#F5F8FC`, tarjetas blancas, tinta `#24384D`, texto secundario `#5D7084`, borde `#DCE5F0`, acento `#326FA6`, éxito `#19724E`, aviso `#86500A` y error `#B43737`. La familia es Segoe UI Variable, con Segoe UI como alternativa.

La ventana conserva sus tres zonas —original, controles y resultado—, pero utiliza la barra superior clara, controles, radios, densidad, estados y lenguaje de la suite. Las acciones secundarias pasan a “Más” cuando falte espacio. El icono será parte de la misma familia que Facturas, con un pictograma de escáner/foto propio.

## Automatización del flujo

1. Persistir la foto actual, la cola, el orden, las páginas del PDF, el perfil y el destino. Restaurar ese trabajo después de cerrar, fallar o actualizar.
2. Esperar a que tamaño y fecha de una imagen vigilada estén estables antes de encolarla. Evitar duplicados mediante identidad de archivo sin borrar el original.
3. Preparar en segundo plano miniaturas y propuestas de recorte/orientación de las siguientes fotos. La propuesta no altera la salida hasta que el usuario la acepta o usa la acción normal.
4. Añadir perfiles locales para factura, DNI y documento. Guardan controles y destino; el perfil inicial reproduce los valores actuales.
5. Tras añadir una página, avanzar automáticamente. Al acabar, ofrecer en la misma zona exportar, enviar a Aplifisa o deshacer la última incorporación.
6. El directorio compartido de clientes permite elegir un cliente y sugerir el prefijo y la carpeta, sin insertar datos en la imagen.

## Estado local compartido

Los datos comunes viven en `%LOCALAPPDATA%\AsesoriaEMarin\Suite`. El directorio `clientes.json` usa el NIF normalizado como clave, conserva procedencia y fecha de cada campo y se escribe de forma atómica. Esta app lo consulta para sugerencias; no reemplaza datos de clientes.

La sesión propia se guarda fuera del repositorio con versión de esquema, escritura temporal + reemplazo y copias rotativas. La primera migración conserva los ajustes actuales de `QSettings`.

## Actualizaciones

La aplicación comprueba GitHub Releases al arrancar y periódicamente. Descarga el instalador en segundo plano, valida tamaño y SHA-256 cuando exista, guarda la sesión, inicia Inno Setup en modo silencioso y se reabre. Si hay trabajo activo, la actualización queda preparada para el cierre o permite “Reiniciar y actualizar”. La comprobación manual muestra errores; la automática no interrumpe el trabajo.

El proceso de publicación ejecuta pruebas, sincroniza la versión, construye EXE e instalador, crea SHA-256 y publica la release desde un flujo de Windows reproducible.

## Errores y recuperación

Los fallos de una foto no detienen el lote. La cola marca el elemento, conserva su posición y permite reintentar solo ese elemento. Ninguna recuperación elimina archivos de origen ni páginas ya confirmadas. Las acciones destructivas mantienen confirmación y, cuando sea posible, deshacer.

## Verificación

- Pruebas unitarias de sesión, estabilidad de archivos vigilados, deduplicación, perfiles y actualización.
- Pruebas de interfaz para barra, estados, diseño adaptable y restauración.
- Pruebas de regresión que comparen los arrays/píxeles o hashes de las salidas actuales con fixtures fijos.
- Prueba del flujo completo foto → PDF → apertura de Facturas a Aplifisa con dobles de proceso.
- Construcción del instalador en Windows antes de publicar.


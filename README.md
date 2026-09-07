# SunoBridge

Un plugin de instrumento **VST3** para FL Studio que vigila una carpeta de tu
disco (donde exportas o descargas desde **Suno Studio**) y carga
automáticamente el archivo más reciente para que puedas dispararlo por MIDI
desde dentro de FL Studio, sin arrastrar el WAV a mano cada vez.

**Importante:** Suno no tiene una API pública oficial, así que este plugin
**no genera música ni habla con los servidores de Suno**. Es un "puente de
archivos": tú generas y exportas en Suno Studio como siempre (web), y este
plugin detecta el archivo nuevo y lo deja listo para tocar en FL Studio en
cuanto lo ve. Ya lo he compilado y verificado que el código compila sin
errores (comprobado en Linux); te falta el último paso, compilarlo para
Windows, porque eso solo se puede hacer y probar en tu propio ordenador
dentro de FL Studio.

## Qué hace

- Un campo para elegir la carpeta a vigilar (por defecto apunta a
  `Descargas`, cámbialo a tu carpeta de exportación de Suno Studio).
- Cada segundo revisa esa carpeta y, si hay un `.wav` / `.aiff` / `.flac`
  más nuevo que el que tiene cargado, lo carga automáticamente.
- Cualquier nota MIDI que le mandes (desde el piano roll o tu teclado)
  dispara ese sample desde el principio. Hay un botón "Preview" para
  probarlo sin MIDI.
- Un slider de Gain, automatizable desde FL Studio.
- También puedes cargar un archivo concreto a mano con "Load one file...",
  si no quieres depender del auto-detectado.

## Limitaciones de esta primera versión

- Es un disparador "one-shot": todas las notas reproducen la muestra a su
  tono/velocidad original (no hay pitch-tracking nota a nota todavía).
- Hasta 8 disparos solapados a la vez.
- Revisa la carpeta cada 1 segundo (no es instantáneo, pero es rápido).
- Pensado para clips cortos/medios (limita la carga a ~1.3 min a 48kHz
  estéreo por seguridad de memoria; dímelo si necesitas más).

## Compilar en Windows (una sola vez)

Necesitas (todo gratis):

1. **Visual Studio 2022 Community** — instálalo con el workload
   **"Desarrollo para el escritorio con C++"** marcado.
   https://visualstudio.microsoft.com/es/vs/community/
2. **Git para Windows** (para que CMake pueda descargar JUCE automáticamente).
   https://git-scm.com/download/win

Pasos:

1. Descomprime esta carpeta `SunoBridge` donde quieras, por ejemplo en
   `C:\Dev\SunoBridge`.
2. Abre **Visual Studio 2022** → `Archivo` → `Abrir` → `Carpeta...` → elige
   la carpeta `SunoBridge` (la que contiene `CMakeLists.txt`).
3. Visual Studio detecta el `CMakeLists.txt` automáticamente y empieza a
   configurar el proyecto (la primera vez descarga JUCE desde GitHub, tarda
   unos minutos — necesita conexión a internet).
4. Arriba, selecciona la configuración **x64-Release** (o similar) en el
   desplegable de configuraciones de CMake.
5. Menú `Compilar` → `Compilar todo` (o clic derecho sobre
   `CMakeLists.txt` → `Compilar`).
6. Cuando termine, el plugin queda en una ruta parecida a:
   ```
   SunoBridge\out\build\x64-Release\SunoBridge_artefacts\Release\VST3\SunoBridge.vst3
   ```
   (la carpeta `SunoBridge.vst3` completa es el plugin — cópiala entera).

## Instalarlo en FL Studio

1. Copia la carpeta `SunoBridge.vst3` a tu carpeta de plugins VST3, por
   ejemplo:
   `C:\Program Files\Common Files\VST3\`
   — o, si prefieres no tocar Archivos de programa, pégala en cualquier
   carpeta tuya (p. ej. `Documentos\SunoBridge\VST3`) y añade esa carpeta
   como ruta extra de búsqueda en FL Studio.
2. En FL Studio: `OPTIONS` → `Manage plugins` (o `File settings`) → añade
   esa carpeta si hace falta → pulsa **Find plugins / Find more plugins**.
3. Ya debería aparecer **SunoBridge** en tu lista de generadores/instrumentos.
   Añádelo a un canal como cualquier otro instrumento.
4. Abre su interfaz, pulsa **"Browse folder..."** y elige la carpeta donde
   caen tus exportaciones de Suno Studio (por defecto usa tu carpeta de
   Descargas). A partir de ahí, cada nueva exportación se carga sola.

## Si algo falla al compilar

Copia y pégame el error completo de Visual Studio (la ventana "Salida" /
"Output" → "CMake"), y lo arreglamos desde aquí.

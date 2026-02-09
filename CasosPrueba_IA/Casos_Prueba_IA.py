import os
import csv
import json
from pathlib import Path
import google.generativeai as genai  # ← API ANTIGUA

# ==============================
# CONFIGURACIÓN
# ==============================

DEFAULT_MODEL_NAME = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.3

def setup_gemini(api_key, model_name=DEFAULT_MODEL_NAME, temperature=DEFAULT_TEMPERATURE):
    """
    Configura la API de Gemini y devuelve el MODELO (no una tupla).
    """
    if not api_key:
        raise ValueError("❌ La API Key no puede estar vacía.")
    
    # Configurar la API
    genai.configure(api_key=api_key)
    
    # Crear el modelo
    model = genai.GenerativeModel(
        model_name,
        generation_config={"temperature": temperature}
    )
    
    # ← IMPORTANTE: Devuelve el MODELO directamente
    return model


# ==============================
# LECTOR DE HUs
# ==============================

def leer_archivos_hu(carpeta: str):
    """Lee todos los archivos .txt de la carpeta."""
    carpeta_path = Path(carpeta)

    if not carpeta_path.exists():
        raise FileNotFoundError(f"La carpeta {carpeta} no existe.")

    archivos = list(carpeta_path.glob("*.txt"))

    if not archivos:
        raise ValueError("No se encontraron archivos .txt en la carpeta.")

    lista_hu = []
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        lista_hu.append((archivo.name, texto))

    return lista_hu


# ==============================
# NORMALIZAR PASOS
# ==============================

def normalizar_pasos(pasos_raw):
    """Convierte pasos a formato numerado."""
    if isinstance(pasos_raw, list):
        pasos_limpios = []
        for i, paso in enumerate(pasos_raw, start=1):
            paso_str = str(paso).strip()
            if paso_str:
                pasos_limpios.append(f"{i}. {paso_str}")
        return "\n".join(pasos_limpios)

    if isinstance(pasos_raw, str):
        texto = pasos_raw.strip()
        if not texto:
            return ""
        if "1." in texto or "1)" in texto:
            return texto
        
        separadores = ["\n", ";"]
        for sep in separadores:
            if sep in texto:
                partes = [p.strip() for p in texto.split(sep) if p.strip()]
                pasos_limpios = [f"{i}. {p}" for i, p in enumerate(partes, start=1)]
                return "\n".join(pasos_limpios)
        
        return f"1. {texto}"

    return str(pasos_raw)


# ==============================
# GENERACIÓN DE CASOS DE PRUEBA
# ==============================

DEFAULT_PROMPT = """
Eres un ingeniero QA senior, experto en certificación, pruebas técnicas y diseño
estructurado de casos de prueba. Analiza profundamente la Historia de Usuario (HU)
y sus criterios de aceptación, respetando fielmente su alcance y requisitos.

Tu tarea es generar un conjunto amplio y detallado de casos de prueba que incluya:

1. Functional (Funcionales)
2. Negative (Pruebas negativas)
3. Edge Case (Casos extremos / poco frecuentes)
4. Boundary (Pruebas de límite)
5. Usability (Usabilidad / UX)
6. Regression (Regresión)
7. Casos adicionales derivados del análisis implícito de la HU
   (no te limites solo a los criterios, agrega lo que falte).

Cada caso debe estar completamente definido.

CONSIDERACIONES IMPORTANTES:
- Respeta el alcance de la HU, no agregues funcionalidades no mencionadas
- Si la HU menciona aplicación WEB/COMPUTADORA, algo relacionado a Atenea usa: hacer clic, seleccionar con mouse, presionar tecla, 
  ventana del navegador, menú desplegable, cursor
- Si la HU menciona aplicación MÓVIL/CELULAR, algo relacionado a Simon pay o simon movilidad usa: tocar, deslizar, pellizcar, rotar dispositivo, 
  notificación push, pantalla táctil
- En lugar de repetir "verificar", alterna con: validar, comprobar, confirmar, corroborar, 
  inspeccionar, examinar, evaluar, constatar, asegurar, certificar.

FORMATO ESTRICTO DE SALIDA (JSON VÁLIDO):

[
  {{
    "criterio": "Razón o requisito que cubre este caso.",
    "id_caso": "CP-001",
    "tipo_prueba": "Functional | Negative | Edge Case | Boundary | Regression | Usability",
    "descripcion": "Breve explicación del propósito del caso.",
    "precondiciones": "Estado inicial necesario.",
    "pasos": [
      "Paso 1 en texto claro",
      "Paso 2 en texto claro",
      "Paso 3 en texto claro"
    ],
    "resultado_esperado": "Resultado esperado que se debe validar.",
    "prioridad": "Alta | Media | Baja",
    "Automatizar": "se puede automatizar el proceso de la prueba si | no"  
  }}
]
CRITERIOS DE AUTOMATIZAR:
-***Automatización atenea***
- **Functional**:si se pueden automatizar
- **Negative**:si se pueden automatizar
- **Edge Case**:si se puede automatizar
- **Boundary**:si se puede automatizar
- **Usability**:si se puede automatizar
- **Regression**:si se puede automatizar
- **Casos adicionales derivados del análisis implícito de la HU**:no se puede automatizar**:no se puede automatizar
- ***Automatizar***
- **si**: esta dentro de las que se pueden automatizar
- **no**: no se puede automatizar

CRITERIOS PARA ASIGNAR PRIORIDAD:
- **Alta**: Casos funcionales críticos, flujos principales, seguridad, pérdida de datos
- **Media**: Casos negativos importantes, validaciones de negocio, usabilidad
- **Baja**: Edge cases poco frecuentes, casos estéticos, escenarios raros

REQUISITOS IMPORTANTES:
- "pasos" DEBE ser SIEMPRE una LISTA de strings.
- Cada caso debe tener un "id_caso" único (CP-001, CP-002, ...).
- NO agregues texto fuera del JSON.
- NO agregues explicaciones antes ni después del JSON.

HU COMPLETA Y CRITERIOS PARA ANALIZAR:
{hu_texto}
"""

def generar_casos_prueba(model, hu_texto: str, custom_prompt=None):
    """
    Genera casos de prueba usando el modelo.
    model: debe ser un objeto GenerativeModel (NO una tupla)
    """
    if custom_prompt:
        try:
            prompt = custom_prompt.format(hu_texto=hu_texto)
        except KeyError:
            prompt = custom_prompt + f"\n\nHU: {hu_texto}"
    else:
        prompt = DEFAULT_PROMPT.format(hu_texto=hu_texto)

    # ← AQUÍ se usa .generate_content() del modelo
    respuesta = model.generate_content(prompt)
    texto = respuesta.text

    inicio = texto.find("[")
    fin = texto.rfind("]") + 1

    if inicio == -1 or fin == 0:
        raise ValueError("No se encontró JSON válido en la respuesta.")

    json_text = texto[inicio:fin]
    casos = json.loads(json_text)

    if not isinstance(casos, list):
        raise ValueError("El JSON devuelto no es una lista de casos.")

    for caso in casos:
        pasos_raw = caso.get("pasos", "")
        caso["pasos"] = normalizar_pasos(pasos_raw)

    return casos


# ==============================
# GUARDAR CSV
# ==============================

def guardar_csv(casos, archivo_salida="casos_prueba_total.csv"):
    campos = [
        "archivo_hu", 
        "criterio", 
        "id_caso", 
        "tipo_prueba",
        "prioridad",
        "Automatizar", 
        "descripcion", 
        "precondiciones", 
        "pasos", 
        "resultado_esperado"
    ]

    with open(archivo_salida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos, delimiter=';')
        writer.writeheader()
        for caso in casos:
            fila = {campo: caso.get(campo, "") for campo in campos}
            writer.writerow(fila)

    print(f"✅ Archivo generado: {archivo_salida}")


# ==============================
# PROGRAMA PRINCIPAL (para consola)
# ==============================

if __name__ == "__main__":
    carpeta_hus = "HUs"
    archivo_salida = "casos_prueba_total.csv"

    print("📄 Leyendo HUs...")
    hu_archivos = leer_archivos_hu(carpeta_hus)

    API_KEY = os.getenv("GEMINI_API_KEY")  # Cargar desde variable de entorno
    
    if not API_KEY:
        print("❌ No se encontró GEMINI_API_KEY en las variables de entorno")
        print("💡 Crea un archivo .env con: GEMINI_API_KEY=tu_api_key")
        exit(1)

    try:
        model = setup_gemini(API_KEY)
        print(f"✅ Modelo configurado: {DEFAULT_MODEL_NAME}")
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)

    todos_los_casos = []

    for nombre_archivo, contenido in hu_archivos:
        print(f"➡ Procesando HU: {nombre_archivo}...")
        try:
            casos = generar_casos_prueba(model, contenido)
            for c in casos:
                c["archivo_hu"] = nombre_archivo
            todos_los_casos.extend(casos)
            print(f"   ✔ {len(casos)} casos generados")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    if todos_los_casos:
        guardar_csv(todos_los_casos, archivo_salida)
        print("🎉 Proceso completado.")
    else:
        print("⚠ No se generaron casos de prueba.")
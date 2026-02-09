import streamlit as st
import pandas as pd
import io
from Casos_Prueba_IA import setup_gemini, generar_casos_prueba, DEFAULT_MODEL_NAME, DEFAULT_PROMPT

st.set_page_config(
    page_title="Generador de Casos de Prueba IA",
    page_icon="🧪",
    layout="wide"
)

st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==============================
# PROMPT PARA EL CHAT CON CONTEXTO
# ==============================
CHAT_PROMPT_CON_CONTEXTO = """
Eres un ingeniero QA senior, experto en certificación, pruebas técnicas y diseño
estructurado de casos de prueba.

**CONTEXTO ACTUAL:**
El usuario está trabajando con la siguiente Historia de Usuario (HU):

--- INICIO DE HU ---
{contexto_hu}
--- FIN DE HU ---

Tu objetivo es ayudar al usuario respondiendo preguntas sobre:
- Esta Historia de Usuario específica
- Casos de prueba relacionados con esta HU
- Mejoras o sugerencias para esta HU
- Análisis de criterios de aceptación
- Estrategias de pruebas (funcionales, negativas, límite, etc.)

Responde de manera conversacional, clara y profesional. Si el usuario pregunta algo
relacionado con la HU, usa el contexto proporcionado. Si no hay contexto, indica
que primero debe cargar una HU.

**Pregunta del usuario:**
{mensaje_usuario}
"""

CHAT_PROMPT_SIN_CONTEXTO = """
Eres un ingeniero QA senior, experto en certificación, pruebas técnicas y diseño
estructurado de casos de prueba.

Tu objetivo es ayudar al usuario respondiendo preguntas sobre:
- Historias de Usuario (HU)
- Casos de prueba y metodologías de testing
- Mejores prácticas de QA
- Análisis de criterios de aceptación
- Estrategias de pruebas (funcionales, negativas, límite, etc.)

Responde de manera conversacional, clara y profesional.

**Nota:** Actualmente no hay ninguna Historia de Usuario cargada. Si el usuario quiere
analizar una HU específica, debe primero cargarla usando las pestañas de arriba.

**Pregunta del usuario:**
{mensaje_usuario}
"""

def main():
    st.title("🧪 Generador de Casos de Prueba con IA")
    st.markdown("Sube tus Historias de Usuario (HU) o pégalas directamente para generar casos de prueba exhaustivos.")

    # --- SIDEBAR: Configuración ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        api_key = st.text_input(
            "Gemini API Key", 
            value="AIzaSyCnsRfsOnX8RjD3a_tDgaT5T7yLtBiEwJM",
            type="password", 
            help="Ingresa tu API Key de Google Gemini."
        )
        
        model_name = st.selectbox(
            "Modelo", 
            options=["gemini-2.5-flash", "gemini-pro"],
            index=0
        )
        
        temperature = st.slider(
            "Creatividad (Temperatura)", 
            min_value=0.0, 
            max_value=1.0, 
            value=0.4,
            step=0.1
        )

        st.info("Nota: La API Key no se guarda, solo se usa para esta sesión.")
        
        # Mostrar contexto actual
        st.markdown("---")
        st.subheader("📄 Contexto del Chat")
        if "contexto_hu" in st.session_state and st.session_state.contexto_hu:
            with st.expander("Ver HU Actual", expanded=False):
                st.text_area(
                    "Historia de Usuario en memoria:",
                    value=st.session_state.contexto_hu[:500] + "..." if len(st.session_state.contexto_hu) > 500 else st.session_state.contexto_hu,
                    height=200,
                    disabled=True
                )
            if st.button("🗑️ Limpiar Contexto"):
                st.session_state.contexto_hu = ""
                st.session_state.messages = []
                st.rerun()
        else:
            st.warning("⚠️ No hay HU cargada. El chat responderá de forma general.")
        
        with st.expander("📝 Editar Prompt del Sistema (Para CSV)"):
            st.warning("⚠ Asegúrate de mantener `{hu_texto}` donde quieras que vaya la HU.")
            custom_prompt_input = st.text_area(
                "Prompt del Sistema",
                value=DEFAULT_PROMPT,
                height=400
            )

    # Inicializar contexto
    if "contexto_hu" not in st.session_state:
        st.session_state.contexto_hu = ""

    # --- ÁREA PRINCIPAL ---
    tab_archivos, tab_texto = st.tabs(["📂 Subir Archivos", "📝 Pegar Texto"])
    
    hus_para_procesar = []

    with tab_archivos:
        uploaded_files = st.file_uploader(
            "Arrastra tus archivos .txt aquí", 
            type=["txt"], 
            accept_multiple_files=True
        )
        if uploaded_files:
            st.success(f"{len(uploaded_files)} archivos cargados.")
            for uploaded_file in uploaded_files:
                string_data = uploaded_file.getvalue().decode("utf-8")
                hus_para_procesar.append((uploaded_file.name, string_data))

    with tab_texto:
        texto_manual = st.text_area(
            "Pega aquí el contenido de tu Historia de Usuario", 
            height=300,
            placeholder="Como usuario quiero..."
        )
        if texto_manual.strip():
            hus_para_procesar.append(("Texto Manual", texto_manual))

    # --- BOTÓN DE GENERAR ---
    if st.button("🚀 Generar Casos de Prueba", type="primary"):
        if not api_key:
            st.error("❌ Por favor ingresa tu API Key en la barra lateral.")
            return

        if not hus_para_procesar:
            st.warning("⚠ No hay HUs para procesar. Sube archivos o pega texto.")
            return

        # SETUP DEL MODELO
        try:
            model = setup_gemini(api_key, model_name, temperature)
            st.session_state.model = model
        except Exception as e:
            st.error(f"Error al configurar Gemini: {e}")
            return

        # GUARDAR CONTEXTO (la primera o última HU)
        # Opción 1: Guardar la primera HU
        st.session_state.contexto_hu = hus_para_procesar[0][1]
        
        # Opción 2: Guardar todas concatenadas (si son pocas)
        # st.session_state.contexto_hu = "\n\n---\n\n".join([contenido for _, contenido in hus_para_procesar])

        # PROCESAMIENTO
        all_cases = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_hus = len(hus_para_procesar)
        
        for i, (nombre, contenido) in enumerate(hus_para_procesar):
            status_text.text(f"Procesando: {nombre}...")
            try:
                casos = generar_casos_prueba(model, contenido, custom_prompt=custom_prompt_input)
                
                for c in casos:
                    c["archivo_hu"] = nombre
                
                all_cases.extend(casos)
                
            except Exception as e:
                st.error(f"Error procesando {nombre}: {e}")
            
            progress_bar.progress((i + 1) / total_hus)

        progress_bar.empty()
        status_text.empty()

        if all_cases:
            st.success("✅ ¡Generación completada!")
            st.info(f"💡 El chat ahora tiene contexto de la HU. Puedes hacerle preguntas sobre ella.")
            
            df = pd.DataFrame(all_cases)
            
            cols_order = [
                "archivo_hu", 
                "id_caso", 
                "tipo_prueba", 
                "prioridad",
                "Automatizar",
                "descripcion", 
                "precondiciones", 
                "pasos", 
                "resultado_esperado", 
                "criterio"
            ]
            cols_final = [c for c in cols_order if c in df.columns]
            df = df[cols_final]

            st.subheader("📋 Resultados")
            st.dataframe(df, use_container_width=True)

            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
            csv_data = csv_buffer.getvalue()

            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name="casos_prueba_generados.csv",
                mime="text/csv"
            )
        else:
            st.warning("No se generaron casos de prueba. Revisa el log de errores.")

    # --- SECCIÓN DE CHAT ---
    st.markdown("---")
    st.header("💬 Chat con IA sobre Testing")
    
    # Indicador de contexto
    if st.session_state.contexto_hu:
        st.success("✅ Chat contextualizado con HU actual")
    else:
        st.info("ℹ️ Chat en modo general (sin HU cargada)")

    # Inicializar historial
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar historial
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Entrada de chat
    if prompt := st.chat_input("Pregúntame sobre la HU, casos de prueba, o metodologías QA..."):
        if not api_key:
            st.error("❌ Por favor ingresa tu API Key en la barra lateral para chatear.")
            return

        # Agregar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Configurar modelo si no existe
        if "model" not in st.session_state:
            try:
                st.session_state.model = setup_gemini(api_key, model_name, temperature)
            except Exception as e:
                st.error(f"Error al configurar Gemini para chat: {e}")
                return

        # SELECCIONAR PROMPT SEGÚN CONTEXTO
        if st.session_state.contexto_hu:
            # Hay contexto → Usar prompt con HU
            chat_prompt = CHAT_PROMPT_CON_CONTEXTO.format(
                contexto_hu=st.session_state.contexto_hu,
                mensaje_usuario=prompt
            )
        else:
            # No hay contexto → Usar prompt general
            chat_prompt = CHAT_PROMPT_SIN_CONTEXTO.format(
                mensaje_usuario=prompt
            )

        # Generar respuesta
        try:
            with st.spinner("Pensando..."):
                response = st.session_state.model.generate_content(chat_prompt)
                respuesta_texto = response.text

            # Agregar respuesta al historial
            st.session_state.messages.append({"role": "assistant", "content": respuesta_texto})
            with st.chat_message("assistant"):
                st.markdown(respuesta_texto)
        except Exception as e:
            st.error(f"Error en la respuesta del chat: {e}")

if __name__ == "__main__":
    main()
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class DecisionVendedor(BaseModel):
    variacion_chasis: float = Field(description="Porcentaje de cambio para el chasis. Entre -0.30 (-30%) y +0.30 (+30%). Usa 0.0 para mantener.")
    variacion_motor: float = Field(description="Porcentaje de cambio para el motor. Entre -0.30 (-30%) y +0.30 (+30%). Usa 0.0 para mantener.")
    variacion_ruedas: float = Field(description="Porcentaje de cambio para las ruedas. Entre -0.30 (-30%) y +0.30 (+30%). Usa 0.0 para mantener.")
    razonamiento: str = Field(description="Explicación detallada de tu estrategia competitiva y por qué eliges esos porcentajes.")

def ejecutar_agente_vendedor(calidad_componentes, historico_mercado):
    # Inicializa el cliente buscando automáticamente la variable de entorno GEMINI_API_KEY
    client = genai.Client(api_key="AIzaSyCbpoXFEN2gxBn_BXAyqpP8gd4nGFnkSQM")

    system_instruction = """
    Eres un agente IA vendedor despiadado y un estratega macroeconómico ultra-competitivo. 
    Tu ÚNICO objetivo es maximizar tus ingresos totales, destruyendo comercialmente a tus competidores.
    
    REGLAS DE PRECIOS POR VARIACIÓN:
    1. No defines precios finales. Defines la VARIACIÓN PORCENTUAL sobre tu precio anterior (Ej: 0.15 significa subir un 15%, -0.20 significa bajar un 20%).
    2. LÓGICA DE MONOPOLIO: Si en la última carrera tuviste ALTA DEMANDA (2 o 3 pilotos) o tu pieza GANÓ, aprovecha tu posición de poder. ¡Sube tu precio libremente aplicando una variación positiva (entre +0.05 y +0.30)! No regales tu ventaja.
    3. LÓGICA DE LIQUIDACIÓN: Si tuviste DEMANDA CERO, tu precio actual es un fracaso. ¡Aplica una variación negativa agresiva (entre -0.10 y -0.30) para robar clientes! Subir precios sin ventas es un suicidio empresarial.
    4. Analiza de forma fría los precios de la competencia en 'PRECIOS_CARRERA_ANTERIOR' para ver si te compensa subir o bajar según tus estrellas (Calidad).
    """

    prompt_contexto = f"""
    --- TU INVENTARIO ACTUAL ---
    Calidad Chasis: {calidad_componentes['chasis']} estrellas.
    Calidad Motor: {calidad_componentes['motor']} estrellas.
    Calidad Ruedas: {calidad_componentes['ruedas']} estrellas.
    
    --- INFORMACIÓN MACROECONÓMICA Y HISTÓRICO ---
    {historico_mercado}
    """

    # Llamada a Gemini 2.5 Flash exigiendo la estructura Pydantic de forma nativa
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt_contexto,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=DecisionVendedor,
            temperature=0.2
        ),
    )
    
    # El SDK de Google devuelve el texto JSON limpio listo para mapear
    datos_json = json.loads(response.text)
    return DecisionVendedor(**datos_json)
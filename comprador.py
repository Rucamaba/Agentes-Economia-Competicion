import json
from typing import Literal
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class EleccionKart(BaseModel):
    razonamiento: str = Field(
        description="Analiza matemáticamente las eficiencias (Calidad/Precio) y justifica los cálculos AQUÍ antes de elegir."
    )
    vendedor_chasis: Literal["A", "B", "C"] = Field(description="Letra exacta del vendedor para el chasis")
    vendedor_motor: Literal["A", "B", "C"] = Field(description="Letra exacta del vendedor para el motor")
    vendedor_ruedas: Literal["A", "B", "C"] = Field(description="Letra exacta del vendedor para las ruedas")

def ejecutar_agente_comprador(nombre_modelo, catalogo_precios):
    client = genai.Client(api_key="AIzaSyCbpoXFEN2gxBn_BXAyqpP8gd4nGFnkSQM")  # Reemplaza con tu clave de API o configúralo en la variable de entorno GEMINI_API_KEY

    system_instruction = f"""
    Eres '{nombre_modelo}', un piloto de karts e ingeniero analítico controlado por IA. 
    Tu único objetivo es ganar el campeonato maximizando tus puntos totales (por posición y por ahorro).
    
    REGLAS DE OPTIMIZACIÓN FRÍA:
    1. Presupuesto estricto: Máximo 100€. La suma de tus 3 componentes NO puede superar los 100€. Es válido sacrificar piezas para ajustarte al presupuesto si consideras que te compensa.
    2. El kart DEBE tener 1 Chasis, 1 Motor y 1 Ruedas. Cada pieza faltante dañará tu rendimiento.
    3. REEVALUACIÓN CONSTANTE (Evita el conformismo): En cada carrera, el mercado cambia. Aunque hayas ganado la carrera anterior, debes analizar TODO el catálogo actual de cero. Si un vendedor ofrece más calidad por un precio similar, o la misma calidad más barata, DEBES cambiar de pieza inmediatamente. Quedarte con la misma configuración teniendo opciones mejores es un error grave.
    4. CÁLCULO DE TEORÍA DE JUEGOS: Los puntos de ahorro (2 al más barato, 1 al segundo) pueden ser vitales, pero siempre va a dar más puntos ganar la carrera. Analiza si te compensa sacrificar un par de estrellas para asegurar 2 puntos de ahorro garantizados si los vendedores han inflado los precios.
    5. PENSAMIENTO ESTRUCTURADO MANDATORIO: Los valores finales de las variables 'vendedor_chasis', 'vendedor_motor' y 'vendedor_ruedas' DEBEN coincidir exactamente con la conclusión de tus cálculos del razonamiento. Es perfectamente válido elegir la misma letra (Ej: C, C, C) para las tres piezas si es la mejor opción del mercado.
    """

    prompt_contexto = f"""
    --- CATÁLOGO DE MERCADO ACTUAL ---
    {catalogo_precios}
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt_contexto,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=EleccionKart,
            temperature=0.1
        ),
    )
    
    datos_json = json.loads(response.text)
    return EleccionKart(**datos_json)
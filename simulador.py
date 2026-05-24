import random
import re
from itertools import combinations
from comprador import AgenteComprador
from vendedor import AgenteVendedor
from economia_costes import (
    calcular_coste_bruto,
    calcular_coste_imputable,
)
import sys
import atexit
import datetime

# Duplicar la salida estándar y de error a un archivo de registro
_LOG_FILENAME = "ejecucion_simulador.md"
try:
    # Abrir en modo sobrescribir para no acumular ejecuciones previas
    _log_file = open(_LOG_FILENAME, "w", encoding="utf-8")
except Exception:
    _log_file = None

class _Tee:
    def __init__(self, *files):
        self._files = files

    def write(self, data):
        for f in self._files:
            try:
                f.write(data)
            except Exception:
                pass
        for f in self._files:
            try:
                f.flush()
            except Exception:
                pass

    def flush(self):
        for f in self._files:
            try:
                f.flush()
            except Exception:
                pass

if _log_file is not None:
    header = f"# Ejecución simulador: {datetime.datetime.now().isoformat()}\n\n"
    try:
        _log_file.write(header)
        _log_file.flush()
    except Exception:
        pass
    sys.stdout = _Tee(sys.stdout, _log_file)
    sys.stderr = _Tee(sys.stderr, _log_file)

def _close_log():
    try:
        if _log_file is not None:
            _log_file.write(f"\n\n--- Ejecución finalizada: {datetime.datetime.now().isoformat()} ---\n")
            _log_file.close()
    except Exception:
        pass

atexit.register(_close_log)

def formatear_variacion_precio(precio_actual, precio_anterior):
    if precio_anterior is None:
        return "(sin referencia)"

    variacion = round(precio_actual - precio_anterior, 2)
    signo = "+" if variacion >= 0 else ""
    return f"({signo}{variacion:.2f}€)"


def calcular_mejor_configuracion(componentes, presupuesto_max=100.0, contratos_activos=None):
    mejor_opcion = None

    if contratos_activos is None:
        contratos_activos = []

    for cantidad in range(1, len(componentes) + 1):
        for subset in combinations(componentes, cantidad):
            gasto = calcular_coste_bruto(subset)
            gasto_imputable = calcular_coste_imputable(subset, contratos_activos)

            if gasto_imputable > presupuesto_max:
                continue

            piezas_faltantes = len(componentes) - len(subset)
            base_sin_penalizacion = sum(componente["calidad"] for componente in subset)
            rendimiento = round(base_sin_penalizacion * (0.8 ** piezas_faltantes), 4)

            candidato = {
                "configuracion": ",".join(componente["vendedor"] for componente in subset),
                "gasto_bruto": gasto,
                "gasto_imputable": gasto_imputable,
                "coste_economico": gasto_imputable,
                "vel_base": rendimiento,
                "piezas_faltantes": piezas_faltantes,
                "base_sin_penalizacion": round(base_sin_penalizacion, 4),
                "piezas_usadas": len(subset),
                "componentes_usados": [dict(componente) for componente in subset],
            }

            if mejor_opcion is None:
                mejor_opcion = candidato
                continue

            mejor_rendimiento = mejor_opcion["vel_base"]
            if rendimiento > mejor_rendimiento:
                mejor_opcion = candidato
                continue

            if rendimiento == mejor_rendimiento:
                if len(subset) > mejor_opcion["piezas_usadas"]:
                    mejor_opcion = candidato
                    continue

                if gasto_imputable < mejor_opcion["gasto_imputable"]:
                    mejor_opcion = candidato

    return mejor_opcion


def normalizar_vendedor(valor):
    if valor is None:
        return None

    texto = str(valor).upper().strip()
    match = re.search(r"\b([A-Z])\b", texto)
    if match:
        return match.group(1)

    for caracter in texto:
        if caracter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            return caracter

    return None


def aplicar_guardrail_precio(precio_nuevo, precio_anterior, demanda_ultima, fue_ganador):
    ajustado = float(precio_nuevo)
    return round(max(1.0, ajustado), 2)


def repartir_puntos_por_empates(elementos_ordenados, clave_igualdad, puntos_por_puesto, max_beneficiarios=None):
    reparto = {}
    indice_puesto = 0
    indice = 0

    while indice < len(elementos_ordenados) and indice_puesto < len(puntos_por_puesto):
        valor = clave_igualdad(elementos_ordenados[indice])
        grupo = [elementos_ordenados[indice]]
        indice += 1

        while indice < len(elementos_ordenados) and clave_igualdad(elementos_ordenados[indice]) == valor:
            grupo.append(elementos_ordenados[indice])
            indice += 1

        if max_beneficiarios is not None and indice_puesto + len(grupo) > max_beneficiarios:
            break

        puntos = puntos_por_puesto[indice_puesto]
        for elemento in grupo:
            reparto[elemento["piloto"]] = puntos

        indice_puesto += len(grupo)

    return reparto


TOTAL_CARRERAS = 10
PRESUPUESTO_TOTAL_CAMPEONATO = 1000.0
PRECIO_MAX_PIEZA = 100.0
DURACION_CONTRATO_EXCLUSIVIDAD = 2
VENTAJA_NOTABLE_ABSOLUTA = 2.0
BONUS_MENOR_GASTO_FINAL = 5
PUNTOS_POSICION = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
PUNTOS_AHORRO = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
BONO_CLASIFICACION_POR_POSICION = [100, 90, 80, 70, 60, 50, 45, 40, 35, 30, 25, 23, 21, 19, 17, 15, 13, 11, 10, 9]


def obtener_contratos_piloto(piloto, contratos_activos):
    return [contrato for contrato in contratos_activos if contrato["piloto"] == piloto]


def obtener_contrato_piloto_slot(piloto, slot, contratos_activos):
    for contrato in contratos_activos:
        if contrato["piloto"] == piloto and contrato["slot"] == slot:
            return contrato
    return None


def hay_contrato_vendedor_slot(vendedor, slot, contratos_activos):
    return any(
        contrato["vendedor"] == vendedor and contrato["slot"] == slot
        for contrato in contratos_activos
    )


def hay_contrato_piloto_slot(piloto, slot, contratos_activos):
    return obtener_contrato_piloto_slot(piloto, slot, contratos_activos) is not None


def bloqueos_exclusividad_para_piloto(piloto, contratos_activos):
    bloqueos = {"chasis": set(), "motor": set(), "ruedas": set()}
    for contrato in contratos_activos:
        if contrato["piloto"] != piloto:
            bloqueos[contrato["slot"]].add(contrato["vendedor"])
    return bloqueos


def pieza_bloqueada_para_piloto(piloto, slot, vendedor, contratos_activos):
    for contrato in contratos_activos:
        if contrato["slot"] == slot and contrato["vendedor"] == vendedor and contrato["piloto"] != piloto:
            return True
    return False


def propietario_exclusividad(slot, vendedor, contratos_activos):
    for contrato in contratos_activos:
        if contrato["slot"] == slot and contrato["vendedor"] == vendedor:
            return contrato["piloto"]
    return None


def proponer_contrato_exclusividad(
    piloto,
    vendedores,
    contratos_activos,
    historial_piezas_piloto,
    slot_objetivo=None,
    precios_actuales=None,
):
    mejor_candidato = None

    for slot in ([slot_objetivo] if slot_objetivo else ["chasis", "motor", "ruedas"]):
        ranking = sorted(vendedores.items(), key=lambda item: item[1][slot], reverse=True)
        if len(ranking) < 2:
            continue

        vendedor_top, datos_top = ranking[0]
        _, datos_segundo = ranking[1]
        ventaja = round(datos_top[slot] - datos_segundo[slot], 2)

        # Solo se puede pedir exclusividad de una pieza que ya se haya usado antes.
        if (slot, vendedor_top) not in historial_piezas_piloto:
            continue

        if ventaja < VENTAJA_NOTABLE_ABSOLUTA:
            continue

        # El piloto solo solicita contrato si la ventaja justifica el precio actual de la pieza.
        if precios_actuales and vendedor_top in precios_actuales:
            precio_slot = precios_actuales[vendedor_top].get(slot)
        else:
            precio_slot = None
        if precio_slot is None:
            precio_slot = {"chasis": 25.0, "motor": 20.0, "ruedas": 15.0}[slot]

        # Índice básico ventaja/precio
        indice_valor = ventaja / max(precio_slot, 1.0)

        # Consideramos también la tendencia del mercado: si el precio subió respecto a la carrera previa,
        # firmar ahora puede evitar pagar más después. Amplificamos el índice según subida relativa.
        try:
            precio_prev = precios_anterior_carrera.get(vendedor_top, {}).get(slot)
        except Exception:
            precio_prev = None
        subida_relativa = 0.0
        if precio_prev is not None and precio_prev > 0:
            subida_relativa = (precio_slot - precio_prev) / precio_prev
        # Aumentamos el índice según la subida relativa (sensibilidad moderada, tope 0.25)
        indice_valor += min(0.25, max(0.0, subida_relativa) * 0.5)

        # También valoramos demanda reciente: más demanda implica mayor probabilidad de subida futura.
        try:
            demanda_reciente = estadisticas_ultima_carrera["demanda"][slot].get(vendedor_top, 0)
        except Exception:
            demanda_reciente = 0
        if demanda_reciente >= 2:
            indice_valor += 0.05

        # Umbral configurable para solicitar contrato
        UMBRAL_INDICE_CONTRATO = 0.08
        if indice_valor < UMBRAL_INDICE_CONTRATO:
            continue

        candidato = {
            "piloto": piloto,
            "vendedor": vendedor_top,
            "slot": slot,
            "ventaja": ventaja,
        }

        if mejor_candidato is None or candidato["ventaja"] > mejor_candidato["ventaja"]:
            mejor_candidato = candidato

    return mejor_candidato


def elegir_ganador_solicitud_por_marketing(solicitudes, puntuaciones_pilotos):
    return sorted(
        solicitudes,
        key=lambda s: (
            puntuaciones_pilotos.get(s["piloto"], 0),
            s["ventaja"],
            s["piloto"],
        ),
        reverse=True,
    )[0]


def obtener_fidelidad_pieza(historial_uso_piezas, piloto, slot, vendedor):
    return (
        historial_uso_piezas
        .get(piloto, {})
        .get(slot, {})
        .get(vendedor, 0)
    )


def cotizar_oferta_contrato(
    solicitud,
    precio_actual_pieza,
    puntuaciones_pilotos,
    historial_uso_piezas,
    demanda_reciente_slot,
    total_pilotos,
    carrera_actual,
):
    piloto = solicitud["piloto"]
    vendedor = solicitud["vendedor"]
    slot = solicitud["slot"]
    ventaja = solicitud["ventaja"]

    max_puntos = max(1, max(puntuaciones_pilotos.values(), default=1))
    marketing_norm = min(1.0, puntuaciones_pilotos.get(piloto, 0) / max_puntos)

    fidelidad_uso = obtener_fidelidad_pieza(historial_uso_piezas, piloto, slot, vendedor)
    fidelidad_norm = min(1.0, fidelidad_uso / max(1, carrera_actual - 1))

    demanda_norm = min(1.0, demanda_reciente_slot / max(1.0, total_pilotos * 0.35))
    ventaja_norm = min(1.0, max(0.0, ventaja - VENTAJA_NOTABLE_ABSOLUTA) / max(1.0, VENTAJA_NOTABLE_ABSOLUTA))
    duracion_norm = max(0.0, (DURACION_CONTRATO_EXCLUSIVIDAD - 1) / 3.0)

    prima = (
        0.05
        + (0.16 * marketing_norm)
        - (0.10 * fidelidad_norm)
        + (0.22 * demanda_norm)
        + (0.08 * ventaja_norm)
        + (0.06 * duracion_norm)
    )
    prima = max(-0.10, min(0.60, prima))

    precio_ronda_contrato = round(max(1.0, precio_actual_pieza * (1.0 + prima)), 2)
    coste_adelantado = round(precio_ronda_contrato * DURACION_CONTRATO_EXCLUSIVIDAD, 2)

    return {
        "prima": round(prima, 4),
        "precio_ronda_contrato": precio_ronda_contrato,
        "coste_adelantado": coste_adelantado,
        "fidelidad_uso": fidelidad_uso,
        "marketing_puntos": puntuaciones_pilotos.get(piloto, 0),
    }


def piloto_acepta_oferta_contrato(solicitud, oferta, saldo_actual):
    if saldo_actual < oferta["coste_adelantado"]:
        return False, "sin saldo suficiente"

    indice_valor = solicitud["ventaja"] / max(1.0, oferta["precio_ronda_contrato"])
    ratio_coste_saldo = oferta["coste_adelantado"] / max(1.0, saldo_actual)

    if indice_valor < 0.09:
        return False, "precio poco rentable para la ventaja"

    if ratio_coste_saldo > 0.60 and indice_valor < 0.16:
        return False, "adelanto demasiado alto para su saldo"

    return True, "acepta"


def vendedor_prefiere_mercado_abierto(
    solicitudes,
    demanda_reciente_slot,
    total_pilotos,
):
    intensidad_solicitudes = len(solicitudes) / max(1.0, total_pilotos)
    demanda_alta = demanda_reciente_slot >= max(3, int(0.20 * total_pilotos))
    solicitudes_muy_altas = intensidad_solicitudes >= 0.35

    if demanda_alta and solicitudes_muy_altas:
        return True, "demanda alta: compensa vender a muchos pilotos sin bloquear pieza"
    return False, "aceptable negociar exclusividad"


def elegir_ganador_entre_aceptadas(
    aceptadas,
    puntuaciones_pilotos,
):
    if not aceptadas:
        return None, "sin_aceptadas"

    orden_marketing = sorted(
        aceptadas,
        key=lambda s: (
            puntuaciones_pilotos.get(s["piloto"], 0),
            s.get("ventaja", 0),
            s["piloto"],
        ),
        reverse=True,
    )
    orden_fidelidad = sorted(
        aceptadas,
        key=lambda s: (
            s.get("fidelidad_uso", 0),
            puntuaciones_pilotos.get(s["piloto"], 0),
            s.get("ventaja", 0),
            s["piloto"],
        ),
        reverse=True,
    )

    mejor_marketing = orden_marketing[0]
    segundo_marketing = orden_marketing[1] if len(orden_marketing) > 1 else None
    gap_marketing = (
        puntuaciones_pilotos.get(mejor_marketing["piloto"], 0)
        - puntuaciones_pilotos.get(segundo_marketing["piloto"], 0)
        if segundo_marketing
        else puntuaciones_pilotos.get(mejor_marketing["piloto"], 0)
    )

    mejor_fidelidad = orden_fidelidad[0]
    segundo_fidelidad = orden_fidelidad[1] if len(orden_fidelidad) > 1 else None
    gap_fidelidad = (
        mejor_fidelidad.get("fidelidad_uso", 0) - segundo_fidelidad.get("fidelidad_uso", 0)
        if segundo_fidelidad
        else mejor_fidelidad.get("fidelidad_uso", 0)
    )

    if gap_fidelidad > max(1, gap_marketing):
        return mejor_fidelidad, "fidelidad"
    return mejor_marketing, "marketing"


def inicializar_estadisticas_contrato(carrera_firma, solicitudes_iniciales):
    return {
        "carrera_firma": carrera_firma,
        "solicitudes_iniciales": solicitudes_iniciales,
        "uso_rondas": 0,
        "victorias_con_pieza": 0,
        "posicion_suma": 0,
        "posiciones_registradas": 0,
    }


def registrar_uso_contrato(contrato, posicion_podio, fue_ganador):
    contrato["uso_rondas"] += 1
    contrato["posicion_suma"] += posicion_podio
    contrato["posiciones_registradas"] += 1
    if fue_ganador:
        contrato["victorias_con_pieza"] += 1


def calcular_factor_subida_post_contrato(contrato, carrera_actual, total_carreras):
    solicitudes = max(1, contrato.get("solicitudes_iniciales", 1))
    interes_norm = min(1.0, max(0.0, (solicitudes - 1) / 2.0))

    usos = max(1, contrato.get("uso_rondas", 0))
    victorias_norm = min(1.0, max(0.0, contrato.get("victorias_con_pieza", 0) / usos))

    if contrato.get("posiciones_registradas", 0) > 0:
        posicion_media = contrato["posicion_suma"] / contrato["posiciones_registradas"]
    else:
        posicion_media = 3.0
    posicion_norm = min(1.0, max(0.0, (4.0 - posicion_media) / 3.0))

    antiguedad_ronda = max(0, carrera_actual - contrato.get("carrera_firma", carrera_actual))
    antiguedad_norm = min(1.0, antiguedad_ronda / max(1, total_carreras - 1))

    factor = (
        0.04 * interes_norm
        + 0.08 * victorias_norm
        + 0.05 * posicion_norm
        + 0.03 * antiguedad_norm
    )

    return round(min(0.25, factor), 4)


def obtener_precio_inicial_por_calidad(calidad, slot):
    """Calcula un precio inicial razonable para una pieza en función
    únicamente de la calidad de la pieza y del tipo de slot.

    No usa información de otros vendedores ni precios previos.
    """
    # Sensibilidades por slot: chasis > motor > ruedas
    factors = {"chasis": 1, "motor": 1, "ruedas": 1}
    factor = factors.get(slot, 1.0)
    # Calidad esperada en [0,10]. Mapear a un rango base [10, 60] y aplicar factor.
    base = 10.0 + (calidad / 10.0) * 50.0
    precio = round(max(1.0, base * factor), 2)
    return precio


def obtener_precio_minimo_dinamico(calidad, slot, demanda_ultima=0, racha_sin_ventas=0):
    precio_base = obtener_precio_inicial_por_calidad(calidad, slot)

    if demanda_ultima <= 0:
        descuento_liquidacion = max(0.60, 0.88 - (0.06 * min(4, max(0, racha_sin_ventas))))
        precio_base = precio_base * descuento_liquidacion

    return round(max(1.0, precio_base), 2)


def calcular_coste_mejora_pieza(calidad_actual, slot, mejora_esperada_abs):
    factor_slot = {"chasis": 1.05, "motor": 0.95, "ruedas": 0.90}
    coste_base = 9.5 + (max(0.0, calidad_actual) ** 2) * 1.6
    factor_mejora = 1.0 + max(0.0, mejora_esperada_abs - 0.5) * 0.18
    return round(coste_base * factor_slot.get(slot, 1.0) * factor_mejora, 2)


def aplicar_mejora_pieza(calidad_actual, mejora_esperada_abs):
    limite_superior = max(0.0, 10.0 - calidad_actual)
    if limite_superior <= 0.0:
        return 0.0, round(min(10.0, calidad_actual), 2)

    mejora_base = max(0.5, mejora_esperada_abs)
    mejora_real = max(0.5, mejora_base * random.uniform(0.45, 1.05))
    mejora_real = min(mejora_real, limite_superior)
    nueva_calidad = round(min(10.0, calidad_actual + mejora_real), 2)
    return round(mejora_real, 4), nueva_calidad


def resumir_presupuestos_pilotos(presupuestos_por_piloto):
    valores = list(presupuestos_por_piloto.values())
    if not valores:
        return {"media": 0.0, "mediana": 0.0, "minima": 0.0, "maxima": 0.0, "bajo_pct": 0.0, "medio_pct": 0.0, "alto_pct": 0.0}

    valores_ordenados = sorted(valores)
    mitad = len(valores_ordenados) // 2
    if len(valores_ordenados) % 2 == 0:
        mediana = (valores_ordenados[mitad - 1] + valores_ordenados[mitad]) / 2.0
    else:
        mediana = valores_ordenados[mitad]

    bajo = sum(1 for valor in valores if valor < 350)
    medio = sum(1 for valor in valores if 350 <= valor < 650)
    alto = sum(1 for valor in valores if valor >= 650)
    total = max(1, len(valores))

    return {
        "media": round(sum(valores) / total, 4),
        "mediana": round(mediana, 4),
        "minima": round(min(valores), 4),
        "maxima": round(max(valores), 4),
        "bajo_pct": round((bajo / total) * 100.0, 4),
        "medio_pct": round((medio / total) * 100.0, 4),
        "alto_pct": round((alto / total) * 100.0, 4),
    }


def estimar_mejora_esperada_por_calidad(calidad_actual):
    if calidad_actual >= 10.0:
        return 0.0

    base = 0.55 + (max(0.0, calidad_actual) / 10.0) * 1.25
    return round(min(2.0, max(0.5, base)), 2)

# ==================================================
# CONFIGURACIÓN INICIAL DEL MERCADO Y VARIABLES
# ==================================================
vendedores = {
    "A": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0, "presupuesto_mejora": 500.0, "mejoras_realizadas": [], "inversion_mejoras": 0.0},
    "B": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0, "presupuesto_mejora": 500.0, "mejoras_realizadas": [], "inversion_mejoras": 0.0},
    "C": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0, "presupuesto_mejora": 500.0, "mejoras_realizadas": [], "inversion_mejoras": 0.0},
    "D": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0, "presupuesto_mejora": 500.0, "mejoras_realizadas": [], "inversion_mejoras": 0.0},
    "E": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0, "presupuesto_mejora": 500.0, "mejoras_realizadas": [], "inversion_mejoras": 0.0}
}

pilotos = [
    "Fernando Alonso",
    "Carlos Sainz",
    "Max Verstappen",
    "Lando Norris",
    "Oscar Piastri",
    "Charles Leclerc",
    "Lewis Hamilton",
    "George Russell",
    "Sergio Perez",
    "Pierre Gasly",
    "Esteban Ocon",
    "Alex Albon",
    "Yuki Tsunoda",
    "Nico Hulkenberg",
    "Liam Lawson",
    "Oliver Bearman",
    "Franco Colapinto",
    "Valtteri Bottas",
    "Kevin Magnussen",
    "Gabriel Bortoleto",
]
puntuaciones_pilotos = {piloto: 0 for piloto in pilotos}
total_gastado_por_piloto = {piloto: 0.0 for piloto in pilotos}
saldo_restante_por_piloto = {piloto: PRESUPUESTO_TOTAL_CAMPEONATO for piloto in pilotos}
bono_clasificacion_por_piloto = {piloto: 0.0 for piloto in pilotos}

# --- CORRECCIÓN CRUCIAL: Inicializamos los objetos aquí, ahora que ya existen las variables anteriores ---
objetos_tiendas = {letra: AgenteVendedor(letra) for letra in vendedores}
objetos_pilotos = {piloto: AgenteComprador(piloto) for piloto in pilotos}

precios_anterior_carrera = {
    letra: {"chasis": None, "motor": None, "ruedas": None}
    for letra in vendedores
}

historico_mercado = "Inicio del campeonato. Ninguna carrera disputada aún."
contratos_exclusividad = []
cooldown_exclusividad = {piloto: {"chasis": 0, "motor": 0, "ruedas": 0} for piloto in pilotos}
historial_piezas_por_piloto = {piloto: set() for piloto in pilotos}
historial_uso_piezas_por_piloto = {
    piloto: {
        "chasis": {letra: 0 for letra in vendedores},
        "motor": {letra: 0 for letra in vendedores},
        "ruedas": {letra: 0 for letra in vendedores},
    }
    for piloto in pilotos
}
subida_post_contrato = {letra: {"chasis": 0.0, "motor": 0.0, "ruedas": 0.0} for letra in vendedores}

estadisticas_ultima_carrera = {
    "demanda": {
        "chasis": {letra: 0 for letra in vendedores},
        "motor": {letra: 0 for letra in vendedores},
        "ruedas": {letra: 0 for letra in vendedores},
    },
    "uso_ganador": {"chasis": None, "motor": None, "ruedas": None},
}

print("==================================================")
print("¡ARRANCA EL CAMPEONATO DE AGENTES IA!")
print(f"💼 Presupuesto total por piloto: {PRESUPUESTO_TOTAL_CAMPEONATO:.2f}€ para todo el campeonato.")
print("🧠 Gestión libre de presupuesto: cada piloto debe administrarse para poder presentar kart válido en todas las carreras.")
print("📌 Regla estratégica: al final del campeonato, el piloto con menor gasto bruto total recibirá +5 puntos. Bajar costes puede ser una jugada ganadora.")
print("==================================================\n")

# Bucle del campeonato: 10 carreras
for carrera in range(1, TOTAL_CARRERAS + 1):
    print(f"--- 🏁 CARRERA {carrera} DE {TOTAL_CARRERAS} ---")

    ingresos_adelantados_por_vendedor = {letra: 0.0 for letra in vendedores}

    calidades_mercado_base = {
        letra: {
            "chasis": round(datos["chasis"], 2),
            "motor": round(datos["motor"], 2),
            "ruedas": round(datos["ruedas"], 2),
        }
        for letra, datos in vendedores.items()
    }
    precios_mercado_base = {
        letra: {
            "chasis": precios_anterior_carrera[letra]["chasis"] if precios_anterior_carrera[letra]["chasis"] is not None else obtener_precio_inicial_por_calidad(datos["chasis"], "chasis"),
            "motor": precios_anterior_carrera[letra]["motor"] if precios_anterior_carrera[letra]["motor"] is not None else obtener_precio_inicial_por_calidad(datos["motor"], "motor"),
            "ruedas": precios_anterior_carrera[letra]["ruedas"] if precios_anterior_carrera[letra]["ruedas"] is not None else obtener_precio_inicial_por_calidad(datos["ruedas"], "ruedas"),
        }
        for letra, datos in vendedores.items()
    }
    presupuestos_mercado_actuales = {
        piloto: round(max(0.0, saldo_restante_por_piloto[piloto]), 2)
        for piloto in pilotos
    }
    demanda_ultima_por_slot = estadisticas_ultima_carrera["demanda"]

    print("\n[Tiendas mejorando piezas antes de fijar precios...]")
    if carrera == 1:
        print("  ⏭️ Carrera 1 sin mejoras: todavía no existe historial de mercado suficiente para evaluar ROI.")
    else:
        for letra, datos in vendedores.items():
            calidad_base = calidades_mercado_base[letra]
            precios_base = precios_mercado_base[letra]
            presupuesto_mejora_disponible = round(datos.get("presupuesto_mejora", 0.0), 2)
            prev_prices = precios_anterior_carrera[letra]
            ingresos_tienda_ant_estimada = (
                estadisticas_ultima_carrera["demanda"]["chasis"][letra] * (prev_prices["chasis"] or 25.0)
                + estadisticas_ultima_carrera["demanda"]["motor"][letra] * (prev_prices["motor"] or 20.0)
                + estadisticas_ultima_carrera["demanda"]["ruedas"][letra] * (prev_prices["ruedas"] or 15.0)
            )
            total_real_ant_estimada = 0.0
            for l_aux in vendedores:
                p_aux = precios_anterior_carrera[l_aux]
                total_real_ant_estimada += (
                    estadisticas_ultima_carrera["demanda"]["chasis"][l_aux] * (p_aux["chasis"] or 25.0)
                    + estadisticas_ultima_carrera["demanda"]["motor"][l_aux] * (p_aux["motor"] or 20.0)
                    + estadisticas_ultima_carrera["demanda"]["ruedas"][l_aux] * (p_aux["ruedas"] or 15.0)
                )
            cuota_ultima_estimada = (ingresos_tienda_ant_estimada / total_real_ant_estimada * 100) if total_real_ant_estimada > 0 else 0.0
            costes_mejora_estimados = {
                slot: calcular_coste_mejora_pieza(calidad_base[slot], slot, estimar_mejora_esperada_por_calidad(calidad_base[slot]))
                for slot in ["chasis", "motor", "ruedas"]
            }

            observacion_mejora = {
                "carrera_actual": carrera,
                "total_carreras": TOTAL_CARRERAS,
                "calidad_propia": calidad_base,
                "calidad_competencia": {
                    rival: calidades_mercado_base[rival]
                    for rival in vendedores
                    if rival != letra
                },
                "precios_propios": precios_base,
                "precios_competencia": {
                    rival: precios_mercado_base[rival]
                    for rival in vendedores
                    if rival != letra
                },
                "demanda_mercado_por_slot": demanda_ultima_por_slot,
                "demanda_propia_por_slot": {
                    "chasis": demanda_ultima_por_slot["chasis"].get(letra, 0),
                    "motor": demanda_ultima_por_slot["motor"].get(letra, 0),
                    "ruedas": demanda_ultima_por_slot["ruedas"].get(letra, 0),
                },
                "presupuestos_pilotos": presupuestos_mercado_actuales,
                "presupuesto_mejora_disponible": presupuesto_mejora_disponible,
                "ingresos_recientes": ingresos_tienda_ant_estimada,
                "cuota_mercado_ultima": cuota_ultima_estimada,
                "costes_mejora_estimados": costes_mejora_estimados,
            }

            decision_mejora = objetos_tiendas[letra].decidir_mejora(observacion_mejora)
            if decision_mejora.slot is not None and decision_mejora.coste_estimado > 0.0:
                slot_mejorado = decision_mejora.slot
                coste_mejora = calcular_coste_mejora_pieza(
                    calidad_base[slot_mejorado],
                    slot_mejorado,
                    decision_mejora.mejora_esperada_pct,
                )
                if coste_mejora <= presupuesto_mejora_disponible:
                    mejora_real_abs, nueva_calidad = aplicar_mejora_pieza(calidad_base[slot_mejorado], decision_mejora.mejora_esperada_pct)
                    datos[slot_mejorado] = nueva_calidad
                    datos["presupuesto_mejora"] = round(max(0.0, presupuesto_mejora_disponible - coste_mejora), 2)
                    datos["inversion_mejoras"] = round(datos.get("inversion_mejoras", 0.0) + coste_mejora, 2)
                    datos.setdefault("mejoras_realizadas", []).append({
                        "carrera": carrera,
                        "slot": slot_mejorado,
                        "calidad_anterior": calidad_base[slot_mejorado],
                        "calidad_nueva": nueva_calidad,
                        "mejora_esperada_pct": decision_mejora.mejora_esperada_pct,
                        "mejora_real_abs": mejora_real_abs,
                        "coste": coste_mejora,
                    })
                    print(
                        f"  🔧 Vendedor {letra} mejora {slot_mejorado}: coste {coste_mejora:.2f}€ | "
                        f"esperado +{decision_mejora.mejora_esperada_pct:.2f} -> real +{mejora_real_abs:.2f} | "
                        f"calidad {calidad_base[slot_mejorado]:.2f} -> {nueva_calidad:.2f} | "
                        f"saldo mejora {datos['presupuesto_mejora']:.2f}€"
                    )
                else:
                    print(
                        f"  ⏭️ Vendedor {letra} pospone mejora en {decision_mejora.slot}: presupuesto {presupuesto_mejora_disponible:.2f}€ < coste {coste_mejora:.2f}€"
                    )
            else:
                print(f"  ⏭️ Vendedor {letra} no mejora esta carrera.")
    
    # FASE 1: Las tiendas fijan precios usando el algoritmo evolutivo Q
    print("\n[Tiendas fijando precios...]")
    resumen_metricas = "HISTORICO_ULTIMA_CARRERA:\n"
    if carrera == 1:
        resumen_metricas += "Primera carrera. No hay datos de demandas previos.\n"
    else:
        resumen_metricas += f"=== RESULTADOS ANALÍTICOS DE LA CARRERA {carrera-1} ===\n"
        for letra_m in vendedores:
            resumen_metricas += f"Vendedor {letra_m} -> Demandas reales recibidas: "
            resumen_metricas += f"Chasis: {estadisticas_ultima_carrera['demanda']['chasis'][letra_m]} unidades | "
            resumen_metricas += f"Motor: {estadisticas_ultima_carrera['demanda']['motor'][letra_m]} unidades | "
            resumen_metricas += f"Ruedas: {estadisticas_ultima_carrera['demanda']['ruedas'][letra_m]} unidades.\n"
        
        ganador_componentes = estadisticas_ultima_carrera["uso_ganador"]
        resumen_metricas += f"Componentes del coche GANADOR: Chasis de {ganador_componentes['chasis']}, Motor de {ganador_componentes['motor']}, Ruedas de {ganador_componentes['ruedas']}.\n"

    precios_prev_texto = "PRECIOS_CARRERA_ANTERIOR:\n"
    for letra_prev in vendedores:
        prev = precios_anterior_carrera[letra_prev]
        ch = f"{prev['chasis']}€" if prev['chasis'] is not None else "sin referencia"
        mo = f"{prev['motor']}€" if prev['motor'] is not None else "sin referencia"
        ru = f"{prev['ruedas']}€" if prev['ruedas'] is not None else "sin referencia"
        precios_prev_texto += f"Vendedor {letra_prev}: Chasis {ch} | Motor {mo} | Ruedas {ru}\n"

    observaciones_vendedores = {}
    for letra, datos in vendedores.items():
        if carrera == 1:
            cuota_ultima = 33.3  # Salen en igualdad de condiciones en la Carrera 1
        else:
            prev_prices = precios_anterior_carrera[letra]
            # Calculamos cuánto ingresó esta tienda en la carrera anterior
            ingresos_tienda_ant = (
                estadisticas_ultima_carrera["demanda"]["chasis"][letra] * (prev_prices["chasis"] or 25.0) +
                estadisticas_ultima_carrera["demanda"]["motor"][letra] * (prev_prices["motor"] or 20.0) +
                estadisticas_ultima_carrera["demanda"]["ruedas"][letra] * (prev_prices["ruedas"] or 15.0)
            )
            # Calculamos el total gastado por todos los pilotos en la carrera anterior
            total_real_ant = 0.0
            for l_aux in vendedores:
                p_aux = precios_anterior_carrera[l_aux]
                total_real_ant += (
                    estadisticas_ultima_carrera["demanda"]["chasis"][l_aux] * (p_aux["chasis"] or 25.0) +
                    estadisticas_ultima_carrera["demanda"]["motor"][l_aux] * (p_aux["motor"] or 20.0) +
                    estadisticas_ultima_carrera["demanda"]["ruedas"][l_aux] * (p_aux["ruedas"] or 15.0)
                )
            cuota_ultima = (ingresos_tienda_ant / total_real_ant * 100) if total_real_ant > 0 else 0.0

        # Para la primera carrera no incluimos precios de la competencia: los vendedores no tienen referencia.
        precios_competencia = {}
        if carrera > 1:
            for letra_rival in vendedores:
                if letra_rival == letra:
                    continue
                prev_rival = precios_anterior_carrera[letra_rival]
                precios_competencia[letra_rival] = {
                    "chasis": prev_rival["chasis"] if prev_rival["chasis"] is not None else 25.0,
                    "motor": prev_rival["motor"] if prev_rival["motor"] is not None else 20.0,
                    "ruedas": prev_rival["ruedas"] if prev_rival["ruedas"] is not None else 15.0,
                }

        historico_contratos_vendedor = [
            {
                "piloto": c["piloto"],
                "slot": c["slot"],
                "carreras_restantes": c["carreras_restantes"],
                "ventaja": c["ventaja"],
            }
            for c in contratos_exclusividad
            if c["vendedor"] == letra
        ]

        # Calculamos precios iniciales propios basados solo en la calidad si no hay referencia previa
        precio_inicial_chasis = obtener_precio_inicial_por_calidad(datos["chasis"], "chasis")
        precio_inicial_motor = obtener_precio_inicial_por_calidad(datos["motor"], "motor")
        precio_inicial_ruedas = obtener_precio_inicial_por_calidad(datos["ruedas"], "ruedas")
        piezas_vendidas_ultima = (
            estadisticas_ultima_carrera["demanda"]["chasis"][letra]
            + estadisticas_ultima_carrera["demanda"]["motor"][letra]
            + estadisticas_ultima_carrera["demanda"]["ruedas"][letra]
        )
        total_piezas_mercado = len(pilotos) * 3
        porcentaje_piezas_ultima = (piezas_vendidas_ultima / total_piezas_mercado * 100) if total_piezas_mercado > 0 else 0.0

        # Flujo formal: observar -> decidir (la ejecucion ocurre al aplicar precios).
        observacion_vendedor = {
            "carrera_actual": carrera,
            "total_carreras": TOTAL_CARRERAS,
            "demandas_ultimas": estadisticas_ultima_carrera["demanda"],
            "uso_ganador": estadisticas_ultima_carrera["uso_ganador"],
            "cuota_mercado_ultima": cuota_ultima,
            "ingresos_recientes": ingresos_tienda_ant if carrera > 1 else 0.0,
            "precios_propios": {
                "chasis": precios_anterior_carrera[letra]["chasis"] if precios_anterior_carrera[letra]["chasis"] is not None else precio_inicial_chasis,
                "motor": precios_anterior_carrera[letra]["motor"] if precios_anterior_carrera[letra]["motor"] is not None else precio_inicial_motor,
                "ruedas": precios_anterior_carrera[letra]["ruedas"] if precios_anterior_carrera[letra]["ruedas"] is not None else precio_inicial_ruedas,
            },
            "precios_competencia": precios_competencia,
            "historico_contratos": historico_contratos_vendedor,
            "objetivo_ingresos": PRESUPUESTO_TOTAL_CAMPEONATO * len(pilotos) / max(1, len(vendedores)),
            "piezas_vendidas_ultima": piezas_vendidas_ultima,
            "total_piezas_mercado": total_piezas_mercado,
            "porcentaje_piezas_ultima": porcentaje_piezas_ultima,
            "calidad_propia": {
                "chasis": datos["chasis"],
                "motor": datos["motor"],
                "ruedas": datos["ruedas"],
            },
            "calidad_competencia": {
                letra_rival: {
                    "chasis": vendedores[letra_rival]["chasis"],
                    "motor": vendedores[letra_rival]["motor"],
                    "ruedas": vendedores[letra_rival]["ruedas"],
                }
                for letra_rival in vendedores
                if letra_rival != letra
            },
            "presupuesto_mejora_disponible": datos.get("presupuesto_mejora", 0.0),
            "presupuestos_pilotos": presupuestos_mercado_actuales,
        }
        observaciones_vendedores[letra] = objetos_tiendas[letra].observar(observacion_vendedor)
        pregunta_vendedor = {
            "tipo": "propuesta_precio",
            "preguntas": {
                "que_precio_propones": "que precio propones?",
                "que_estrategia_quieres_usar": "que estrategia quieres usar?",
            },
            "contexto": observaciones_vendedores[letra],
        }
        decision = objetos_tiendas[letra].responder_pregunta(pregunta_vendedor)
        # =========================================================================
        
        prev = precios_anterior_carrera[letra]

        p_ch_ant = prev["chasis"] if prev["chasis"] is not None else precio_inicial_chasis
        p_mo_ant = prev["motor"] if prev["motor"] is not None else precio_inicial_motor
        p_ru_ant = prev["ruedas"] if prev["ruedas"] is not None else precio_inicial_ruedas

        precio_chasis_nuevo = p_ch_ant * (1.0 + decision.variacion_chasis)
        precio_motor_nuevo = p_mo_ant * (1.0 + decision.variacion_motor)
        precio_ruedas_nuevo = p_ru_ant * (1.0 + decision.variacion_ruedas)

        # Si hay exclusividad activa en una pieza, ese precio queda congelado durante el contrato.
        precios_actualizados = {
            "chasis": aplicar_guardrail_precio(
                precio_chasis_nuevo,
                prev["chasis"],
                estadisticas_ultima_carrera["demanda"]["chasis"][letra],
                estadisticas_ultima_carrera["uso_ganador"]["chasis"] == letra,
            ),
            "motor": aplicar_guardrail_precio(
                precio_motor_nuevo,
                prev["motor"],
                estadisticas_ultima_carrera["demanda"]["motor"][letra],
                estadisticas_ultima_carrera["uso_ganador"]["motor"] == letra,
            ),
            "ruedas": aplicar_guardrail_precio(
                precio_ruedas_nuevo,
                prev["ruedas"],
                estadisticas_ultima_carrera["demanda"]["ruedas"][letra],
                estadisticas_ultima_carrera["uso_ganador"]["ruedas"] == letra,
            ),
        }

        for slot in ["chasis", "motor", "ruedas"]:
            if hay_contrato_vendedor_slot(letra, slot, contratos_exclusividad):
                precio_referencia = prev[slot]
                if precio_referencia is None:
                    precio_referencia = {"chasis": 25.0, "motor": 20.0, "ruedas": 15.0}[slot]
                precios_actualizados[slot] = round(precio_referencia, 2)
            else:
                racha_sin_ventas = objetos_tiendas[letra].memoria["rachas_sin_ventas"].get(slot, 0)
                precio_minimo_calidad = obtener_precio_minimo_dinamico(
                    datos[slot],
                    slot,
                    demanda_ultima=estadisticas_ultima_carrera["demanda"][slot][letra],
                    racha_sin_ventas=racha_sin_ventas,
                )
                precios_actualizados[slot] = round(max(precios_actualizados[slot], precio_minimo_calidad), 2)

            # Tras finalizar un contrato, el vendedor puede subir precio por valor percibido.
            factor_subida = subida_post_contrato[letra][slot]
            if factor_subida > 0:
                precio_referencia = precios_actualizados[slot]
                precios_actualizados[slot] = round(max(1.0, precio_referencia * (1.0 + factor_subida)), 2)
                subida_post_contrato[letra][slot] = 0.0

        datos["precios"] = precios_actualizados

    print("\n[Contratos de exclusividad...]")
    solicitudes_por_vendedor_slot = {}
    if carrera == 1:
        print("  ⏳ Carrera 1 sin contratos: aún no hay historial para evaluar ventajas reales.")
    else:
        precios_actuales_por_vendedor = {
            letra: datos.get("precios", {})
            for letra, datos in vendedores.items()
        }

        for piloto in pilotos:
            contratos_piloto = obtener_contratos_piloto(piloto, contratos_exclusividad)
            contratos_texto = ", ".join(
                f"{c['slot']} con vendedor {c['vendedor']} ({c['carreras_restantes']} carrera(s) restante(s))"
                for c in contratos_piloto
            )
            if contratos_texto:
                print(f"  🔒 {piloto} mantiene exclusividad en: {contratos_texto}.")

            for slot in ["chasis", "motor", "ruedas"]:
                if cooldown_exclusividad[piloto][slot] > 0:
                    print(
                        f"  🕒 {piloto} está en enfriamiento para {slot} "
                        f"({cooldown_exclusividad[piloto][slot]} carrera(s) restante(s))."
                    )
                    cooldown_exclusividad[piloto][slot] -= 1
                    continue

                if hay_contrato_piloto_slot(piloto, slot, contratos_exclusividad):
                    continue

                propuesta = proponer_contrato_exclusividad(
                    piloto,
                    vendedores,
                    contratos_exclusividad,
                    historial_piezas_por_piloto[piloto],
                    slot_objetivo=slot,
                    precios_actuales=precios_actuales_por_vendedor,
                )
                if not propuesta:
                    continue

                vendedor_objetivo = propuesta["vendedor"]
                slot_objetivo = propuesta["slot"]
                if hay_contrato_vendedor_slot(vendedor_objetivo, slot_objetivo, contratos_exclusividad):
                    continue

                precio_actual_pieza = vendedores[vendedor_objetivo]["precios"].get(slot_objetivo)
                if precio_actual_pieza is None:
                    precio_actual_pieza = {"chasis": 25.0, "motor": 20.0, "ruedas": 15.0}[slot_objetivo]
                demanda_reciente_slot = estadisticas_ultima_carrera["demanda"][slot_objetivo].get(vendedor_objetivo, 0)
                oferta_inicial = cotizar_oferta_contrato(
                    propuesta,
                    precio_actual_pieza=precio_actual_pieza,
                    puntuaciones_pilotos=puntuaciones_pilotos,
                    historial_uso_piezas=historial_uso_piezas_por_piloto,
                    demanda_reciente_slot=demanda_reciente_slot,
                    total_pilotos=len(pilotos),
                    carrera_actual=carrera,
                )
                saldo_actual = saldo_restante_por_piloto[piloto]
                if saldo_actual < oferta_inicial["coste_adelantado"]:
                    continue

                propuesta.update(oferta_inicial)

                clave = (vendedor_objetivo, slot_objetivo)
                solicitudes_por_vendedor_slot.setdefault(clave, []).append(propuesta)

        if not solicitudes_por_vendedor_slot:
            print("  ℹ️ No se presentaron solicitudes de exclusividad esta carrera.")
        else:
            for (vendedor_objetivo, slot_objetivo), solicitudes in solicitudes_por_vendedor_slot.items():
                solicitudes_texto = ", ".join(
                    f"{s['piloto']} (+{s['ventaja']}★)" for s in solicitudes
                )
                precio_actual_pieza = vendedores[vendedor_objetivo]["precios"].get(slot_objetivo)
                if precio_actual_pieza is None:
                    precio_actual_pieza = {"chasis": 25.0, "motor": 20.0, "ruedas": 15.0}[slot_objetivo]
                demanda_reciente_slot = estadisticas_ultima_carrera["demanda"][slot_objetivo].get(vendedor_objetivo, 0)

                print(
                    f"  📨 Solicitudes para {slot_objetivo} de vendedor {vendedor_objetivo}: {solicitudes_texto}."
                )

                rechazar_mercado, motivo_mercado = vendedor_prefiere_mercado_abierto(
                    solicitudes,
                    demanda_reciente_slot=demanda_reciente_slot,
                    total_pilotos=len(pilotos),
                )
                if rechazar_mercado:
                    print(
                        f"  🛑 Vendedor {vendedor_objetivo} rechaza contratos en {slot_objetivo}: {motivo_mercado}."
                    )
                    continue

                aceptadas = []
                for solicitud in solicitudes:
                    saldo_solicitante = saldo_restante_por_piloto[solicitud["piloto"]]
                    acepta, motivo = piloto_acepta_oferta_contrato(
                        solicitud,
                        oferta=solicitud,
                        saldo_actual=saldo_solicitante,
                    )
                    print(
                        f"    💬 Oferta a {solicitud['piloto']}: {solicitud['precio_ronda_contrato']:.2f}€/carrera "
                        f"(prima {solicitud['prima']*100:.1f}%, total {solicitud['coste_adelantado']:.2f}€) -> "
                        f"{'acepta' if acepta else 'rechaza'} ({motivo})."
                    )
                    if acepta:
                        aceptadas.append(solicitud)

                if not aceptadas:
                    print(
                        f"  ℹ️ Ningún piloto aceptó la oferta de exclusividad para {slot_objetivo} de {vendedor_objetivo}."
                    )
                    continue

                elegido, criterio_eleccion = elegir_ganador_entre_aceptadas(
                    aceptadas,
                    puntuaciones_pilotos=puntuaciones_pilotos,
                )
                puntos_elegido = puntuaciones_pilotos.get(elegido["piloto"], 0)
                coste_adelantado = elegido["coste_adelantado"]
                saldo_actual = saldo_restante_por_piloto[elegido["piloto"]]
                print(
                    f"  ✅ Vendedor {vendedor_objetivo} elige a {elegido['piloto']} por {criterio_eleccion} "
                    f"(clasificación actual: {puntos_elegido} puntos, fidelidad: {elegido.get('fidelidad_uso', 0)} uso(s))."
                )

                if coste_adelantado > saldo_actual:
                    print(
                        f"  ⛔ Contrato rechazado para {elegido['piloto']}: adelanto {coste_adelantado:.2f}€ "
                        f"supera su saldo disponible ({saldo_actual:.2f}€)."
                    )
                    continue

                saldo_restante_por_piloto[elegido["piloto"]] = round(saldo_actual - coste_adelantado, 2)
                total_gastado_por_piloto[elegido["piloto"]] += coste_adelantado
                vendedores[vendedor_objetivo]["ingresos_totales"] += coste_adelantado
                ingresos_adelantados_por_vendedor[vendedor_objetivo] += coste_adelantado
                contratos_exclusividad.append(
                    {
                        "piloto": elegido["piloto"],
                        "vendedor": vendedor_objetivo,
                        "slot": slot_objetivo,
                        "ventaja": elegido["ventaja"],
                        "solicitudes_iniciales": len(solicitudes),
                        "coste_adelantado": coste_adelantado,
                        "precio_ronda_contrato": elegido["precio_ronda_contrato"],
                        "prima_contrato": elegido["prima"],
                        "criterio_eleccion": criterio_eleccion,
                        "carreras_restantes": DURACION_CONTRATO_EXCLUSIVIDAD,
                        **inicializar_estadisticas_contrato(carrera, len(solicitudes)),
                    }
                )
                print(
                    f"  💳 {elegido['piloto']} firma contrato y paga {coste_adelantado:.2f}€ "
                    f"({DURACION_CONTRATO_EXCLUSIVIDAD} carreras de {slot_objetivo} en {vendedor_objetivo}, "
                    f"prima {elegido['prima']*100:.1f}%)."
                )
                print(
                    f"  💰 Saldo restante de {elegido['piloto']}: {saldo_restante_por_piloto[elegido['piloto']]:.2f}€."
                )

    texto_catalogo_usuario = "CATÁLOGO DISPONIBLE:\n"
    texto_catalogo_piloto = "CATÁLOGO DISPONIBLE:\n"
    for letra, datos in vendedores.items():
        precios_previos = precios_anterior_carrera[letra]
        tag_ch = " 🔒" if hay_contrato_vendedor_slot(letra, "chasis", contratos_exclusividad) else ""
        tag_mo = " 🔒" if hay_contrato_vendedor_slot(letra, "motor", contratos_exclusividad) else ""
        tag_ru = " 🔒" if hay_contrato_vendedor_slot(letra, "ruedas", contratos_exclusividad) else ""
        texto_catalogo_usuario += (
            f"Vendedor {letra}: "
            f"Chasis {datos['chasis']}★ ({datos['precios']['chasis']}€ {formatear_variacion_precio(datos['precios']['chasis'], precios_previos['chasis'])}){tag_ch} | "
            f"Motor {datos['motor']}★ ({datos['precios']['motor']}€ {formatear_variacion_precio(datos['precios']['motor'], precios_previos['motor'])}){tag_mo} | "
            f"Ruedas {datos['ruedas']}★ ({datos['precios']['ruedas']}€ {formatear_variacion_precio(datos['precios']['ruedas'], precios_previos['ruedas'])}){tag_ru}\n"
        )
        texto_catalogo_piloto += (
            f"Vendedor {letra}: "
            f"Chasis {datos['chasis']}★ ({datos['precios']['chasis']}€){tag_ch} | "
            f"Motor {datos['motor']}★ ({datos['precios']['motor']}€){tag_mo} | "
            f"Ruedas {datos['ruedas']}★ ({datos['precios']['ruedas']}€){tag_ru}\n"
        )
    print(texto_catalogo_usuario)

    # FASE 2: Todos los compradores eligen sus piezas
    print("[Pilotos comprando componentes...]")
    compras_carrera = {}
    presupuesto_por_piloto = {}
    contratos_por_piloto = {}
    observaciones_pilotos = {}
    for piloto in pilotos:
        contratos_piloto = obtener_contratos_piloto(piloto, contratos_exclusividad)
        contratos_por_piloto[piloto] = contratos_piloto
        saldo_restante = saldo_restante_por_piloto[piloto]
        presupuesto_maximo = round(max(0.0, saldo_restante), 2)
        presupuesto_por_piloto[piloto] = presupuesto_maximo

        bloqueos_piloto = bloqueos_exclusividad_para_piloto(piloto, contratos_exclusividad)
        for slot in ["chasis", "motor", "ruedas"]:
            for vendedor_bloqueado in sorted(bloqueos_piloto[slot]):
                piloto_beneficiario = propietario_exclusividad(slot, vendedor_bloqueado, contratos_exclusividad)

        # Flujo formal: observar -> decidir (la ejecucion ocurre al procesar compras).
        observacion_piloto = {
            "carrera_actual": carrera,
            "total_carreras": TOTAL_CARRERAS,
            "catalogo_vendedores": vendedores,
            "presupuesto_max": presupuesto_maximo,
            "presupuesto_total_restante": saldo_restante,
            "bloqueos_exclusividad": bloqueos_piloto,
            "contratos_activos": contratos_piloto,
            "historial_resultados_anteriores": [historico_mercado],
        }
        observaciones_pilotos[piloto] = objetos_pilotos[piloto].observar(observacion_piloto)
        pregunta_piloto = {
            "tipo": "compra_componentes",
            "preguntas": {
                "que_compras_quieres_hacer": "que compras quieres hacer?",
                "que_estrategia_quieres_usar": "que estrategia quieres usar?",
            },
            "contexto": observaciones_pilotos[piloto],
        }
        eleccion = objetos_pilotos[piloto].responder_pregunta(pregunta_piloto)
        compras_carrera[piloto] = eleccion
        
        v_ch_letra = normalizar_vendedor(eleccion.vendedor_chasis)
        v_mo_letra = normalizar_vendedor(eleccion.vendedor_motor)
        v_ru_letra = normalizar_vendedor(eleccion.vendedor_ruedas)
        
        try:
            p_ch = vendedores[v_ch_letra]["precios"]["chasis"] if v_ch_letra in vendedores else None
            p_mo = vendedores[v_mo_letra]["precios"]["motor"] if v_mo_letra in vendedores else None
            p_ru = vendedores[v_ru_letra]["precios"]["ruedas"] if v_ru_letra in vendedores else None

            if p_ch is None or p_mo is None or p_ru is None:
                raise ValueError("Alguna pieza no tiene vendedor válido")

            coste_desglose = f"{p_ch}€ (Chasis {v_ch_letra}) + {p_mo}€ (Motor {v_mo_letra}) + {p_ru}€ (Ruedas {v_ru_letra}) = {round(p_ch+p_mo+p_ru, 2)}€"
        except Exception:
            coste_desglose = "Error al calcular desglose (formato de tienda inválido)"

        print(f"\n🏎️  Piloto: {piloto}")
        if contratos_piloto:
            contrato_texto = ", ".join(
                f"{c['slot']} con vendedor {c['vendedor']} (coste adelantado: {c['coste_adelantado']:.2f}€)"
                for c in contratos_piloto
            )
            print(
                f"  🔒 Contratos activos: {contrato_texto} | presupuesto de compra esta carrera: {presupuesto_maximo:.2f}€"
            )
        print(
            f"  💼 Saldo campeonato: {saldo_restante:.2f}€ | presupuesto de compra esta carrera: {presupuesto_maximo:.2f}€"
        )
        print(f"  💰 Presupuesto invertido: {coste_desglose}")
        print(f"  🧠 Razonamiento completo: \"{eleccion.razonamiento}\"")
    print("\n" + "="*50)

    # FASE 3: El Motor resuelve costes, descalificaciones, bonus y carrera
    print("\n[🚦 ¡SÉMÁFORO EN VERDE! Procesando normativa y rendimiento...]")
    
    pilotos_validos = []
    resumen_ventas_texto = ""
    ingresos_por_vendedor_carrera = {letra: 0.0 for letra in vendedores}
    # Sumamos los ingresos cobrados por adelantado al registro de la carrera
    for _letra in ingresos_adelantados_por_vendedor:
        ingresos_por_vendedor_carrera[_letra] += ingresos_adelantados_por_vendedor.get(_letra, 0.0)
    demanda_carrera = {
        "chasis": {letra: 0 for letra in vendedores},
        "motor": {letra: 0 for letra in vendedores},
        "ruedas": {letra: 0 for letra in vendedores},
    }

    for piloto, eleccion in compras_carrera.items():
        try:
            v_chasis = normalizar_vendedor(eleccion.vendedor_chasis)
            v_motor = normalizar_vendedor(eleccion.vendedor_motor)
            v_ruedas = normalizar_vendedor(eleccion.vendedor_ruedas)
            
            componentes = []
            if v_chasis in vendedores:
                if pieza_bloqueada_para_piloto(piloto, "chasis", v_chasis, contratos_exclusividad):
                    print(f"  🚫 {piloto} no puede comprar chasis de {v_chasis}: exclusividad activa para otro piloto.")
                else:
                    componentes.append({"slot": "chasis", "vendedor": v_chasis, "precio": vendedores[v_chasis]["precios"]["chasis"], "calidad": vendedores[v_chasis]["chasis"]})
            if v_motor in vendedores:
                if pieza_bloqueada_para_piloto(piloto, "motor", v_motor, contratos_exclusividad):
                    print(f"  🚫 {piloto} no puede comprar motor de {v_motor}: exclusividad activa para otro piloto.")
                else:
                    componentes.append({"slot": "motor", "vendedor": v_motor, "precio": vendedores[v_motor]["precios"]["motor"], "calidad": vendedores[v_motor]["motor"]})
            if v_ruedas in vendedores:
                if pieza_bloqueada_para_piloto(piloto, "ruedas", v_ruedas, contratos_exclusividad):
                    print(f"  🚫 {piloto} no puede comprar ruedas de {v_ruedas}: exclusividad activa para otro piloto.")
                else:
                    componentes.append({"slot": "ruedas", "vendedor": v_ruedas, "precio": vendedores[v_ruedas]["precios"]["ruedas"], "calidad": vendedores[v_ruedas]["ruedas"]})

            if not componentes:
                print(f"  ❌ {piloto} NO PUEDE CORRER: No se pudo interpretar ninguna pieza válida.")
                continue

            mejor_opcion = calcular_mejor_configuracion(
                componentes,
                presupuesto_max=presupuesto_por_piloto[piloto],
                contratos_activos=contratos_por_piloto[piloto],
            )
            if mejor_opcion is None:
                print(f"  ❌ {piloto} PENALIZADO: No existe una configuración válida por presupuesto.")
                continue

            configuracion = mejor_opcion["configuracion"]
            vel_base = mejor_opcion["vel_base"]
            piezas_faltantes = mejor_opcion["piezas_faltantes"]
            base_sin_penalizacion = mejor_opcion["base_sin_penalizacion"]
            componentes_usados = mejor_opcion["componentes_usados"]

            if piezas_faltantes > 0:
                piezas_sacrificadas = 3 - len(configuracion.split(","))
                print(f"  ⚠️ {piloto} supera el presupuesto o sacrifica piezas: {piezas_sacrificadas} pieza(s) fuera. Penalización aplicada: {base_sin_penalizacion:.2f} -> {vel_base:.2f}")

            # Amortización de contratos: parte del coste ya se pagó por adelantado y debe imputarse a la ronda
            contratos_activos_piloto = contratos_por_piloto.get(piloto, [])
            amortizacion_total_ronda = round(
                sum(c.get("coste_adelantado", 0.0) / DURACION_CONTRATO_EXCLUSIVIDAD for c in contratos_activos_piloto if c.get("carreras_restantes", 0) > 0),
                2,
            )

            for componente in componentes_usados:
                # Si la pieza está cubierta por un contrato activo del piloto, ya fue pagada por adelantado
                esta_contratada = any(
                    c["slot"] == componente["slot"] and c["vendedor"] == componente["vendedor"] for c in contratos_activos_piloto
                )
                if not esta_contratada:
                    vendedores[componente["vendedor"]]["ingresos_totales"] += componente["precio"]
                    ingresos_por_vendedor_carrera[componente["vendedor"]] += componente["precio"]
                # La demanda y el historial siempre se registran
                demanda_carrera[componente["slot"]][componente["vendedor"]] += 1
                historial_piezas_por_piloto[piloto].add((componente["slot"], componente["vendedor"]))
                historial_uso_piezas_por_piloto[piloto][componente["slot"]][componente["vendedor"]] += 1

            gasto_economico_ronda = round(mejor_opcion["coste_economico"] + amortizacion_total_ronda, 2)

            pilotos_validos.append({
                "piloto": piloto,
                "vel_base": vel_base,
                "gasto_bruto": mejor_opcion["gasto_bruto"],
                "gasto_economico": gasto_economico_ronda,
                "penalizacion": 0.0,
                "configuracion": configuracion,
                "componentes_usados": componentes_usados,
            })
            # Se descuenta del saldo únicamente el coste imputable de esta compra (las amortizaciones ya se pagaron al firmar)
            saldo_restante_por_piloto[piloto] = round(
                max(0.0, saldo_restante_por_piloto[piloto] - mejor_opcion["coste_economico"]),
                2,
            )
            total_gastado_por_piloto[piloto] += mejor_opcion["coste_economico"]
            resumen_ventas_texto += (
                f"- Piloto {piloto} compró {configuracion} por {mejor_opcion['gasto_bruto']:.2f}€ "
                f"(coste economico: {mejor_opcion['coste_economico']:.2f}€, original: {v_chasis},{v_motor},{v_ruedas}).\n"
            )
            
        except Exception as e:
            print(f"  ❌ {piloto} cometió un error crítico al procesar la respuesta.")

    bonus_por_piloto = {piloto: 0 for piloto in pilotos}
    pilotos_eligibles_ahorro = [p for p in pilotos_validos if len(p.get("componentes_usados", [])) == 3]

    if pilotos_eligibles_ahorro:
        pilotos_ordenados_gasto = sorted(pilotos_eligibles_ahorro, key=lambda x: x["gasto_bruto"])
        bonus_por_piloto.update(
            repartir_puntos_por_empates(
                pilotos_ordenados_gasto,
                clave_igualdad=lambda item: item["gasto_bruto"],
                puntos_por_puesto=PUNTOS_AHORRO,
                max_beneficiarios=10,
            )
        )

        if pilotos_ordenados_gasto:
            print("  ⚖️ Puntos de ahorro repartidos solo entre los 10 coches más baratos, con empate de corte sin puntos.")
    else:
        print("  ⚖️ No hay karts completos (3 piezas) para repartir puntos de ahorro.")

    resultados_carrera = []
    for p in pilotos_validos:
        ruido = random.uniform(-1.5, 1.5)
        puntuacion_final = p["vel_base"] + p["penalizacion"] + ruido
        resultados_carrera.append({
            "piloto": p["piloto"],
            "puntos_carrera": puntuacion_final,
            "coste_economico": p["gasto_economico"],
            "gasto_bruto": p["gasto_bruto"],
            "configuracion": p.get("configuracion", "INVÁLIDA"),
            "componentes_usados": p.get("componentes_usados", []),
        })

    resultados_carrera.sort(key=lambda x: (-x["puntos_carrera"], x["coste_economico"], x["gasto_bruto"], x["piloto"]))
    
    puntos_por_posicion = repartir_puntos_por_empates(
        resultados_carrera,
        clave_igualdad=lambda item: item["puntos_carrera"],
        puntos_por_puesto=PUNTOS_POSICION,
    )
    print("\n🏆 RESULTADOS DE LA CARRERA (Puntos Posición + Puntos Ahorro):")
    for i, res in enumerate(resultados_carrera):
        puntos_pos = puntos_por_posicion.get(res["piloto"], 0)
        puntos_ahorro = bonus_por_piloto[res["piloto"]]
        bono_clasificacion = BONO_CLASIFICACION_POR_POSICION[i] if i < len(BONO_CLASIFICACION_POR_POSICION) else 0
        
        total_puntos_ronda = puntos_pos + puntos_ahorro
        puntuaciones_pilotos[res["piloto"]] += total_puntos_ronda
        bono_clasificacion_por_piloto[res["piloto"]] += bono_clasificacion
        saldo_restante_por_piloto[res["piloto"]] = round(saldo_restante_por_piloto[res["piloto"]] + bono_clasificacion, 2)
        
        print(f"  {i+1}º Lugar: {res['piloto']} | Rendimiento Pista: {res['puntos_carrera']:.2f} | Coste económico: {res['coste_economico']:.2f}€ ({res['configuracion']}) | (+{puntos_pos} pos, +{puntos_ahorro} ahorro, +{bono_clasificacion}€ carrera) -> Total: +{total_puntos_ronda} Puntos")

    # Para reportar cuota de mercado por carrera contamos todos los ingresos efectivos recibidos
    # en la ronda, incluyendo pagos por contratos (adelantados) y ventas al momento.
    total_ingresos_ronda = sum(ingresos_por_vendedor_carrera.values())
    total_piezas_mercado = len(pilotos) * 3
    print("\n💼 RESUMEN DE NEGOCIO POR VENDEDOR:")
    if total_ingresos_ronda > 0:
        for letra in vendedores:
            ingresos = ingresos_por_vendedor_carrera[letra]
            porcentaje = (ingresos / total_ingresos_ronda) * 100
            piezas_vendidas = (
                demanda_carrera["chasis"][letra]
                + demanda_carrera["motor"][letra]
                + demanda_carrera["ruedas"][letra]
            )
            porcentaje_piezas = (piezas_vendidas / total_piezas_mercado * 100) if total_piezas_mercado > 0 else 0.0
            print(
                f"  🏪 Tienda {letra}: Ingresos {ingresos:.2f}€ | {porcentaje:.1f}% del dinero gastado por todos los pilotos | "
                f"Piezas {piezas_vendidas}/{total_piezas_mercado} ({porcentaje_piezas:.1f}%)"
            )
    else:
        print("  No hubo gasto válido en esta carrera.")

    # Flujo formal vendedores: resultado -> aprender.
    for letra in vendedores:
        ingresos_vendedor = ingresos_por_vendedor_carrera[letra]
        cuota_vendedor = (ingresos_vendedor / total_ingresos_ronda * 100) if total_ingresos_ronda > 0 else 0.0
        historial_mejoras_vendedor = vendedores[letra].get("mejoras_realizadas", [])
        mejora_ultima = historial_mejoras_vendedor[-1] if historial_mejoras_vendedor else None
        resultado_vendedor = {
            "ingresos_carrera": ingresos_vendedor,
            "cuota_mercado": cuota_vendedor,
            "piezas_vendidas": (
                demanda_carrera["chasis"][letra]
                + demanda_carrera["motor"][letra]
                + demanda_carrera["ruedas"][letra]
            ),
            "total_piezas_mercado": len(pilotos) * 3,
            "porcentaje_piezas": (
                (
                    demanda_carrera["chasis"][letra]
                    + demanda_carrera["motor"][letra]
                    + demanda_carrera["ruedas"][letra]
                ) / max(1, len(pilotos) * 3) * 100
            ),
            "demanda_actual_por_pieza": {
                "chasis": demanda_carrera["chasis"][letra],
                "motor": demanda_carrera["motor"][letra],
                "ruedas": demanda_carrera["ruedas"][letra],
            },
            "recompensa": round((ingresos_vendedor / 10.0) + (cuota_vendedor / 10.0), 4),
            "mejora_realizada": mejora_ultima is not None,
            "slot_mejorado": mejora_ultima.get("slot") if mejora_ultima else None,
            "coste_mejora": mejora_ultima.get("coste", 0.0) if mejora_ultima else 0.0,
            "mejora_esperada_pct": mejora_ultima.get("mejora_esperada_pct", 0.0) if mejora_ultima else 0.0,
            "mejora_real_abs": mejora_ultima.get("mejora_real_abs", 0.0) if mejora_ultima else 0.0,
            "roi_mejora": (
                (
                    max(0.0, (mejora_ultima.get("calidad_nueva", 0.0) if mejora_ultima else 0.0) - (mejora_ultima.get("calidad_anterior", 0.0) if mejora_ultima else 0.0))
                    * 10.0
                ) / max(1.0, mejora_ultima.get("coste", 1.0) if mejora_ultima else 1.0)
            ) if mejora_ultima else 0.0,
            "demanda_slot_mejorado": (
                demanda_carrera[mejora_ultima["slot"]][letra] if mejora_ultima and mejora_ultima.get("slot") in demanda_carrera else 0
            ),
        }
        objetos_tiendas[letra].aprender(resultado_vendedor)
        vendedores[letra]["presupuesto_mejora"] = round(vendedores[letra].get("presupuesto_mejora", 0.0) + ingresos_vendedor, 2)

    for letra, datos in vendedores.items():
        precios_anterior_carrera[letra] = datos["precios"].copy()

    estadisticas_ultima_carrera["demanda"] = demanda_carrera
    if resultados_carrera:
        componentes_ganador = resultados_carrera[0].get("componentes_usados", [])
        uso_ganador = {"chasis": None, "motor": None, "ruedas": None}
        for componente in componentes_ganador:
            uso_ganador[componente["slot"]] = componente["vendedor"]
        estadisticas_ultima_carrera["uso_ganador"] = uso_ganador

    resultados_por_piloto = {res["piloto"]: res for res in resultados_carrera}
    for contrato in contratos_exclusividad:
        resultado_piloto = resultados_por_piloto.get(contrato["piloto"])
        if not resultado_piloto:
            continue

        piezas_piloto = resultado_piloto.get("componentes_usados", [])
        pieza_contrato_usada = any(
            componente["slot"] == contrato["slot"] and componente["vendedor"] == contrato["vendedor"]
            for componente in piezas_piloto
        )
        if not pieza_contrato_usada:
            continue

        posicion_podio_contrato = resultados_carrera.index(resultado_piloto) + 1
        registrar_uso_contrato(
            contrato,
            posicion_podio=posicion_podio_contrato,
            fue_ganador=(posicion_podio_contrato == 1),
        )

    historico_mercado = f"En la carrera {carrera} ocurrió lo siguiente:\n"
    historico_mercado += resumen_ventas_texto
    if resultados_carrera:
        historico_mercado += f"El ganador en pista fue {resultados_carrera[0]['piloto']}.\n"
    
    media_velocidad_carrera = (sum(res["puntos_carrera"] for res in resultados_carrera) / len(resultados_carrera)) if resultados_carrera else 0.0

    for res in resultados_carrera:
        p_nombre = res["piloto"]
        originales = compras_carrera[p_nombre]
        elecciones_hechas = {
            "chasis": normalizar_vendedor(originales.vendedor_chasis),
            "motor": normalizar_vendedor(originales.vendedor_motor),
            "ruedas": normalizar_vendedor(originales.vendedor_ruedas)
        }
        
        vel_piloto = res["puntos_carrera"]
        # Sacamos la posición exacta en el podio (1 para el primero, 2 para el segundo, etc.)
        posicion_podio = resultados_carrera.index(res) + 1
        
        # Flujo formal compradores: resultado -> aprender.
        resultado_piloto = {
            "elecciones_hechas": elecciones_hechas,
            "rendimiento_pista": vel_piloto,
            "media_parrilla": media_velocidad_carrera,
            "posicion_podio": posicion_podio,
            "gasto_economico": res.get("coste_economico", 0.0),
            "presupuesto_disponible": presupuesto_por_piloto.get(p_nombre, PRESUPUESTO_TOTAL_CAMPEONATO),
        }
        objetos_pilotos[p_nombre].aprender(resultado_piloto)

    contratos_expirados = []
    for contrato in contratos_exclusividad:
        contrato["carreras_restantes"] -= 1
        if contrato["carreras_restantes"] <= 0:
            contratos_expirados.append(contrato)

    if contratos_expirados:
        for contrato in contratos_expirados:
            cooldown_exclusividad[contrato["piloto"]][contrato["slot"]] = 1
            factor_subida = calcular_factor_subida_post_contrato(contrato, carrera, TOTAL_CARRERAS)
            subida_post_contrato[contrato["vendedor"]][contrato["slot"]] = max(
                subida_post_contrato[contrato["vendedor"]][contrato["slot"]],
                factor_subida,
            )
            print(
                f"  🔓 Finaliza exclusividad: {contrato['piloto']} con vendedor {contrato['vendedor']} "
                f"en {contrato['slot']}. Entra en enfriamiento 1 carrera para esa pieza."
            )
            print(
                f"  📈 Vendedor {contrato['vendedor']} prepara subida post-contrato en {contrato['slot']} "
                f"de +{factor_subida*100:.1f}% para la próxima carrera."
            )

    contratos_exclusividad = [c for c in contratos_exclusividad if c["carreras_restantes"] > 0]

    print("\n--------------------------------------------------\n")

# ==================================================
# CLASIFICACIONES TOTALES DEL CAMPEONATO
# ==================================================
pilotos_con_gasto = {piloto: gasto for piloto, gasto in total_gastado_por_piloto.items() if gasto > 0}
bonus_final_gasto = {piloto: 0 for piloto in pilotos}

print("\n💡 BONUS FINAL DE EFICIENCIA ECONÓMICA:")
if pilotos_con_gasto:
    gasto_minimo = min(pilotos_con_gasto.values())
    pilotos_menor_gasto = [piloto for piloto, gasto in pilotos_con_gasto.items() if gasto == gasto_minimo]
    for piloto in pilotos_menor_gasto:
        bonus_final_gasto[piloto] = BONUS_MENOR_GASTO_FINAL
        puntuaciones_pilotos[piloto] += BONUS_MENOR_GASTO_FINAL

    if len(pilotos_menor_gasto) == 1:
        print(
            f"  🏁 {pilotos_menor_gasto[0]} ha sido el piloto que menos ha gastado en total ({gasto_minimo:.2f}€) y recibe +{BONUS_MENOR_GASTO_FINAL} puntos."
        )
    else:
        nombres_empate = ", ".join(pilotos_menor_gasto)
        print(
            f"  ⚖️ Empate en el menor gasto total ({gasto_minimo:.2f}€) entre {nombres_empate}. Cada uno recibe +{BONUS_MENOR_GASTO_FINAL} puntos."
        )
else:
    print("  No hubo gasto válido acumulado en el campeonato, así que no se reparte el bonus final.")

print("==================================================")
print("🏁 FIN DEL CAMPEONATO - PODIO FINAL 🏁")
print("==================================================")
clasificacion_final = sorted(
    puntuaciones_pilotos.items(),
    key=lambda x: (-x[1], total_gastado_por_piloto.get(x[0], 0.0), x[0]),
)

for piloto, puntos in clasificacion_final:
    gasto_total = total_gastado_por_piloto.get(piloto, 0.0)
    saldo_restante = saldo_restante_por_piloto.get(piloto, 0.0)
    bonus_gasto = bonus_final_gasto.get(piloto, 0)
    puntos_base = puntos - bonus_gasto
    extra_bonus = f" | Bonus ahorro final: +{bonus_gasto}" if bonus_gasto else ""
    print(
        f"🏎️  {piloto}: {puntos_base} Puntos base{extra_bonus} | Total: {puntos} Puntos "
        f"| Gasto total: {gasto_total:.2f}€ | Saldo final: {saldo_restante:.2f}€"
    )

print("\n💰 INGRESOS TOTALES DE LAS TIENDAS:")
for letra, datos in vendedores.items():
    print(f"  🏪 Tienda {letra}: {datos['ingresos_totales']:.2f}€ recaudados | {datos.get('inversion_mejoras', 0.0):.2f}€ invertidos en mejoras")
print("==================================================")
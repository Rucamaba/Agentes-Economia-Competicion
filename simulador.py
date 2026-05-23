import random
import re
from itertools import combinations
from comprador import AgenteComprador
from vendedor import AgenteVendedor
from economia_costes import (
    calcular_coste_bruto,
    calcular_coste_imputable,
    calcular_presupuesto_disponible,
)

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
    match = re.search(r"\b([ABC])\b", texto)
    if match:
        return match.group(1)

    for caracter in texto:
        if caracter in "ABC":
            return caracter

    return None


def aplicar_guardrail_precio(precio_nuevo, precio_anterior, demanda_ultima, fue_ganador):
    ajustado = float(precio_nuevo)

    if precio_anterior is None:
        return round(max(5.0, min(80.0, ajustado)), 2)

    # Si una pieza se vendio mucho o fue parte del coche ganador, evitamos rebajas agresivas.
    if (demanda_ultima >= 2 or fue_ganador) and ajustado < (precio_anterior * 0.95):
        ajustado = precio_anterior * 0.95

    # Si una pieza no se vendio nada, evitamos subidas demasiado optimistas.
    if demanda_ultima == 0 and ajustado > (precio_anterior * 1.10):
        ajustado = precio_anterior * 1.10

    return round(max(5.0, min(80.0, ajustado)), 2)


TOTAL_CARRERAS = 10
DURACION_CONTRATO_EXCLUSIVIDAD = 2
VENTAJA_NOTABLE_ABSOLUTA = 2.0
BONUS_MENOR_GASTO_FINAL = 5


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


def proponer_contrato_exclusividad(piloto, vendedores, contratos_activos, historial_piezas_piloto, slot_objetivo=None):
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


def calcular_presupuesto_piloto(contratos_piloto):
    return calcular_presupuesto_disponible(contratos_piloto)


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

# ==================================================
# CONFIGURACIÓN INICIAL DEL MERCADO Y VARIABLES
# ==================================================
vendedores = {
    "A": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0},
    "B": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0},
    "C": {"chasis": round(random.uniform(0.0, 10.0), 2), "motor": round(random.uniform(0.0, 10.0), 2), "ruedas": round(random.uniform(0.0, 10.0), 2), "precios": {}, "ingresos_totales": 0.0}
}

pilotos = ["Fernando Alonso", "Carlos Sainz", "Max Verstappen"]
puntuaciones_pilotos = {piloto: 0 for piloto in pilotos}
total_gastado_por_piloto = {piloto: 0.0 for piloto in pilotos}

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
print("📌 Regla estratégica: al final del campeonato, el piloto con menor gasto bruto total recibirá +5 puntos. Bajar costes puede ser una jugada ganadora.")
print("==================================================\n")

# Bucle del campeonato: 10 carreras
for carrera in range(1, TOTAL_CARRERAS + 1):
    print(f"--- 🏁 CARRERA {carrera} DE {TOTAL_CARRERAS} ---")

    print("\n[Contratos de exclusividad...]")
    solicitudes_por_vendedor_slot = {}
    if carrera == 1:
        print("  ⏳ Carrera 1 sin contratos: aún no hay historial para evaluar ventajas reales.")
    else:
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
                )
                if not propuesta:
                    continue

                vendedor_objetivo = propuesta["vendedor"]
                slot_objetivo = propuesta["slot"]
                if hay_contrato_vendedor_slot(vendedor_objetivo, slot_objetivo, contratos_exclusividad):
                    continue

                clave = (vendedor_objetivo, slot_objetivo)
                solicitudes_por_vendedor_slot.setdefault(clave, []).append(propuesta)

        if not solicitudes_por_vendedor_slot:
            print("  ℹ️ No se presentaron solicitudes de exclusividad esta carrera.")
        else:
            for (vendedor_objetivo, slot_objetivo), solicitudes in solicitudes_por_vendedor_slot.items():
                solicitudes_texto = ", ".join(
                    f"{s['piloto']} (+{s['ventaja']}★)" for s in solicitudes
                )
                elegido = elegir_ganador_solicitud_por_marketing(solicitudes, puntuaciones_pilotos)
                precio_actual_pieza = vendedores[vendedor_objetivo]["precios"].get(slot_objetivo)
                if precio_actual_pieza is None:
                    precio_actual_pieza = {"chasis": 25.0, "motor": 20.0, "ruedas": 15.0}[slot_objetivo]
                coste_adelantado = round(precio_actual_pieza * DURACION_CONTRATO_EXCLUSIVIDAD, 2)
                contratos_exclusividad.append(
                    {
                        "piloto": elegido["piloto"],
                        "vendedor": vendedor_objetivo,
                        "slot": slot_objetivo,
                        "ventaja": elegido["ventaja"],
                        "solicitudes_iniciales": len(solicitudes),
                        "coste_adelantado": coste_adelantado,
                        "carreras_restantes": DURACION_CONTRATO_EXCLUSIVIDAD,
                        **inicializar_estadisticas_contrato(carrera, len(solicitudes)),
                    }
                )
                puntos_elegido = puntuaciones_pilotos.get(elegido["piloto"], 0)
                print(
                    f"  📨 Solicitudes para {slot_objetivo} de vendedor {vendedor_objetivo}: {solicitudes_texto}."
                )
                print(
                    f"  ✅ Vendedor {vendedor_objetivo} elige a {elegido['piloto']} por marketing "
                    f"(mejor posición/clasificación actual: {puntos_elegido} puntos)."
                )
                print(
                    f"  💳 {elegido['piloto']} paga por adelantado {coste_adelantado:.2f}€ "
                    f"({DURACION_CONTRATO_EXCLUSIVIDAD} carreras de {slot_objetivo} en {vendedor_objetivo})."
                )
    
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

        precios_competencia = {}
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

        # Flujo formal: observar -> decidir (la ejecucion ocurre al aplicar precios).
        observacion_vendedor = {
            "carrera_actual": carrera,
            "total_carreras": TOTAL_CARRERAS,
            "demandas_ultimas": estadisticas_ultima_carrera["demanda"],
            "uso_ganador": estadisticas_ultima_carrera["uso_ganador"],
            "cuota_mercado_ultima": cuota_ultima,
            "ingresos_recientes": ingresos_tienda_ant if carrera > 1 else 0.0,
            "precios_propios": {
                "chasis": precios_anterior_carrera[letra]["chasis"] if precios_anterior_carrera[letra]["chasis"] is not None else 25.0,
                "motor": precios_anterior_carrera[letra]["motor"] if precios_anterior_carrera[letra]["motor"] is not None else 20.0,
                "ruedas": precios_anterior_carrera[letra]["ruedas"] if precios_anterior_carrera[letra]["ruedas"] is not None else 15.0,
            },
            "precios_competencia": precios_competencia,
            "historico_contratos": historico_contratos_vendedor,
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
        print(f"  ❓ Vendedor {letra}: que precio propones? / que estrategia quieres usar?")
        decision = objetos_tiendas[letra].responder_pregunta(pregunta_vendedor)
        # =========================================================================
        
        prev = precios_anterior_carrera[letra]
        
        p_ch_ant = prev["chasis"] if prev["chasis"] is not None else 25.0
        p_mo_ant = prev["motor"] if prev["motor"] is not None else 20.0
        p_ru_ant = prev["ruedas"] if prev["ruedas"] is not None else 15.0

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

            # Tras finalizar un contrato, el vendedor puede subir precio por valor percibido.
            factor_subida = subida_post_contrato[letra][slot]
            if factor_subida > 0:
                precio_referencia = precios_actualizados[slot]
                precios_actualizados[slot] = round(max(5.0, min(80.0, precio_referencia * (1.0 + factor_subida))), 2)
                subida_post_contrato[letra][slot] = 0.0

        datos["precios"] = precios_actualizados

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
        presupuesto_maximo = calcular_presupuesto_piloto(contratos_piloto)
        presupuesto_por_piloto[piloto] = presupuesto_maximo

        bloqueos_piloto = bloqueos_exclusividad_para_piloto(piloto, contratos_exclusividad)
        for slot in ["chasis", "motor", "ruedas"]:
            for vendedor_bloqueado in sorted(bloqueos_piloto[slot]):
                piloto_beneficiario = propietario_exclusividad(slot, vendedor_bloqueado, contratos_exclusividad)
                print(
                    f"\n"
                    f"  📞 {piloto} consulta {slot} a vendedor {vendedor_bloqueado}: venta denegada "
                    f"(exclusividad activa con {piloto_beneficiario})."
                )

        # Flujo formal: observar -> decidir (la ejecucion ocurre al procesar compras).
        observacion_piloto = {
            "carrera_actual": carrera,
            "total_carreras": TOTAL_CARRERAS,
            "catalogo_vendedores": vendedores,
            "presupuesto_max": presupuesto_maximo,
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
        print(f"  ❓ Piloto {piloto}: que compras quieres hacer? / que estrategia quieres usar?")
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
                f"  🔒 Contratos activos: {contrato_texto} | presupuesto temporal: {presupuesto_maximo:.2f}€"
            )
        print(f"  💰 Presupuesto invertido: {coste_desglose}")
        print(f"  🧠 Razonamiento completo:\n     \"{eleccion.razonamiento}\"")
    print("\n" + "="*50)

    # FASE 3: El Motor resuelve costes, descalificaciones, bonus y carrera
    print("\n[🚦 ¡SÉMÁFORO EN VERDE! Procesando normativa y rendimiento...]")
    
    pilotos_validos = []
    resumen_ventas_texto = ""
    ingresos_por_vendedor_carrera = {letra: 0.0 for letra in vendedores}
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

            for componente in componentes_usados:
                vendedores[componente["vendedor"]]["ingresos_totales"] += componente["precio"]
                ingresos_por_vendedor_carrera[componente["vendedor"]] += componente["precio"]
                demanda_carrera[componente["slot"]][componente["vendedor"]] += 1
                historial_piezas_por_piloto[piloto].add((componente["slot"], componente["vendedor"]))

            pilotos_validos.append({
                "piloto": piloto,
                "vel_base": vel_base,
                "gasto_bruto": mejor_opcion["gasto_bruto"],
                "gasto_economico": mejor_opcion["coste_economico"],
                "penalizacion": 0.0,
                "configuracion": configuracion,
                "componentes_usados": componentes_usados,
            })
            total_gastado_por_piloto[piloto] += mejor_opcion["gasto_bruto"]
            resumen_ventas_texto += (
                f"- Piloto {piloto} compró {configuracion} por {mejor_opcion['gasto_bruto']:.2f}€ "
                f"(coste economico: {mejor_opcion['coste_economico']:.2f}€, original: {v_chasis},{v_motor},{v_ruedas}).\n"
            )
            
        except Exception as e:
            print(f"  ❌ {piloto} cometió un error crítico al procesar la respuesta.")

    bonus_por_piloto = {piloto: 0 for piloto in pilotos}
    pilotos_eligibles_ahorro = [p for p in pilotos_validos if len(p.get("componentes_usados", [])) == 3]

    if len(pilotos_eligibles_ahorro) >= 2:
        # Los puntos de ahorro se calculan en base al gasto bruto (gasto_bruto),
        # no al coste imputable/económico. Evita que contratos adelantados aseguren puntos.
        pilotos_ordenados_gasto = sorted(pilotos_eligibles_ahorro, key=lambda x: x["gasto_bruto"])
        gastos = [p["gasto_bruto"] for p in pilotos_ordenados_gasto]

        if len(gastos) == 3 and gastos[0] == gastos[1] == gastos[2]:
            print("  ⚖️ Empate total del gasto bruto: Los 3 karts gastaron lo mismo. No se reparten puntos de ahorro.")
        else:
            if gastos[0] == gastos[1]:
                print(f"  ⚖️  Empate en primer puesto de ahorro (gasto bruto {gastos[0]}€): ¡+2 puntos para ambos!")
                bonus_por_piloto[pilotos_ordenados_gasto[0]["piloto"]] = 2
                bonus_por_piloto[pilotos_ordenados_gasto[1]["piloto"]] = 2
            else:
                bonus_por_piloto[pilotos_ordenados_gasto[0]["piloto"]] = 2
                if len(gastos) == 3 and gastos[1] == gastos[2]:
                    print(f"  ⚖️  Empate en segundo puesto de ahorro (gasto bruto {gastos[1]}€): solo se reparte el primer puesto.")
                else:
                    bonus_por_piloto[pilotos_ordenados_gasto[1]["piloto"]] = 1
    else:
        print("  ⚖️ No hay suficientes karts completos (3 piezas) para repartir puntos de ahorro.")

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

    resultados_carrera.sort(key=lambda x: x["puntos_carrera"], reverse=True)
    
    reparto_puntos_posicion = [10, 6, 4]
    print("\n🏆 RESULTADOS DE LA CARRERA (Puntos Posición + Puntos Ahorro):")
    for i, res in enumerate(resultados_carrera):
        puntos_pos = reparto_puntos_posicion[i] if i < len(reparto_puntos_posicion) else 0
        puntos_ahorro = bonus_por_piloto[res["piloto"]]
        
        total_puntos_ronda = puntos_pos + puntos_ahorro
        puntuaciones_pilotos[res["piloto"]] += total_puntos_ronda
        
        print(f"  {i+1}º Lugar: {res['piloto']} | Rendimiento Pista: {res['puntos_carrera']:.2f} | Coste económico: {res['coste_economico']:.2f}€ ({res['configuracion']}) | (+{puntos_pos} pos, +{puntos_ahorro} ahorro) -> Total: +{total_puntos_ronda} Puntos")

    total_gastado_por_pilotos = sum(p["gasto_economico"] for p in pilotos_validos)
    print("\n💼 RESUMEN DE NEGOCIO POR VENDEDOR:")
    if total_gastado_por_pilotos > 0:
        for letra in vendedores:
            ingresos = ingresos_por_vendedor_carrera[letra]
            porcentaje = (ingresos / total_gastado_por_pilotos) * 100
            print(f"  🏪 Tienda {letra}: Ingresos {ingresos:.2f}€ | {porcentaje:.1f}% del dinero gastado por todos los pilotos")
    else:
        print("  No hubo gasto válido en esta carrera.")

    print("\n📦 RESUMEN DE COMPRAS:")
    print(resumen_ventas_texto.rstrip() if resumen_ventas_texto else "  No hubo compras válidas.")

    # Flujo formal vendedores: resultado -> aprender.
    for letra in vendedores:
        ingresos_vendedor = ingresos_por_vendedor_carrera[letra]
        cuota_vendedor = (ingresos_vendedor / total_gastado_por_pilotos * 100) if total_gastado_por_pilotos > 0 else 0.0
        resultado_vendedor = {
            "ingresos_carrera": ingresos_vendedor,
            "cuota_mercado": cuota_vendedor,
            "demanda_actual_por_pieza": {
                "chasis": demanda_carrera["chasis"][letra],
                "motor": demanda_carrera["motor"][letra],
                "ruedas": demanda_carrera["ruedas"][letra],
            },
            "recompensa": round((ingresos_vendedor / 10.0) + (cuota_vendedor / 10.0), 4),
        }
        objetos_tiendas[letra].aprender(resultado_vendedor)

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
    
    media_velocidad_carrera = sum(res["puntos_carrera"] for res in resultados_carrera) / len(resultados_carrera)

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
            "presupuesto_disponible": presupuesto_por_piloto.get(p_nombre, 100.0),
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
for piloto, puntos in sorted(puntuaciones_pilotos.items(), key=lambda x: x[1], reverse=True):
    gasto_total = total_gastado_por_piloto.get(piloto, 0.0)
    bonus_gasto = bonus_final_gasto.get(piloto, 0)
    puntos_base = puntos - bonus_gasto
    extra_bonus = f" | Bonus ahorro final: +{bonus_gasto}" if bonus_gasto else ""
    print(f"🏎️  {piloto}: {puntos_base} Puntos base{extra_bonus} | Total: {puntos} Puntos | Gasto total: {gasto_total:.2f}€")

print("\n💰 INGRESOS TOTALES DE LAS TIENDAS:")
for letra, datos in vendedores.items():
    print(f"  🏪 Tienda {letra}: {datos['ingresos_totales']:.2f}€ recaudados")
print("==================================================")
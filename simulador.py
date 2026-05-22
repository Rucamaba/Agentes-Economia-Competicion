import random
import re
from itertools import combinations
from comprador import AgenteComprador
from vendedor import AgenteVendedor

def formatear_variacion_precio(precio_actual, precio_anterior):
    if precio_anterior is None:
        return "(sin referencia)"

    variacion = round(precio_actual - precio_anterior, 2)
    signo = "+" if variacion >= 0 else ""
    return f"({signo}{variacion:.2f}€)"


def calcular_mejor_configuracion(componentes):
    mejor_opcion = None

    for cantidad in range(1, len(componentes) + 1):
        for subset in combinations(componentes, cantidad):
            gasto = round(sum(componente["precio"] for componente in subset), 2)
            if gasto > 100:
                continue

            piezas_faltantes = len(componentes) - len(subset)
            base_sin_penalizacion = sum(componente["calidad"] for componente in subset)
            rendimiento = round(base_sin_penalizacion * (0.8 ** piezas_faltantes), 4)

            candidato = {
                "configuracion": ",".join(componente["vendedor"] for componente in subset),
                "gasto": gasto,
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

                if gasto < mejor_opcion["gasto"]:
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

# --- CORRECCIÓN CRUCIAL: Inicializamos los objetos aquí, ahora que ya existen las variables anteriores ---
objetos_tiendas = {letra: AgenteVendedor(letra) for letra in vendedores}
objetos_pilotos = {piloto: AgenteComprador(piloto) for piloto in pilotos}

precios_anterior_carrera = {
    letra: {"chasis": None, "motor": None, "ruedas": None}
    for letra in vendedores
}

historico_mercado = "Inicio del campeonato. Ninguna carrera disputada aún."

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
print("==================================================\n")

# Bucle del campeonato: 6 carreras
for carrera in range(1, 7):
    print(f"--- 🏁 CARRERA {carrera} DE 6 ---")
    
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

        # Llamamos al vendedor pasándole su cuota de mercado real
        decision = objetos_tiendas[letra].decidir_variacion_q(
            demandas_ultimas=estadisticas_ultima_carrera["demanda"], 
            uso_ganador=estadisticas_ultima_carrera["uso_ganador"],
            cuota_mercado_ultima=cuota_ultima
        )
        # =========================================================================
        
        prev = precios_anterior_carrera[letra]
        
        p_ch_ant = prev["chasis"] if prev["chasis"] is not None else 25.0
        p_mo_ant = prev["motor"] if prev["motor"] is not None else 20.0
        p_ru_ant = prev["ruedas"] if prev["ruedas"] is not None else 15.0

        precio_chasis_nuevo = p_ch_ant * (1.0 + decision.variacion_chasis)
        precio_motor_nuevo = p_mo_ant * (1.0 + decision.variacion_motor)
        precio_ruedas_nuevo = p_ru_ant * (1.0 + decision.variacion_ruedas)

        # Tus guardrails matemáticos tradicionales se quedan exactamente abajo:
        datos["precios"] = {
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

    texto_catalogo_usuario = "CATÁLOGO DISPONIBLE:\n"
    texto_catalogo_piloto = "CATÁLOGO DISPONIBLE:\n"
    for letra, datos in vendedores.items():
        precios_previos = precios_anterior_carrera[letra]
        texto_catalogo_usuario += (
            f"Vendedor {letra}: "
            f"Chasis {datos['chasis']}★ ({datos['precios']['chasis']}€ {formatear_variacion_precio(datos['precios']['chasis'], precios_previos['chasis'])}) | "
            f"Motor {datos['motor']}★ ({datos['precios']['motor']}€ {formatear_variacion_precio(datos['precios']['motor'], precios_previos['motor'])}) | "
            f"Ruedas {datos['ruedas']}★ ({datos['precios']['ruedas']}€ {formatear_variacion_precio(datos['precios']['ruedas'], precios_previos['ruedas'])})\n"
        )
        texto_catalogo_piloto += (
            f"Vendedor {letra}: "
            f"Chasis {datos['chasis']}★ ({datos['precios']['chasis']}€) | "
            f"Motor {datos['motor']}★ ({datos['precios']['motor']}€) | "
            f"Ruedas {datos['ruedas']}★ ({datos['precios']['ruedas']}€)\n"
        )
    print(texto_catalogo_usuario)

    # FASE 2: Todos los compradores eligen sus piezas
    print("[Pilotos comprando componentes...]")
    compras_carrera = {}
    for piloto in pilotos:
        eleccion = objetos_pilotos[piloto].elegir_componentes_q(vendedores)
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
                componentes.append({"slot": "chasis", "vendedor": v_chasis, "precio": vendedores[v_chasis]["precios"]["chasis"], "calidad": vendedores[v_chasis]["chasis"]})
            if v_motor in vendedores:
                componentes.append({"slot": "motor", "vendedor": v_motor, "precio": vendedores[v_motor]["precios"]["motor"], "calidad": vendedores[v_motor]["motor"]})
            if v_ruedas in vendedores:
                componentes.append({"slot": "ruedas", "vendedor": v_ruedas, "precio": vendedores[v_ruedas]["precios"]["ruedas"], "calidad": vendedores[v_ruedas]["ruedas"]})

            if not componentes:
                print(f"  ❌ {piloto} NO PUEDE CORRER: No se pudo interpretar ninguna pieza válida.")
                continue

            mejor_opcion = calcular_mejor_configuracion(componentes)
            if mejor_opcion is None:
                print(f"  ❌ {piloto} PENALIZADO: No existe una configuración válida por presupuesto.")
                continue

            configuracion = mejor_opcion["configuracion"]
            coste = mejor_opcion["gasto"]
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

            pilotos_validos.append({"piloto": piloto, "vel_base": vel_base, "gasto": coste, "penalizacion": 0.0, "configuracion": configuracion, "componentes_usados": componentes_usados})
            resumen_ventas_texto += f"- Piloto {piloto} compró {configuracion} por {coste:.2f}€ (original: {v_chasis},{v_motor},{v_ruedas}).\n"
            
        except Exception as e:
            print(f"  ❌ {piloto} cometió un error crítico al procesar la respuesta.")

    bonus_por_piloto = {piloto: 0 for piloto in pilotos}
    pilotos_eligibles_ahorro = [p for p in pilotos_validos if len(p.get("componentes_usados", [])) == 3]

    if len(pilotos_eligibles_ahorro) >= 2:
        pilotos_ordenados_gasto = sorted(pilotos_eligibles_ahorro, key=lambda x: x["gasto"])
        gastos = [p["gasto"] for p in pilotos_ordenados_gasto]
        
        if len(gastos) == 3 and gastos[0] == gastos[1] == gastos[2]:
            print("  ⚖️ Empate total de costes: Los 3 karts gastaron lo mismo. No se reparten puntos de ahorro.")
        else:
            if gastos[0] == gastos[1]:
                print(f"  ⚖️  Empate en primer puesto de ahorro ({gastos[0]}€): ¡+2 puntos para ambos!")
                bonus_por_piloto[pilotos_ordenados_gasto[0]["piloto"]] = 2
                bonus_por_piloto[pilotos_ordenados_gasto[1]["piloto"]] = 2
            else:
                bonus_por_piloto[pilotos_ordenados_gasto[0]["piloto"]] = 2
                if len(gastos) == 3 and gastos[1] == gastos[2]:
                    print(f"  ⚖️  Empate en segundo puesto de ahorro ({gastos[1]}€): solo se reparte el primer puesto.")
                else:
                    bonus_por_piloto[pilotos_ordenados_gasto[1]["piloto"]] = 1
    else:
        print("  ⚖️ No hay suficientes karts completos (3 piezas) para repartir puntos de ahorro.")

    resultados_carrera = []
    for p in pilotos_validos:
        ruido = random.uniform(-1.5, 1.5)
        puntuacion_final = p["vel_base"] + p["penalizacion"] + ruido
        resultados_carrera.append({"piloto": p["piloto"], "puntos_carrera": puntuacion_final, "gasto": p["gasto"], "configuracion": p.get("configuracion", "INVÁLIDA"), "componentes_usados": p.get("componentes_usados", [])})

    resultados_carrera.sort(key=lambda x: x["puntos_carrera"], reverse=True)
    
    reparto_puntos_posicion = [10, 6, 4]
    print("\n🏆 RESULTADOS DE LA CARRERA (Puntos Posición + Puntos Ahorro):")
    for i, res in enumerate(resultados_carrera):
        puntos_pos = reparto_puntos_posicion[i] if i < len(reparto_puntos_posicion) else 0
        puntos_ahorro = bonus_por_piloto[res["piloto"]]
        
        total_puntos_ronda = puntos_pos + puntos_ahorro
        puntuaciones_pilotos[res["piloto"]] += total_puntos_ronda
        
        print(f"  {i+1}º Lugar: {res['piloto']} | Rendimiento Pista: {res['puntos_carrera']:.2f} | Gasto: {res['gasto']:.2f}€ ({res['configuracion']}) | (+{puntos_pos} pos, +{puntos_ahorro} ahorro) -> Total: +{total_puntos_ronda} Puntos")

    total_gastado_por_pilotos = sum(p["gasto"] for p in pilotos_validos)
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

    for letra, datos in vendedores.items():
        precios_anterior_carrera[letra] = datos["precios"].copy()

    estadisticas_ultima_carrera["demanda"] = demanda_carrera
    if resultados_carrera:
        componentes_ganador = resultados_carrera[0].get("componentes_usados", [])
        uso_ganador = {"chasis": None, "motor": None, "ruedas": None}
        for componente in componentes_ganador:
            uso_ganador[componente["slot"]] = componente["vendedor"]
        estadisticas_ultima_carrera["uso_ganador"] = uso_ganador

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
        
        # Llamamos al nuevo método de rendimiento y podio
        objetos_pilotos[p_nombre].aprender_de_resultado_rendimiento(
            elecciones_hechas=elecciones_hechas, 
            rendimiento_pista=vel_piloto, 
            media_parrilla=media_velocidad_carrera,
            posicion_podio=posicion_podio  # <--- NUEVO PARÁMETRO MANDATORIO
        )

    print("\n--------------------------------------------------\n")

# ==================================================
# CLASIFICACIONES TOTALES DEL CAMPEONATO
# ==================================================
print("==================================================")
print("🏁 FIN DEL CAMPEONATO - PODIO FINAL 🏁")
print("==================================================")
for piloto, puntos in sorted(puntuaciones_pilotos.items(), key=lambda x: x[1], reverse=True):
    print(f"🏎️  {piloto}: {puntos} Puntos Totales")

print("\n💰 INGRESOS TOTALES DE LAS TIENDAS:")
for letra, datos in vendedores.items():
    print(f"  🏪 Tienda {letra}: {datos['ingresos_totales']:.2f}€ recaudados")
print("==================================================")
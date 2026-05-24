import random
from agente_base import AgenteBase

class DecisionVendedor:
    def __init__(self, variacion_chasis, variacion_motor, variacion_ruedas, razonamiento):
        self.variacion_chasis = variacion_chasis
        self.variacion_motor = variacion_motor
        self.variacion_ruedas = variacion_ruedas
        self.razonamiento = razonamiento


class DecisionMejoraVendedor:
    def __init__(self, slot, mejora_esperada_pct, coste_estimado, prioridad, razonamiento):
        self.slot = slot
        self.mejora_esperada_pct = mejora_esperada_pct
        self.coste_estimado = coste_estimado
        self.prioridad = prioridad
        self.razonamiento = razonamiento

class AgenteVendedor(AgenteBase):
    def __init__(self, letra):
        super().__init__(
            nombre=letra,
            parametros_aprendizaje={"sensibilidad_precio_min": 0.06, "sensibilidad_precio_max": 0.12},
        )
        self.letra = letra
        self.sensibilidad_precio = random.uniform(0.06, 0.12)
        self.memoria_ajustes = {"chasis": 0.0, "motor": 0.0, "ruedas": 0.0}
        self.historial_contratos = []
        self.memoria["impacto_subidas"] = {"chasis": 0.0, "motor": 0.0, "ruedas": 0.0}
        self.memoria["impacto_rebajas_cuota"] = {"media": 0.0, "n": 0}
        self.memoria["impacto_cuota_piezas"] = {"media": 0.0, "n": 0}
        self.memoria["sensibilidad_segmentos"] = {}
        self.memoria["rentabilidad_exclusividad"] = {"media": 0.0, "n": 0}
        self.memoria["estrategias_mejora"] = {
            "chasis": {"media": 0.0, "n": 0},
            "motor": {"media": 0.0, "n": 0},
            "ruedas": {"media": 0.0, "n": 0},
        }
        self.memoria["rachas_sin_ventas"] = {
            "chasis": 0,
            "motor": 0,
            "ruedas": 0,
        }
        self.memoria["estrategias_venta"] = {
            "crecer_cuota": {"media": 0.0, "n": 0},
            "exprimir_margen": {"media": 0.0, "n": 0},
            "defender_posicion": {"media": 0.0, "n": 0},
            "captar_contratos_exclusivos": {"media": 0.0, "n": 0},
        }
        self.memoria["evaluaciones_post_ronda"] = []
        self.memoria["pautas_recordadas"] = {}
        self.memoria["historial_mejoras"] = []
        self.memoria["ultima_mejora"] = {}

        # Intentamos cargar memoria persistida (si existe)
        try:
            self.load_memory()
        except Exception:
            pass

    def _perfil_estrategia_venta(self, estrategia):
        perfiles = {
            "crecer_cuota": {
                "peso_precio": 0.38,
                "peso_probabilidad": 0.32,
                "peso_q": 0.20,
                "peso_estabilidad": 0.10,
                "sesgo_variacion": -0.03,
            },
            "exprimir_margen": {
                "peso_precio": 0.52,
                "peso_probabilidad": 0.20,
                "peso_q": 0.18,
                "peso_estabilidad": 0.10,
                "sesgo_variacion": 0.03,
            },
            "defender_posicion": {
                "peso_precio": 0.34,
                "peso_probabilidad": 0.30,
                "peso_q": 0.24,
                "peso_estabilidad": 0.12,
                "sesgo_variacion": 0.0,
            },
            "captar_contratos_exclusivos": {
                "peso_precio": 0.36,
                "peso_probabilidad": 0.22,
                "peso_q": 0.24,
                "peso_estabilidad": 0.18,
                "sesgo_variacion": 0.015,
            },
        }
        return perfiles.get(estrategia, perfiles["defender_posicion"])

    def _seleccionar_estrategia_venta(self, estado):
        cuota = estado.get("cuota_mercado", 0.0)
        demanda_media = sum(estado.get("demanda_reciente_por_pieza", {}).values()) / 3.0
        contratos = len(estado.get("historico_contratos_exclusividades", []))
        porcentaje_piezas = estado.get("porcentaje_piezas_ultima", 0.0)
        ingresos_recientes = estado.get("ingresos_recientes", 0.0)
        precios_rivales = []
        for datos in estado.get("precios_competencia", {}).values():
            precios_rivales.extend(datos.values())

        presion_competitiva = 0.0
        if precios_rivales:
            media_rival = sum(precios_rivales) / len(precios_rivales)
            precio_propios = []
            for datos in estado.get("precios_competencia", {}).values():
                precio_propios.extend(datos.values())
            precio_propio_estimado = sum(precio_propios) / len(precio_propios) if precio_propios else media_rival
            if media_rival > 0:
                presion_competitiva = max(-1.0, min(1.0, (precio_propio_estimado - media_rival) / media_rival))

        media_estrategias = {
            nombre: datos["media"]
            for nombre, datos in self.memoria["estrategias_venta"].items()
        }

        puntuaciones = {
            "crecer_cuota": 0.0,
            "exprimir_margen": 0.0,
            "defender_posicion": 0.0,
            "captar_contratos_exclusivos": 0.0,
        }

        if cuota < 18.0:
            puntuaciones["crecer_cuota"] += 1.2
        elif cuota < 32.0:
            puntuaciones["defender_posicion"] += 0.8
        else:
            puntuaciones["exprimir_margen"] += 0.7

        if ingresos_recientes <= 0.0:
            puntuaciones["crecer_cuota"] += 1.5
            puntuaciones["defender_posicion"] += 0.3
            puntuaciones["exprimir_margen"] -= 0.8

        if porcentaje_piezas >= 25.0:
            puntuaciones["exprimir_margen"] += 0.9
        elif porcentaje_piezas <= 15.0:
            if contratos > 0:
                puntuaciones["defender_posicion"] += 0.4
            else:
                puntuaciones["crecer_cuota"] += 0.8

        if demanda_media >= 2.0:
            puntuaciones["exprimir_margen"] += 0.6
        elif demanda_media <= 0.8:
            puntuaciones["crecer_cuota"] += 0.5

        if abs(presion_competitiva) <= 0.12:
            puntuaciones["defender_posicion"] += 0.5
        elif presion_competitiva < 0:
            puntuaciones["crecer_cuota"] += 0.4
        else:
            puntuaciones["exprimir_margen"] += 0.4

        if contratos >= 1 or self.memoria["rentabilidad_exclusividad"]["media"] > 0.5:
            puntuaciones["captar_contratos_exclusivos"] += 1.0

        for nombre, media in media_estrategias.items():
            if self.memoria["estrategias_venta"][nombre]["n"] >= 2:
                puntuaciones[nombre] += media * 0.15

        historial_evaluacion = self.memoria.get("evaluaciones_post_ronda", [])
        if historial_evaluacion:
            ultima_eval = historial_evaluacion[-1]
            if ultima_eval.get("precio") == "gano":
                puntuaciones["exprimir_margen"] += 0.35
            elif ultima_eval.get("precio") == "perdio":
                puntuaciones["crecer_cuota"] += 0.45

            if ultima_eval.get("funciono"):
                puntuaciones["defender_posicion"] += 0.2
            if ultima_eval.get("contrato_perjudicial"):
                puntuaciones["captar_contratos_exclusivos"] += 0.2

        return max(puntuaciones, key=lambda nombre: (puntuaciones[nombre], media_estrategias[nombre]))

    def _evaluar_post_ronda_venta(self, resultado, estrategia_venta):
        observacion = self.memoria.get("ultima_observacion") or {}
        contratos_activos = observacion.get("historico_contratos", [])
        ingresos_anterior = observacion.get("ingresos_recientes", 0.0)
        ingresos_actual = resultado.get("ingresos_carrera", 0.0)
        cuota_anterior = observacion.get("cuota_mercado_ultima", 0.0)
        cuota_actual = resultado.get("cuota_mercado", cuota_anterior)
        porcentaje_piezas_anterior = observacion.get("porcentaje_piezas_ultima", 0.0)
        porcentaje_piezas_actual = resultado.get("porcentaje_piezas", porcentaje_piezas_anterior)
        demanda_actual = resultado.get("demanda_actual_por_pieza", {})
        demanda_prevista = observacion.get("demandas_ultimas", {})

        delta_ingresos = ingresos_actual - ingresos_anterior
        delta_cuota = cuota_actual - cuota_anterior
        funciono = delta_ingresos >= 0 or delta_cuota >= 0

        mejora_demanda = sum(demanda_actual.values()) - sum(
            demanda_prevista.get(slot, {}).get(self.letra, 0) for slot in ["chasis", "motor", "ruedas"]
        )

        if delta_ingresos > 0 and mejora_demanda >= 0:
            juicio_precio = "gano"
        elif delta_ingresos < 0 and mejora_demanda < 0:
            juicio_precio = "perdio"
        elif delta_cuota > 0 and estrategia_venta in {"crecer_cuota", "defender_posicion"}:
            juicio_precio = "gano"
        else:
            juicio_precio = "neutral"

        contrato_perjudicial = bool(contratos_activos) and delta_ingresos < 0 and estrategia_venta != "captar_contratos_exclusivos"
        bajo_peso_piezas_sin_contrato = porcentaje_piezas_actual <= 15.0 and not contratos_activos

        if contrato_perjudicial:
            pauta = "proteger rentabilidad contractual"
        elif bajo_peso_piezas_sin_contrato:
            pauta = "recuperar cuota de piezas bajando precio"
        elif porcentaje_piezas_actual >= 25.0:
            pauta = "aprovechar cuota de piezas para subir margen"
        elif juicio_precio == "gano" and estrategia_venta == "exprimir_margen":
            pauta = "mantener bandas de precio altas en demanda fuerte"
        elif juicio_precio == "perdio":
            pauta = "reducir agresividad de precio"
        else:
            pauta = "observar respuesta de demanda por slot"

        evaluacion = {
            "funciono": funciono,
            "precio": juicio_precio,
            "contrato_perjudicial": contrato_perjudicial,
            "pauta": pauta,
            "delta_ingresos": round(delta_ingresos, 4),
            "delta_cuota": round(delta_cuota, 4),
            "porcentaje_piezas_anterior": round(porcentaje_piezas_anterior, 4),
            "porcentaje_piezas_actual": round(porcentaje_piezas_actual, 4),
        }

        self.memoria["evaluaciones_post_ronda"].append(evaluacion)
        self.memoria["evaluaciones_post_ronda"] = self.memoria["evaluaciones_post_ronda"][-20:]
        stats_pauta = self.memoria["pautas_recordadas"].get(pauta, {"n": 0})
        stats_pauta["n"] = stats_pauta.get("n", 0) + 1
        self.memoria["pautas_recordadas"][pauta] = stats_pauta
        return evaluacion

    def observar(self, entorno):
        self.memoria["observacion_anterior"] = self.memoria.get("ultima_observacion")
        self.memoria["ultima_observacion"] = entorno
        return entorno

    def responder_pregunta(self, pregunta):
        contexto = pregunta.get("contexto", {})
        return self.decidir(contexto)

    def _segmento_mercado(self, cuota):
        if cuota < 20:
            return "cuota_baja"
        if cuota < 40:
            return "cuota_media"
        return "cuota_alta"

    def _estado_q_venta(self, observacion):
        return self.construir_estado_venta(
            demandas_ultimas=observacion.get("demandas_ultimas", {}),
            uso_ganador=observacion.get("uso_ganador", {}),
            cuota_mercado_ultima=observacion.get("cuota_mercado_ultima", 0.0),
            ingresos_recientes=observacion.get("ingresos_recientes", 0.0),
            precios_competencia=observacion.get("precios_competencia", {}),
            precios_propios=observacion.get("precios_propios", {}),
            historico_contratos=observacion.get("historico_contratos", []),
            piezas_vendidas_ultima=observacion.get("piezas_vendidas_ultima", 0),
            total_piezas_mercado=observacion.get("total_piezas_mercado", 0),
            porcentaje_piezas_ultima=observacion.get("porcentaje_piezas_ultima", 0.0),
        )

    def _aplicar_memoria_variacion(self, slot, variacion_base, estado):
        variacion = variacion_base

        dano_subidas = self.memoria["impacto_subidas"].get(slot, 0.0)
        if variacion > 0 and dano_subidas > 0:
            variacion *= max(0.6, 1.0 - min(0.4, dano_subidas * 0.15))

        segmento = self._segmento_mercado(estado["cuota_mercado"])
        key_segmento = f"{slot}:{segmento}"
        sensibilidad = self.memoria["sensibilidad_segmentos"].get(key_segmento, {"media": 0.0}).get("media", 0.0)
        if variacion > 0 and sensibilidad > 0.6:
            variacion *= 0.8
        elif variacion < 0 and sensibilidad > 0.6:
            variacion *= 1.15

        precios_rivales = [datos[slot] for _, datos in estado["precios_competencia"].items() if slot in datos]
        if precios_rivales:
            media_rivales = sum(precios_rivales) / len(precios_rivales)
            if media_rivales > 0 and estado["ingresos_recientes"] > 0:
                prima_competitiva = (estado["ingresos_recientes"] / 100.0)
                if variacion > 0:
                    variacion *= max(0.75, 1.0 - min(0.25, prima_competitiva * 0.1))

        return round(variacion, 4)

    def decidir(self, observacion):
        estado_q = self._estado_q_venta(observacion)
        carrera_actual = observacion.get("carrera_actual", 1)
        total_carreras = max(1, observacion.get("total_carreras", 10))
        progreso = 0.0 if total_carreras <= 1 else (carrera_actual - 1) / (total_carreras - 1)
        nivel_exploracion = max(0.04, 0.50 * (1.0 - progreso))
        estado = self.construir_estado_venta(
            demandas_ultimas=observacion.get("demandas_ultimas", {}),
            uso_ganador=observacion.get("uso_ganador", {}),
            cuota_mercado_ultima=observacion.get("cuota_mercado_ultima", 0.0),
            ingresos_recientes=observacion.get("ingresos_recientes", 0.0),
            precios_competencia=observacion.get("precios_competencia", {}),
            precios_propios=observacion.get("precios_propios", {}),
            historico_contratos=observacion.get("historico_contratos", []),
            piezas_vendidas_ultima=observacion.get("piezas_vendidas_ultima", 0),
            total_piezas_mercado=observacion.get("total_piezas_mercado", 0),
            porcentaje_piezas_ultima=observacion.get("porcentaje_piezas_ultima", 0.0),
        )
        estrategia_venta = self._seleccionar_estrategia_venta(estado)
        decision = self.decidir_variacion_q(
            demandas_ultimas=observacion.get("demandas_ultimas", {}),
            uso_ganador=observacion.get("uso_ganador", {}),
            cuota_mercado_ultima=observacion.get("cuota_mercado_ultima", 0.0),
            ingresos_recientes=observacion.get("ingresos_recientes", 0.0),
            precios_competencia=observacion.get("precios_competencia", {}),
            precios_propios=observacion.get("precios_propios", {}),
            historico_contratos=observacion.get("historico_contratos", []),
            estado_q=estado_q,
            estrategia_venta=estrategia_venta,
            nivel_exploracion=nivel_exploracion,
        )
        self.registrar_accion(
            {
                "tipo": "ajuste_precios",
                "variacion_chasis": decision.variacion_chasis,
                "variacion_motor": decision.variacion_motor,
                "variacion_ruedas": decision.variacion_ruedas,
                "estado_q": estado_q,
                "estrategia_venta": estrategia_venta,
                "acciones_q": {
                    "chasis": {"slot": "chasis", "variacion": round(decision.variacion_chasis, 4)},
                    "motor": {"slot": "motor", "variacion": round(decision.variacion_motor, 4)},
                    "ruedas": {"slot": "ruedas", "variacion": round(decision.variacion_ruedas, 4)},
                },
            }
        )
        return decision

    def aprender(self, resultado):
        recompensa = resultado.get("recompensa", 0.0)
        self.registrar_recompensa(recompensa)

        observacion = self.memoria.get("ultima_observacion") or {}
        accion = self.historial_acciones[-1] if self.historial_acciones else {}
        estrategia_actual = accion.get("estrategia_venta", "defender_posicion")
        estado_q = accion.get("estado_q") or self._estado_q_venta(observacion)
        acciones_q = accion.get("acciones_q") or {}
        demanda_actual = resultado.get("demanda_actual_por_pieza", {})

        for slot in ["chasis", "motor", "ruedas"]:
            variacion = accion.get(f"variacion_{slot}", 0.0)
            accion_q = acciones_q.get(slot, {"slot": slot, "variacion": round(variacion, 4)})
            demanda_prev_slot = observacion.get("demandas_ultimas", {}).get(slot, {}).get(self.letra, 0)
            demanda_actual_slot = demanda_actual.get(slot, 0)
            racha_sin_ventas = self.memoria["rachas_sin_ventas"].get(slot, 0)
            if demanda_actual_slot <= 0:
                self.memoria["rachas_sin_ventas"][slot] = racha_sin_ventas + 1
            else:
                self.memoria["rachas_sin_ventas"][slot] = 0

            if variacion > 0 and demanda_actual_slot < demanda_prev_slot:
                self.memoria["impacto_subidas"][slot] = round(self.memoria["impacto_subidas"][slot] * 0.85 + 0.15, 4)
            else:
                self.memoria["impacto_subidas"][slot] = round(self.memoria["impacto_subidas"][slot] * 0.9, 4)

            segmento = self._segmento_mercado(observacion.get("cuota_mercado_ultima", 0.0))
            key_segmento = f"{slot}:{segmento}"
            stats_seg = self.memoria["sensibilidad_segmentos"].get(key_segmento, {"media": 0.0, "n": 0})
            nuevo_n_seg = stats_seg["n"] + 1
            sensibilidad = abs((demanda_actual_slot - demanda_prev_slot) / (variacion if abs(variacion) > 0.01 else 0.01))
            nueva_media_seg = stats_seg["media"] + ((sensibilidad - stats_seg["media"]) / nuevo_n_seg)
            self.memoria["sensibilidad_segmentos"][key_segmento] = {"media": round(nueva_media_seg, 4), "n": nuevo_n_seg}

            recompensa_slot = recompensa + (0.35 * (demanda_actual_slot - demanda_prev_slot))
            if variacion > 0:
                recompensa_slot -= 0.10 * variacion
            elif variacion < 0 and demanda_actual_slot == 0:
                recompensa_slot += 0.15
            self.actualizar_q(estado_q, accion_q, round(recompensa_slot, 4), contexto="venta")

        cuota_anterior = observacion.get("cuota_mercado_ultima", 0.0)
        cuota_actual = resultado.get("cuota_mercado", cuota_anterior)
        hubo_rebaja = any((accion.get(f"variacion_{slot}", 0.0) < 0) for slot in ["chasis", "motor", "ruedas"])
        if hubo_rebaja:
            stats_rebaja = self.memoria["impacto_rebajas_cuota"]
            nuevo_n = stats_rebaja["n"] + 1
            mejora_cuota = cuota_actual - cuota_anterior
            stats_rebaja["media"] = round(stats_rebaja["media"] + ((mejora_cuota - stats_rebaja["media"]) / nuevo_n), 4)
            stats_rebaja["n"] = nuevo_n

        contratos_activos = observacion.get("historico_contratos", [])
        if contratos_activos:
            stats_exc = self.memoria["rentabilidad_exclusividad"]
            nuevo_n_exc = stats_exc["n"] + 1
            delta_ingresos = resultado.get("ingresos_carrera", 0.0) - observacion.get("ingresos_recientes", 0.0)
            stats_exc["media"] = round(stats_exc["media"] + ((delta_ingresos - stats_exc["media"]) / nuevo_n_exc), 4)
            stats_exc["n"] = nuevo_n_exc

        pieza_pct_actual = resultado.get("porcentaje_piezas", observacion.get("porcentaje_piezas_ultima", 0.0))
        pieza_pct_anterior = observacion.get("porcentaje_piezas_ultima", pieza_pct_actual)
        stats_piezas = self.memoria["impacto_cuota_piezas"]
        nuevo_n_piezas = stats_piezas["n"] + 1
        delta_piezas = pieza_pct_actual - pieza_pct_anterior
        stats_piezas["media"] = round(stats_piezas["media"] + ((delta_piezas - stats_piezas["media"]) / nuevo_n_piezas), 4)
        stats_piezas["n"] = nuevo_n_piezas

        stats_estrategia = self.memoria["estrategias_venta"].get(estrategia_actual, {"media": 0.0, "n": 0})
        nuevo_n_estrategia = stats_estrategia["n"] + 1
        score_estrategia = 0.8 if resultado.get("cuota_mercado", observacion.get("cuota_mercado_ultima", 0.0)) >= observacion.get("cuota_mercado_ultima", 0.0) else -0.5
        if resultado.get("ingresos_carrera", 0.0) > observacion.get("ingresos_recientes", 0.0):
            score_estrategia += 0.4
        if pieza_pct_actual >= 25.0:
            score_estrategia += 0.35
        elif pieza_pct_actual <= 15.0 and not contratos_activos:
            score_estrategia -= 0.35
        nueva_media_estrategia = stats_estrategia["media"] + ((score_estrategia - stats_estrategia["media"]) / nuevo_n_estrategia)
        self.memoria["estrategias_venta"][estrategia_actual] = {"media": round(nueva_media_estrategia, 4), "n": nuevo_n_estrategia}

        evaluacion = self._evaluar_post_ronda_venta(resultado, estrategia_actual)
        self.memoria["ultima_evaluacion_post_ronda"] = evaluacion

        ultima_mejora = self.memoria.get("ultima_mejora") or {}
        slot_mejorado = ultima_mejora.get("slot")
        if slot_mejorado in {"chasis", "motor", "ruedas"} and resultado.get("mejora_realizada"):
            stats_mejora = self.memoria["estrategias_mejora"].get(slot_mejorado, {"media": 0.0, "n": 0})
            nuevo_n_mejora = stats_mejora["n"] + 1
            roi_mejora = resultado.get("roi_mejora", 0.0)
            puntuacion_mejora = roi_mejora
            mejora_real_abs = resultado.get("mejora_real_abs", 0.0)
            if mejora_real_abs >= ultima_mejora.get("mejora_esperada_pct", 0.0) * 0.8:
                puntuacion_mejora += 0.15
            if mejora_real_abs <= ultima_mejora.get("mejora_esperada_pct", 0.0) * 0.5:
                puntuacion_mejora -= 0.10
            stats_mejora["media"] = round(stats_mejora["media"] + ((puntuacion_mejora - stats_mejora["media"]) / nuevo_n_mejora), 4)
            stats_mejora["n"] = nuevo_n_mejora
            self.memoria["estrategias_mejora"][slot_mejorado] = stats_mejora

            self.memoria["historial_mejoras"].append(
                {
                    "slot": slot_mejorado,
                    "roi_mejora": round(roi_mejora, 4),
                    "mejora_real_abs": round(mejora_real_abs, 4),
                    "coste_mejora": round(resultado.get("coste_mejora", 0.0), 2),
                }
            )
            self.memoria["historial_mejoras"] = self.memoria["historial_mejoras"][-20:]

        # Persistimos memoria tras aprender
        try:
            self.save_memory()
        except Exception:
            pass

    def _banda_calidad(self, calidad):
        if calidad <= 3.0:
            return "baja"
        if calidad <= 6.0:
            return "media"
        return "alta"

    def _resumen_presupuestos_mercado(self, presupuestos_pilotos):
        valores = list(presupuestos_pilotos.values())
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

    def construir_estado_mejora(self, observacion):
        calidad_propia = observacion.get("calidad_propia", {})
        calidad_competencia = observacion.get("calidad_competencia", {})
        demanda_mercado = observacion.get("demanda_mercado_por_slot", {})
        demanda_propia = observacion.get("demanda_propia_por_slot", {})
        presupuestos_pilotos = observacion.get("presupuestos_pilotos", {})
        presupuestos_resumen = self._resumen_presupuestos_mercado(presupuestos_pilotos)

        return {
            "calidad_propia": calidad_propia,
            "calidad_competencia": calidad_competencia,
            "precios_propios": observacion.get("precios_propios", {}),
            "precios_competencia": observacion.get("precios_competencia", {}),
            "demanda_mercado_por_slot": demanda_mercado,
            "demanda_propia_por_slot": demanda_propia,
            "presupuestos_pilotos": presupuestos_pilotos,
            "presupuestos_resumen": presupuestos_resumen,
            "presupuesto_mejora_disponible": observacion.get("presupuesto_mejora_disponible", 0.0),
            "ingresos_recientes": observacion.get("ingresos_recientes", 0.0),
            "cuota_mercado": observacion.get("cuota_mercado_ultima", 0.0),
        }

    def decidir_mejora(self, observacion):
        estado = self.construir_estado_mejora(observacion)
        carrera_actual = int(observacion.get("carrera_actual", 1))
        presupuesto = estado["presupuesto_mejora_disponible"]
        demanda_mercado = estado["demanda_mercado_por_slot"]
        demanda_propia = estado["demanda_propia_por_slot"]
        calidad_propia = estado["calidad_propia"]
        calidad_competencia = estado["calidad_competencia"]
        precios_propios = estado["precios_propios"]
        presupuesto_medio = estado["presupuestos_resumen"]["media"]
        costes_estimados = observacion.get("costes_mejora_estimados", {})

        if carrera_actual <= 1:
            decision = DecisionMejoraVendedor(
                slot=None,
                mejora_esperada_pct=0.0,
                coste_estimado=0.0,
                prioridad=0.0,
                razonamiento=f"Tienda {self.letra} no mejora en la carrera 1: falta historial de mercado para evaluar ROI.",
            )
            self.memoria["ultima_mejora"] = {
                "slot": None,
                "mejora_esperada_pct": 0.0,
                "coste_estimado": 0.0,
                "prioridad": 0.0,
                "razonamiento": decision.razonamiento,
            }
            self.memoria["historial_mejoras"].append(self.memoria["ultima_mejora"])
            self.memoria["historial_mejoras"] = self.memoria["historial_mejoras"][-20:]
            return decision

        mejor_decision = None
        mejor_puntuacion_sin_mejora = 0.12
        for slot in ["chasis", "motor", "ruedas"]:
            calidad_actual = float(calidad_propia.get(slot, 0.0))
            if calidad_actual >= 10.0:
                continue
            precio_actual = float(precios_propios.get(slot, 0.0))
            demanda_total = float(sum(demanda_mercado.get(slot, {}).values()))
            demanda_propia_slot = float(demanda_propia.get(slot, 0.0))
            cuota_slot = (demanda_propia_slot / demanda_total) if demanda_total > 0 else 0.0

            rivales = {
                vendedor: datos.get(slot, 0.0)
                for vendedor, datos in calidad_competencia.items()
                if vendedor != self.letra
            }
            rivales_ordenados = sorted(rivales.values(), reverse=True)
            mejor_rival = rivales_ordenados[0] if rivales_ordenados else 0.0
            segundo_rival = rivales_ordenados[1] if len(rivales_ordenados) > 1 else mejor_rival
            competencia_similar = sum(1 for valor in rivales_ordenados if abs(valor - calidad_actual) <= 1.25)
            densidad_competencia = competencia_similar / max(1, len(rivales_ordenados))

            banda_propia = self._banda_calidad(calidad_actual)
            bandas_rivales = {"baja": 0, "media": 0, "alta": 0}
            for valor in rivales.values():
                bandas_rivales[self._banda_calidad(valor)] += 1
            hueco_banda = 1.0 if bandas_rivales[banda_propia] <= 1 else 0.0

            if calidad_actual <= 3.0:
                mejora_esperada = 0.75
            elif calidad_actual <= 6.0:
                mejora_esperada = 1.0
            elif calidad_actual <= 8.0:
                mejora_esperada = 1.3
            else:
                mejora_esperada = 1.55

            mejora_maxima_real = max(0.0, 10.0 - calidad_actual)
            mejora_esperada_realista = min(mejora_esperada, mejora_maxima_real)
            if mejora_esperada_realista <= 0.0:
                continue

            calidad_proyectada = min(10.0, calidad_actual + mejora_esperada_realista)
            precio_proyectado = max(precio_actual, 10.0 + (calidad_proyectada / 10.0) * 50.0)
            incremento_precio = max(0.0, precio_proyectado - precio_actual)

            presupuesto_relativo = precio_proyectado / max(1.0, presupuesto_medio)
            if presupuesto_relativo <= 0.18:
                afinidad_presupuesto = 1.0
            elif presupuesto_relativo <= 0.28:
                afinidad_presupuesto = 0.82
            elif presupuesto_relativo <= 0.40:
                afinidad_presupuesto = 0.55
            else:
                afinidad_presupuesto = max(0.05, 1.20 - presupuesto_relativo * 2.0)

            oportunidad_oferta = 0.20
            if hueco_banda > 0:
                oportunidad_oferta += 0.25
            if calidad_actual >= mejor_rival + 1.0:
                oportunidad_oferta += 0.22
            elif calidad_actual <= mejor_rival - 1.25:
                oportunidad_oferta += 0.10
            if calidad_actual >= segundo_rival + 0.75:
                oportunidad_oferta += 0.12
            oportunidad_oferta += max(0.0, 0.25 - densidad_competencia * 0.25)
            if cuota_slot >= 0.40:
                oportunidad_oferta += 0.15
            elif cuota_slot <= 0.20:
                oportunidad_oferta += 0.08

            demanda_total_mercado = max(1.0, sum(sum(slot_demanda.values()) for slot_demanda in demanda_mercado.values()))
            demanda_norm = demanda_total / demanda_total_mercado
            coste_estimado = float(costes_estimados.get(slot, 0.0))
            if coste_estimado <= 0.0:
                coste_estimado = self._estimar_coste_mejora_local(calidad_actual, slot, mejora_esperada_realista)
            roi_estimado = ((demanda_propia_slot * incremento_precio) + ((demanda_total - demanda_propia_slot) * precio_proyectado * oportunidad_oferta * afinidad_presupuesto)) / max(1.0, coste_estimado)
            puntuacion = (
                0.32 * oportunidad_oferta
                + 0.28 * demanda_norm
                + 0.20 * afinidad_presupuesto
                + 0.20 * min(1.5, roi_estimado / 2.0)
            )

            if mejora_esperada_realista < mejora_esperada * 0.75:
                puntuacion -= 0.18
            if mejora_esperada_realista <= 0.20:
                puntuacion -= 0.25

            if presupuesto < coste_estimado:
                puntuacion -= 0.45
            if self.memoria["estrategias_mejora"][slot]["n"] >= 2:
                puntuacion += self.memoria["estrategias_mejora"][slot]["media"] * 0.10

            razonamiento = (
                f"{slot}: mejora esperada {mejora_esperada:.2f} capada a {mejora_esperada_realista:.2f} | "
                f"oferta {oportunidad_oferta:.2f} | demanda {demanda_norm:.2f} | "
                f"presupuesto {afinidad_presupuesto:.2f} | ROI {roi_estimado:.2f} | "
                f"densidad {densidad_competencia:.2f}"
            )

            decision_slot = DecisionMejoraVendedor(
                slot=slot,
                mejora_esperada_pct=round(mejora_esperada_realista, 4),
                coste_estimado=round(coste_estimado, 2),
                prioridad=round(puntuacion, 4),
                razonamiento=razonamiento,
            )

            if mejor_decision is None or decision_slot.prioridad > mejor_decision.prioridad:
                mejor_decision = decision_slot

        if mejor_decision is None:
            mejor_decision = DecisionMejoraVendedor(None, 0.0, 0.0, 0.0, "Sin datos para decidir mejora")

        if mejor_decision.slot is None:
            decision = DecisionMejoraVendedor(
                slot=None,
                mejora_esperada_pct=0.0,
                coste_estimado=0.0,
                prioridad=0.0,
                razonamiento=f"Tienda {self.letra} no mejora ninguna pieza: no ve una mejora rentable o alcanzable.",
            )
        elif mejor_decision.coste_estimado > presupuesto or mejor_decision.prioridad < mejor_puntuacion_sin_mejora or presupuesto < max(1.0, mejor_decision.coste_estimado * 0.5):
            decision = DecisionMejoraVendedor(
                slot=None,
                mejora_esperada_pct=0.0,
                coste_estimado=0.0,
                prioridad=round(mejor_decision.prioridad, 4),
                razonamiento=(
                    f"Tienda {self.letra} pospone mejoras: {mejor_decision.razonamiento}"
                    if mejor_decision.razonamiento
                    else f"Tienda {self.letra} pospone mejoras por falta de oportunidad clara"
                ),
            )
        else:
            decision = DecisionMejoraVendedor(
                slot=mejor_decision.slot,
                mejora_esperada_pct=mejor_decision.mejora_esperada_pct,
                coste_estimado=mejor_decision.coste_estimado,
                prioridad=mejor_decision.prioridad,
                razonamiento=f"Tienda {self.letra} mejora {mejor_decision.slot}: {mejor_decision.razonamiento}",
            )

        self.memoria["ultima_mejora"] = {
            "slot": decision.slot,
            "mejora_esperada_pct": decision.mejora_esperada_pct,
            "coste_estimado": decision.coste_estimado,
            "prioridad": decision.prioridad,
            "razonamiento": decision.razonamiento,
        }
        self.memoria["historial_mejoras"].append(self.memoria["ultima_mejora"])
        self.memoria["historial_mejoras"] = self.memoria["historial_mejoras"][-20:]
        return decision

    def funcion_objetivo_venta(self, demanda_pieza, cuota_mercado_ultima, variacion_precio, aprendizaje_slot):
        """Objetivo del vendedor.

        Combina cuatro metas:
        1) Maximizar ingresos acumulados (proxy: demanda * nivel de precio).
        2) Evitar subidas excesivas que destruyan demanda.
        3) Activar descuentos cuando la cuota de mercado cae demasiado.
        4) Incorporar aprendizaje historico sobre subir o bajar precio por slot.
        """
        ingresos_proxy = demanda_pieza * (1.0 + variacion_precio)
        penalizacion_precio_alto = max(0.0, variacion_precio - 0.12) * 2.0
        incentivo_rescate_cuota = max(0.0, (15.0 - cuota_mercado_ultima) / 15.0) * max(0.0, -variacion_precio)

        return (
            0.60 * ingresos_proxy
            - 0.25 * penalizacion_precio_alto
            + 0.10 * incentivo_rescate_cuota
            + 0.30 * aprendizaje_slot
        )

    def funcion_valor_precio(
        self,
        ingreso_esperado,
        probabilidad_venta,
        elasticidad_estimada,
        posicion_competitiva,
        impacto_demanda_futura,
    ):
        ingreso_norm = min(1.0, ingreso_esperado / 120.0)
        prob_norm = max(0.0, min(1.0, probabilidad_venta))
        elasticidad_penalizacion = min(1.0, max(0.0, elasticidad_estimada / 3.0))
        impacto_norm = max(-1.0, min(1.0, impacto_demanda_futura))

        return (
            0.32 * ingreso_norm
            + 0.24 * prob_norm
            - 0.16 * elasticidad_penalizacion
            + 0.14 * posicion_competitiva
            + 0.14 * impacto_norm
        )

    def _estimar_metricas_precio(self, slot, variacion_precio, estado):
        precio_actual = estado.get("precios_propios", {}).get(slot, 20.0)
        precio_propuesto = max(1.0, precio_actual * (1.0 + variacion_precio))
        demanda_reciente = estado["demanda_reciente_por_pieza"][slot]

        precios_rivales = [datos[slot] for _, datos in estado["precios_competencia"].items() if slot in datos]
        media_rival = sum(precios_rivales) / len(precios_rivales) if precios_rivales else precio_propuesto
        posicion_competitiva = 1.0 - ((precio_propuesto - media_rival) / max(1.0, media_rival))
        posicion_competitiva = max(-1.0, min(1.0, posicion_competitiva))

        segmento = self._segmento_mercado(estado["cuota_mercado"])
        key_segmento = f"{slot}:{segmento}"
        elasticidad_estimada = self.memoria["sensibilidad_segmentos"].get(key_segmento, {"media": 0.8}).get("media", 0.8)

        presion_precio = max(-1.0, min(1.0, (precio_propuesto - media_rival) / max(1.0, media_rival)))
        base_prob = 0.35 + min(0.55, demanda_reciente / 4.0)
        probabilidad_venta = max(0.05, min(0.98, base_prob - (presion_precio * 0.35 * max(0.4, elasticidad_estimada))))

        demanda_esperada = probabilidad_venta * 3.0
        ingreso_esperado = demanda_esperada * precio_propuesto

        impacto_demanda_futura = 0.0
        if variacion_precio > 0:
            impacto_demanda_futura -= self.memoria["impacto_subidas"].get(slot, 0.0)
        if variacion_precio < 0:
            impacto_demanda_futura += self.memoria["impacto_rebajas_cuota"].get("media", 0.0) / 10.0

        return {
            "precio_propuesto": precio_propuesto,
            "ingreso_esperado": ingreso_esperado,
            "probabilidad_venta": probabilidad_venta,
            "elasticidad_estimada": elasticidad_estimada,
            "posicion_competitiva": posicion_competitiva,
            "impacto_demanda_futura": impacto_demanda_futura,
        }

    def _estimar_beneficio_riesgo_venta(self, metricas, variacion_precio, estrategia_venta):
        perfil = self._perfil_estrategia_venta(estrategia_venta)
        beneficio_esperado = metricas["ingreso_esperado"] * (0.75 + perfil["peso_precio"])
        riesgo_demanda = (1.0 - metricas["probabilidad_venta"]) * (1.0 + abs(variacion_precio) * 1.5)
        riesgo_elastico = min(1.5, metricas["elasticidad_estimada"] * abs(variacion_precio))
        riesgo_total = (0.65 * riesgo_demanda) + (0.35 * riesgo_elastico)
        estabilidad = 1.0 - min(1.0, abs(variacion_precio))
        utilidad = beneficio_esperado - (12.0 * riesgo_total) + (2.0 * estabilidad)
        return {
            "beneficio_esperado": beneficio_esperado,
            "riesgo_total": riesgo_total,
            "utilidad": utilidad,
        }

    def _actualizar_memoria_ajuste(self, slot, demanda_pieza, variacion_precio):
        acierto_subida = demanda_pieza >= 2 and variacion_precio > 0
        acierto_bajada = demanda_pieza == 0 and variacion_precio < 0
        resultado = 1.0 if (acierto_subida or acierto_bajada) else -0.4
        self.memoria_ajustes[slot] = self.memoria_ajustes[slot] * 0.8 + (0.2 * resultado)

    def _estimar_coste_mejora_local(self, calidad_actual, slot, mejora_esperada_abs):
        factor_slot = {"chasis": 1.05, "motor": 0.95, "ruedas": 0.90}
        coste_base = 9.5 + (max(0.0, calidad_actual) ** 2) * 1.6
        factor_mejora = 1.0 + max(0.0, mejora_esperada_abs - 0.5) * 0.18
        return round(coste_base * factor_slot.get(slot, 1.0) * factor_mejora, 2)

    def construir_estado_venta(
        self,
        demandas_ultimas,
        uso_ganador,
        cuota_mercado_ultima,
        ingresos_recientes=0.0,
        precios_competencia=None,
        precios_propios=None,
        historico_contratos=None,
        piezas_vendidas_ultima=0,
        total_piezas_mercado=0,
        porcentaje_piezas_ultima=0.0,
    ):
        if precios_competencia is None:
            precios_competencia = {}
        if precios_propios is None:
            precios_propios = {}
        if historico_contratos is None:
            historico_contratos = []

        self.historial_contratos.extend(historico_contratos)
        self.historial_contratos = self.historial_contratos[-30:]

        return {
            "demanda_reciente_por_pieza": {
                "chasis": demandas_ultimas["chasis"].get(self.letra, 0),
                "motor": demandas_ultimas["motor"].get(self.letra, 0),
                "ruedas": demandas_ultimas["ruedas"].get(self.letra, 0),
            },
            "ingresos_recientes": ingresos_recientes,
            "cuota_mercado": cuota_mercado_ultima,
            "piezas_vendidas_ultima": piezas_vendidas_ultima,
            "total_piezas_mercado": total_piezas_mercado,
            "porcentaje_piezas_ultima": porcentaje_piezas_ultima,
            "precios_competencia": precios_competencia,
            "precios_propios": precios_propios,
            "uso_ganador": {
                "chasis": uso_ganador.get("chasis"),
                "motor": uso_ganador.get("motor"),
                "ruedas": uso_ganador.get("ruedas"),
            },
            "historico_contratos_exclusividades": list(self.historial_contratos),
        }

    def decidir_variacion_q(
        self,
        demandas_ultimas,
        uso_ganador,
        cuota_mercado_ultima,
        ingresos_recientes=0.0,
        precios_competencia=None,
        precios_propios=None,
        historico_contratos=None,
        estado_q=None,
        estrategia_venta="defender_posicion",
        nivel_exploracion=0.1,
    ):
        estado = self.construir_estado_venta(
            demandas_ultimas=demandas_ultimas,
            uso_ganador=uso_ganador,
            cuota_mercado_ultima=cuota_mercado_ultima,
            ingresos_recientes=ingresos_recientes,
            precios_competencia=precios_competencia,
            precios_propios=precios_propios,
            historico_contratos=historico_contratos,
        )
        perfil_estrategia = self._perfil_estrategia_venta(estrategia_venta)

        variaciones = {}
        razonamientos = []
        
        # El pánico global por marginación absoluta (<15% de ingresos totales) se mantiene como salvaguarda
        guerra_de_precios_global = estado["cuota_mercado"] < 15.0 and estado["cuota_mercado"] >= 0.0
        
        for slot in ["chasis", "motor", "ruedas"]:
            demanda_pieza = estado["demanda_reciente_por_pieza"][slot]
            pieza_fue_ganadora = estado["uso_ganador"][slot] == self.letra
            
            # 1. CASO CRÍTICO: Si la tienda está al borde de la quiebra global, tira los precios de todo
            if guerra_de_precios_global:
                variaciones[slot] = -0.25
                razonamientos.append(f"{slot}: REBAJA CRISIS GLOBAL")
                continue
                
            # 2. EVALUACIÓN QUIRÚRGICA POR PIEZA (Lógica de Monopolio o Liquidación Individual)
            if demanda_pieza == 3:
                # Dominio absoluto de este componente: Avaricia máxima aplicada solo aquí
                factor_avaricia = self.sensibilidad_precio * 2.5
                variaciones[slot] = factor_avaricia * 1.8
                razonamientos.append(f"{slot}: ¡MONOPOLIO ABSOLUTO! Subida exprimidora")
                
            elif demanda_pieza == 2 or pieza_fue_ganadora:
                # Buen dominio de la pieza: Subida estándar para aumentar margen
                variaciones[slot] = self.sensibilidad_precio * 1.5
                razonamientos.append(f"{slot}: Dominio notable. Incremento de margen")
                
            elif demanda_pieza == 0:
                # FRACASO INDIVIDUAL: Nadie quiere esta pieza específica. 
                # Da igual si la tienda nada en oro gracias a otros slots; esta pieza SE LIQUIDA.
                variaciones[slot] = -0.20
                razonamientos.append(f"{slot}: LIQUIDACIÓN INDIVIDUAL (Ventas = 0)")
                
            else:
                # Equilibrio competitivo (1 comprador): ajuste leve guiado por presión competitiva y memoria.
                precios_rivales = [datos[slot] for _, datos in estado["precios_competencia"].items() if slot in datos]
                if precios_rivales:
                    media_rival = sum(precios_rivales) / len(precios_rivales)
                    precio_propio = estado.get("precios_propios", {}).get(slot, media_rival)
                    presion_competitiva = (precio_propio - media_rival) / max(1.0, media_rival)
                    memoria_ajuste = self.memoria["impacto_subidas"].get(slot, 0.0) - (self.memoria["impacto_rebajas_cuota"].get("media", 0.0) / 10.0)
                    variaciones[slot] = round((-0.4 * presion_competitiva) + (0.02 * memoria_ajuste), 4)
                    razonamientos.append(f"{slot}: Posición estable guiada por presión competitiva")
                else:
                    variaciones[slot] = 0.0
                    razonamientos.append(f"{slot}: Posición estable sin referencia rival")

            variaciones[slot] += perfil_estrategia["sesgo_variacion"]

            variaciones[slot] = self._aplicar_memoria_variacion(slot, variaciones[slot], estado)
            variaciones[slot] = round(variaciones[slot], 4)

            metricas = self._estimar_metricas_precio(slot, variaciones[slot], estado)
            valor_precio = self.funcion_valor_precio(
                ingreso_esperado=metricas["ingreso_esperado"],
                probabilidad_venta=metricas["probabilidad_venta"],
                elasticidad_estimada=metricas["elasticidad_estimada"],
                posicion_competitiva=metricas["posicion_competitiva"],
                impacto_demanda_futura=metricas["impacto_demanda_futura"],
            )
            valor_q = 0.0 if estado_q is None else self.obtener_valor_q(estado_q, {"slot": slot, "variacion": round(variaciones[slot], 4)}, contexto="venta")
            plan = self._estimar_beneficio_riesgo_venta(metricas, variaciones[slot], estrategia_venta)
            estabilidad = 1.0 - min(1.0, abs(variaciones[slot]))
            valor_total = (
                (perfil_estrategia["peso_precio"] * valor_precio)
                + (perfil_estrategia["peso_q"] * valor_q)
                + (perfil_estrategia["peso_estabilidad"] * estabilidad)
                + (0.12 * plan["utilidad"])
            )
            razonamientos.append(f"{slot}: valor-precio {valor_total:+.2f}")

            objetivo_slot = self.funcion_objetivo_venta(
                demanda_pieza=demanda_pieza,
                cuota_mercado_ultima=estado["cuota_mercado"],
                variacion_precio=variaciones[slot],
                aprendizaje_slot=self.memoria_ajustes[slot],
            )

            # Si el objetivo sale debil tras una subida agresiva, suavizamos para no matar demanda.
            if objetivo_slot < 0 and variaciones[slot] > 0.12:
                variaciones[slot] = round(variaciones[slot] * 0.5, 4)
                razonamientos.append(f"{slot}: Ajuste defensivo para sostener demanda")

            if estado["ingresos_recientes"] <= 0.0:
                variaciones[slot] = round(variaciones[slot] - 0.08, 4)
            if estrategia_venta == "crecer_cuota" and demanda_pieza <= 1:
                variaciones[slot] = round(variaciones[slot] - 0.02, 4)
            elif estrategia_venta == "exprimir_margen" and demanda_pieza >= 2:
                variaciones[slot] = round(variaciones[slot] + 0.02, 4)
            elif estrategia_venta == "captar_contratos_exclusivos" and estado["historico_contratos_exclusividades"]:
                variaciones[slot] = round(variaciones[slot] + 0.01, 4)

            if demanda_pieza == 0:
                racha_sin_ventas = self.memoria["rachas_sin_ventas"].get(slot, 0)
                rebaja_forzada = -0.18 - min(0.12, 0.03 * racha_sin_ventas)
                variaciones[slot] = min(variaciones[slot], rebaja_forzada)
                razonamientos.append(f"{slot}: ajuste forzado por ventas nulas ({racha_sin_ventas} ronda(s))")

            plan_final = self._estimar_beneficio_riesgo_venta(
                self._estimar_metricas_precio(slot, variaciones[slot], estado),
                variaciones[slot],
                estrategia_venta,
            )
            razonamientos.append(
                f"{slot}: plan beneficio-riesgo {plan_final['utilidad']:+.2f} "
                f"(beneficio {plan_final['beneficio_esperado']:.2f}, riesgo {plan_final['riesgo_total']:.2f})"
            )

            self._actualizar_memoria_ajuste(slot, demanda_pieza, variaciones[slot])

        return DecisionVendedor(
            variacion_chasis=variaciones["chasis"],
            variacion_motor=variaciones["motor"],
            variacion_ruedas=variaciones["ruedas"],
            razonamiento=f"Tienda {self.letra} [{estrategia_venta}] -> " + " | ".join(razonamientos)
        )
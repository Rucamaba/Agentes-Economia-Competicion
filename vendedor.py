import random
from agente_base import AgenteBase

class DecisionVendedor:
    def __init__(self, variacion_chasis, variacion_motor, variacion_ruedas, razonamiento):
        self.variacion_chasis = variacion_chasis
        self.variacion_motor = variacion_motor
        self.variacion_ruedas = variacion_ruedas
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
        self.memoria["sensibilidad_segmentos"] = {}
        self.memoria["rentabilidad_exclusividad"] = {"media": 0.0, "n": 0}
        self.memoria["estrategias_venta"] = {
            "crecer_cuota": {"media": 0.0, "n": 0},
            "exprimir_margen": {"media": 0.0, "n": 0},
            "defender_posicion": {"media": 0.0, "n": 0},
            "captar_contratos_exclusivos": {"media": 0.0, "n": 0},
        }
        self.memoria["evaluaciones_post_ronda"] = []
        self.memoria["pautas_recordadas"] = {}

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

        if contrato_perjudicial:
            pauta = "proteger rentabilidad contractual"
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
            historico_contratos=observacion.get("historico_contratos", []),
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
            historico_contratos=observacion.get("historico_contratos", []),
        )
        estrategia_venta = self._seleccionar_estrategia_venta(estado)
        decision = self.decidir_variacion_q(
            demandas_ultimas=observacion.get("demandas_ultimas", {}),
            uso_ganador=observacion.get("uso_ganador", {}),
            cuota_mercado_ultima=observacion.get("cuota_mercado_ultima", 0.0),
            ingresos_recientes=observacion.get("ingresos_recientes", 0.0),
            precios_competencia=observacion.get("precios_competencia", {}),
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

        stats_estrategia = self.memoria["estrategias_venta"].get(estrategia_actual, {"media": 0.0, "n": 0})
        nuevo_n_estrategia = stats_estrategia["n"] + 1
        score_estrategia = 0.8 if resultado.get("cuota_mercado", observacion.get("cuota_mercado_ultima", 0.0)) >= observacion.get("cuota_mercado_ultima", 0.0) else -0.5
        if resultado.get("ingresos_carrera", 0.0) > observacion.get("ingresos_recientes", 0.0):
            score_estrategia += 0.4
        nueva_media_estrategia = stats_estrategia["media"] + ((score_estrategia - stats_estrategia["media"]) / nuevo_n_estrategia)
        self.memoria["estrategias_venta"][estrategia_actual] = {"media": round(nueva_media_estrategia, 4), "n": nuevo_n_estrategia}

        evaluacion = self._evaluar_post_ronda_venta(resultado, estrategia_actual)
        self.memoria["ultima_evaluacion_post_ronda"] = evaluacion

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
        precio_propuesto = max(5.0, min(80.0, precio_actual * (1.0 + variacion_precio)))
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

    def construir_estado_venta(
        self,
        demandas_ultimas,
        uso_ganador,
        cuota_mercado_ultima,
        ingresos_recientes=0.0,
        precios_competencia=None,
        historico_contratos=None,
    ):
        if precios_competencia is None:
            precios_competencia = {}
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
            "precios_competencia": precios_competencia,
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
                # Equilibrio competitivo (1 comprador): Ajuste leve, con poca exploración al inicio.
                variaciones[slot] = random.uniform(-0.02, 0.02) * nivel_exploracion
                razonamientos.append(f"{slot}: Posición estable")

            variaciones[slot] += perfil_estrategia["sesgo_variacion"]

            variaciones[slot] = self._aplicar_memoria_variacion(slot, variaciones[slot], estado)

            candidatos = {
                round(variaciones[slot], 4),
                -0.30,
                -0.22,
                -0.15,
                -0.08,
                -0.03,
                0.0,
                0.04,
                0.08,
                0.12,
                0.18,
                0.25,
            }

            ranking_candidatos = []
            for variacion_candidata in sorted(candidatos):
                metricas = self._estimar_metricas_precio(slot, variacion_candidata, estado)
                valor_precio = self.funcion_valor_precio(
                    ingreso_esperado=metricas["ingreso_esperado"],
                    probabilidad_venta=metricas["probabilidad_venta"],
                    elasticidad_estimada=metricas["elasticidad_estimada"],
                    posicion_competitiva=metricas["posicion_competitiva"],
                    impacto_demanda_futura=metricas["impacto_demanda_futura"],
                )
                valor_q = 0.0 if estado_q is None else self.obtener_valor_q(estado_q, {"slot": slot, "variacion": round(variacion_candidata, 4)}, contexto="venta")
                plan = self._estimar_beneficio_riesgo_venta(metricas, variacion_candidata, estrategia_venta)
                estabilidad = 1.0 - min(1.0, abs(variacion_candidata))
                valor_total = (
                    (perfil_estrategia["peso_precio"] * valor_precio)
                    + (perfil_estrategia["peso_q"] * valor_q)
                    + (perfil_estrategia["peso_estabilidad"] * estabilidad)
                    + (0.12 * plan["utilidad"])
                )
                ranking_candidatos.append({
                    "variacion": variacion_candidata,
                    "valor_total": valor_total,
                })

            ranking_candidatos.sort(key=lambda item: item["valor_total"], reverse=True)
            mejor_valor = ranking_candidatos[0]["valor_total"]
            empatados = [item for item in ranking_candidatos if abs(item["valor_total"] - mejor_valor) <= 1e-9]
            if len(empatados) > 1:
                mejor_variacion = random.choice(empatados)["variacion"]
                razonamientos.append(f"{slot}: desempate entre opciones equivalentes")
            elif len(ranking_candidatos) > 1 and random.random() < nivel_exploracion:
                limite = min(3, len(ranking_candidatos))
                explorables = ranking_candidatos[:limite]
                pesos = [1.0 / (indice + 1) for indice in range(limite)]
                mejor_variacion = random.choices(explorables, weights=pesos, k=1)[0]["variacion"]
                razonamientos.append(f"{slot}: exploración controlada de precio")
            else:
                mejor_variacion = ranking_candidatos[0]["variacion"]

            variaciones[slot] = round(mejor_variacion, 4)
            razonamientos.append(f"{slot}: Valor-precio óptimo {variaciones[slot]:+.2f}")

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

            if estrategia_venta == "crecer_cuota" and demanda_pieza <= 1:
                variaciones[slot] = round(min(variaciones[slot], 0.02), 4)
            elif estrategia_venta == "exprimir_margen" and demanda_pieza >= 2:
                variaciones[slot] = round(max(variaciones[slot], 0.04), 4)
            elif estrategia_venta == "defender_posicion":
                variaciones[slot] = round(max(-0.08, min(0.08, variaciones[slot])), 4)
            elif estrategia_venta == "captar_contratos_exclusivos" and estado["historico_contratos_exclusividades"]:
                variaciones[slot] = round(variaciones[slot] + 0.01, 4)

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
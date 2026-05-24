import random
import math
from economia_costes import calcular_coste_bruto, calcular_coste_imputable
from agente_base import AgenteBase

class EleccionKart:
    def __init__(self, razonamiento, vendedor_chasis, seller_motor, vendedor_ruedas):
        self.razonamiento = razonamiento
        self.vendedor_chasis = vendedor_chasis
        self.vendedor_motor = seller_motor
        self.vendedor_ruedas = vendedor_ruedas
        # indicador opcional para plantarse (no comprar esta ronda)
        self.plantarse = False

class AgenteComprador(AgenteBase):
    def __init__(self, nombre):
        super().__init__(
            nombre=nombre,
            parametros_aprendizaje={"alpha": 0.15, "temperatura": 0.7},
        )
        # --- MEMORIA A LARGO PLAZO ---
        # Bajamos alpha a 0.15 para que recuerden los éxitos pasados y no tengan amnesia
        self.alpha = self.parametros_aprendizaje["alpha"]
        self.temperatura = self.parametros_aprendizaje["temperatura"]  # Un pelo más frío para consolidar los setups campeones
        
        self.q_chasis = {letra: 0.0 for letra in ["A", "B", "C", "D", "E"]}
        self.q_motor = {letra: 0.0 for letra in ["A", "B", "C", "D", "E"]}
        self.q_ruedas = {letra: 0.0 for letra in ["A", "B", "C", "D", "E"]}
        
        self.historico_rendimientos = []
        self.historial_resultados = []
        self.rendimiento_combinaciones = {}
        self.memoria["equilibrio_vendedor"] = {
            letra: {"media": 0.0, "n": 0}
            for letra in ["A", "B", "C", "D", "E"]
        }
        self.memoria["combos_posicion"] = {}
        self.memoria["bloqueos_frecuentes"] = {"chasis": {}, "motor": {}, "ruedas": {}}
        self.memoria["estrategia_presupuesto"] = {
            "bajo": {"preferencia_ahorro": 0.6, "preferencia_rendimiento": 0.4, "n": 0},
            "medio": {"preferencia_ahorro": 0.5, "preferencia_rendimiento": 0.5, "n": 0},
            "alto": {"preferencia_ahorro": 0.4, "preferencia_rendimiento": 0.6, "n": 0},
        }
        self.memoria["estrategias_compra"] = {
            "agresiva": {"media": 0.0, "n": 0},
            "conservadora": {"media": 0.0, "n": 0},
            "oportunista": {"media": 0.0, "n": 0},
            "equilibrada": {"media": 0.0, "n": 0},
        }
        self.memoria["evaluaciones_post_ronda"] = []
        self.memoria["pautas_recordadas"] = {}
        # Intentamos cargar memoria persistida (si existe)
        try:
            self.load_memory()
        except Exception:
            pass

    def _perfil_estrategia_compra(self, estrategia):
        perfiles = {
            "agresiva": {
                "peso_rendimiento": 0.72,
                "peso_ahorro": 0.14,
                "peso_largo_plazo": 0.14,
                "peso_combinacion": 0.30,
                "peso_q": 0.24,
            },
            "conservadora": {
                "peso_rendimiento": 0.40,
                "peso_ahorro": 0.42,
                "peso_largo_plazo": 0.18,
                "peso_combinacion": 0.28,
                "peso_q": 0.18,
            },
            "oportunista": {
                "peso_rendimiento": 0.50,
                "peso_ahorro": 0.28,
                "peso_largo_plazo": 0.22,
                "peso_combinacion": 0.34,
                "peso_q": 0.20,
            },
            "equilibrada": {
                "peso_rendimiento": 0.55,
                "peso_ahorro": 0.25,
                "peso_largo_plazo": 0.20,
                "peso_combinacion": 0.32,
                "peso_q": 0.20,
            },
        }
        return perfiles.get(estrategia, perfiles["equilibrada"])

    def _seleccionar_estrategia_compra(self, estado):
        presupuesto = estado.get("presupuesto_disponible", 100.0)
        segmento = self._segmento_presupuesto(presupuesto)
        media_valoracion = {
            nombre: datos["media"]
            for nombre, datos in self.memoria["estrategias_compra"].items()
        }

        precios = []
        for vendedor in estado.get("precios_actuales", {}).values():
            precios.extend(vendedor.values())
        dispersion = 0.0
        if precios:
            precio_min = min(precios)
            precio_max = max(precios)
            precio_media = sum(precios) / len(precios)
            if precio_media > 0:
                dispersion = (precio_max - precio_min) / precio_media

        resultados_previos = [
            item for item in estado.get("historial_resultados_anteriores", [])
            if isinstance(item, dict)
        ]
        ultimo_podio = resultados_previos[-1]["posicion"] if resultados_previos else 3
        rendimiento_reciente = (
            sum(item.get("rendimiento", 0.0) for item in resultados_previos[-3:])
            / max(1, min(3, len(resultados_previos)))
            if resultados_previos
            else 0.0
        )

        puntuaciones = {
            "agresiva": 0.0,
            "conservadora": 0.0,
            "oportunista": 0.0,
            "equilibrada": 0.0,
        }

        if segmento == "bajo":
            puntuaciones["conservadora"] += 1.0
        elif segmento == "alto":
            puntuaciones["agresiva"] += 0.8
        else:
            puntuaciones["equilibrada"] += 0.6

        if dispersion >= 0.35:
            puntuaciones["oportunista"] += 1.0
        if dispersion <= 0.14:
            puntuaciones["equilibrada"] += 0.5

        if ultimo_podio == 3:
            puntuaciones["agresiva"] += 0.8
        elif ultimo_podio == 2:
            puntuaciones["equilibrada"] += 0.5
        else:
            puntuaciones["conservadora"] += 0.4

        if rendimiento_reciente >= 5.0:
            puntuaciones["agresiva"] += 0.4
        elif rendimiento_reciente <= 2.5:
            puntuaciones["conservadora"] += 0.3

        for nombre, media in media_valoracion.items():
            if self.memoria["estrategias_compra"][nombre]["n"] >= 2:
                puntuaciones[nombre] += media * 0.15

        historial_evaluacion = self.memoria.get("evaluaciones_post_ronda", [])
        if historial_evaluacion:
            ultima_eval = historial_evaluacion[-1]
            if ultima_eval.get("precio") == "perdio":
                puntuaciones["conservadora"] += 0.5
            elif ultima_eval.get("precio") == "gano":
                puntuaciones["oportunista"] += 0.35

            if ultima_eval.get("funciono"):
                puntuaciones["equilibrada"] += 0.2
            if ultima_eval.get("contrato_perjudicial"):
                puntuaciones["agresiva"] += 0.2

        return max(puntuaciones, key=lambda nombre: (puntuaciones[nombre], media_valoracion[nombre]))

    def _evaluar_post_ronda_compra(self, elecciones_hechas, rendimiento_pista, media_parrilla, posicion_podio, gasto_economico=None, presupuesto_disponible=None):
        contratos_activos = (self.memoria.get("ultima_observacion") or {}).get("contratos_activos", [])
        ratio_gasto = None
        if gasto_economico is not None and presupuesto_disponible and presupuesto_disponible > 0:
            ratio_gasto = gasto_economico / presupuesto_disponible

        funciono = posicion_podio <= 2 or rendimiento_pista >= media_parrilla
        if ratio_gasto is None:
            juicio_precio = "neutral"
        elif posicion_podio == 1 and ratio_gasto <= 0.90:
            juicio_precio = "gano"
        elif ratio_gasto >= 0.98 and posicion_podio == 3:
            juicio_precio = "perdio"
        elif ratio_gasto <= 0.80:
            juicio_precio = "gano"
        else:
            juicio_precio = "perdio" if posicion_podio == 3 else "neutral"

        contrato_perjudicial = bool(contratos_activos) and posicion_podio == 3 and ratio_gasto is not None and ratio_gasto > 0.9

        if contrato_perjudicial:
            pauta = "evitar contratos costosos"
        elif juicio_precio == "gano" and funciono:
            pauta = "priorizar combinaciones eficientes"
        elif juicio_precio == "perdio":
            pauta = "reforzar control de gasto"
        else:
            pauta = "mantener equilibrio entre coste y rendimiento"

        evaluacion = {
            "funciono": funciono,
            "precio": juicio_precio,
            "contrato_perjudicial": contrato_perjudicial,
            "pauta": pauta,
            "posicion_podio": posicion_podio,
            "ratio_gasto": round(ratio_gasto, 4) if ratio_gasto is not None else None,
        }

        self.memoria["evaluaciones_post_ronda"].append(evaluacion)
        self.memoria["evaluaciones_post_ronda"] = self.memoria["evaluaciones_post_ronda"][-20:]
        stats_pauta = self.memoria["pautas_recordadas"].get(pauta, {"n": 0})
        stats_pauta["n"] = stats_pauta.get("n", 0) + 1
        self.memoria["pautas_recordadas"][pauta] = stats_pauta
        return evaluacion

    def observar(self, entorno):
        bloqueos = entorno.get("bloqueos_exclusividad", {})
        for slot in ["chasis", "motor", "ruedas"]:
            for vendedor in bloqueos.get(slot, set()):
                prev = self.memoria["bloqueos_frecuentes"][slot].get(vendedor, 0)
                self.memoria["bloqueos_frecuentes"][slot][vendedor] = prev + 1
        # --- Memoria corto plazo: guardamos última observación relevante ---
        corto = self.memoria.get("corto_plazo", {})
        corto["ultimo_precio"] = entorno.get("catalogo_vendedores", {})
        corto["ultima_demanda"] = entorno.get("demanda_reciente", {})
        corto["ultimo_contrato"] = entorno.get("contratos_activos", [])
        self.memoria["corto_plazo"] = corto

        # --- Memoria tendencia de precios (largo plazo) ---
        tendencia = self.memoria.get("tendencia_precios", {})
        catalogo = entorno.get("catalogo_vendedores", {})
        for vendedor, datos in catalogo.items():
            if vendedor not in tendencia:
                tendencia[vendedor] = {"chasis": [], "motor": [], "ruedas": []}
            for slot in ["chasis", "motor", "ruedas"]:
                precio = datos["precios"].get(slot)
                if precio is not None:
                    tendencia[vendedor][slot].append(precio)
                    # mantenemos ventana corta de 6 rondas
                    tendencia[vendedor][slot] = tendencia[vendedor][slot][-6:]
        self.memoria["tendencia_precios"] = tendencia

        self.memoria["ultima_observacion"] = entorno
        return entorno

    def responder_pregunta(self, pregunta):
        contexto = pregunta.get("contexto", {})
        return self.decidir(contexto)

    def _segmento_presupuesto(self, presupuesto):
        if presupuesto < 350:
            return "bajo"
        if presupuesto < 650:
            return "medio"
        return "alto"

    def _estado_q_compra(self, observacion):
        return self.construir_estado_compra(
            catalogo_vendedores=observacion.get("catalogo_vendedores", {}),
            presupuesto_max=observacion.get("presupuesto_max", 1000.0),
            contratos_activos=observacion.get("contratos_activos", []),
            historial_resultados_anteriores=observacion.get("historial_resultados_anteriores", []),
        )

    def decidir(self, observacion):
        estado_q = self._estado_q_compra(observacion)
        carrera_actual = observacion.get("carrera_actual", 1)
        total_carreras = max(1, observacion.get("total_carreras", 10))
        progreso = 0.0 if total_carreras <= 1 else (carrera_actual - 1) / (total_carreras - 1)
        nivel_exploracion = max(0.05, 0.55 * (1.0 - progreso))
        estado = self.construir_estado_compra(
            catalogo_vendedores=observacion.get("catalogo_vendedores", {}),
            presupuesto_max=observacion.get("presupuesto_max", 1000.0),
            contratos_activos=observacion.get("contratos_activos", []),
            historial_resultados_anteriores=observacion.get("historial_resultados_anteriores", []),
        )
        estrategia_compra = self._seleccionar_estrategia_compra(estado)
        decision = self.elegir_componentes_q(
            catalogo_vendedores=observacion.get("catalogo_vendedores", {}),
            presupuesto_max=observacion.get("presupuesto_max", 1000.0),
            bloqueos_exclusividad=observacion.get("bloqueos_exclusividad", {}),
            contratos_activos=observacion.get("contratos_activos", []),
            historial_resultados_anteriores=observacion.get("historial_resultados_anteriores", []),
            estado_q=estado_q,
            estrategia_compra=estrategia_compra,
            nivel_exploracion=nivel_exploracion,
            carrera_actual=carrera_actual,
            total_carreras=total_carreras,
        )
        self.registrar_accion(
            {
                "tipo": "compra_componentes",
                "chasis": decision.vendedor_chasis,
                "motor": decision.vendedor_motor,
                "ruedas": decision.vendedor_ruedas,
                "estado_q": estado_q,
                "accion_q": f"{decision.vendedor_chasis},{decision.vendedor_motor},{decision.vendedor_ruedas}",
                "estrategia_compra": estrategia_compra,
            }
        )
        return decision

    def aprender(self, resultado):
        elecciones = resultado.get("elecciones_hechas")
        if not elecciones:
            return

        posicion = resultado.get("posicion_podio", 3)
        recompensa = 8.0 if posicion == 1 else (0.0 if posicion == 2 else -6.0)
        self.registrar_recompensa(recompensa)

        accion = self.historial_acciones[-1] if self.historial_acciones else {}
        estado_q = accion.get("estado_q") or self._estado_q_compra(self.memoria.get("ultima_observacion") or {})
        accion_q = accion.get("accion_q")
        if estado_q is not None and accion_q is not None:
            self.actualizar_q(estado_q, accion_q, recompensa, contexto="compra")

        self.aprender_de_resultado_rendimiento(
            elecciones_hechas=elecciones,
            rendimiento_pista=resultado.get("rendimiento_pista", 0.0),
            media_parrilla=resultado.get("media_parrilla", 0.0),
            posicion_podio=posicion,
            gasto_economico=resultado.get("gasto_economico"),
            presupuesto_disponible=resultado.get("presupuesto_disponible"),
        )

        # Persistimos memoria tras aprender
        try:
            self.save_memory()
        except Exception:
            pass

    def funcion_objetivo_compra(self, puntos_esperados, gasto_imputable, presupuesto_max, valor_largo_plazo, estrategia="equilibrada"):
        """Objetivo del comprador.

        Prioriza tres metas simultaneas:
        1) Maximizar puntos esperados en carrera.
        2) Mantener el gasto bajo control respecto al presupuesto.
        3) Aprovechar el aprendizaje historico (valores Q) a largo plazo.
        """
        perfil = self._perfil_estrategia_compra(estrategia)
        if presupuesto_max <= 0:
            control_gasto = 0.0
        else:
            ratio_gasto = gasto_imputable / presupuesto_max
            control_gasto = 1.0 - ratio_gasto

        return (
            perfil["peso_rendimiento"] * puntos_esperados
            + perfil["peso_ahorro"] * control_gasto
            + perfil["peso_largo_plazo"] * valor_largo_plazo
        )

    def funcion_valor_combinacion(
        self,
        calidad_total,
        precio_total,
        gasto_imputable,
        estabilidad_proveedor,
        riesgo_exclusividad,
        sinergia_historial,
        presupuesto_max,
    ):
        calidad_norm = calidad_total / 30.0
        precio_norm = 1.0 - min(1.0, precio_total / max(1.0, presupuesto_max * 1.2))
        gasto_norm = 1.0 - min(1.0, gasto_imputable / max(1.0, presupuesto_max))

        return (
            0.30 * calidad_norm
            + 0.14 * precio_norm
            + 0.16 * gasto_norm
            + 0.12 * estabilidad_proveedor
            - 0.12 * riesgo_exclusividad
            + 0.16 * sinergia_historial
        )

    def _coste_minimo_kart_actual(self, catalogo_vendedores, bloqueos_exclusividad):
        costes_minimos = {}
        for slot in ["chasis", "motor", "ruedas"]:
            precios_slot = [
                datos["precios"][slot]
                for vendedor, datos in catalogo_vendedores.items()
                if vendedor not in bloqueos_exclusividad.get(slot, set())
            ]
            if not precios_slot:
                return None
            costes_minimos[slot] = min(precios_slot)
        return round(costes_minimos["chasis"] + costes_minimos["motor"] + costes_minimos["ruedas"], 2)

    def _estimar_utilidad_esperada_compra(
        self,
        valor_objetivo,
        valor_combinacion,
        valor_q,
        valor_futuro,
        estrategia_compra,
    ):
        perfil = self._perfil_estrategia_compra(estrategia_compra)
        utilidad_inmediata = (
            (perfil["peso_rendimiento"] * 0.60 * valor_objetivo)
            + (perfil["peso_combinacion"] * 0.85 * valor_combinacion)
            + (perfil["peso_q"] * valor_q)
        )
        utilidad_futura = (
            0.38 * valor_futuro
            + 0.20 * valor_q
            + 0.12 * valor_combinacion
            + 0.30 * valor_objetivo
        )
        utilidad_total = utilidad_inmediata + (0.28 * utilidad_futura)
        return {
            "utilidad_inmediata": utilidad_inmediata,
            "utilidad_futura": utilidad_futura,
            "utilidad_total": utilidad_total,
        }

    def construir_estado_compra(self, catalogo_vendedores, presupuesto_max, contratos_activos=None, historial_resultados_anteriores=None):
        if contratos_activos is None:
            contratos_activos = []
        if historial_resultados_anteriores is None:
            historial_resultados_anteriores = []

        precios_actuales = {
            vendedor: {
                "chasis": datos["precios"]["chasis"],
                "motor": datos["precios"]["motor"],
                "ruedas": datos["precios"]["ruedas"],
            }
            for vendedor, datos in catalogo_vendedores.items()
        }

        calidad_piezas = {
            vendedor: {
                "chasis": datos["chasis"],
                "motor": datos["motor"],
                "ruedas": datos["ruedas"],
            }
            for vendedor, datos in catalogo_vendedores.items()
        }

        return {
            "precios_actuales": precios_actuales,
            "calidad_piezas": calidad_piezas,
            "contratos_activos": list(contratos_activos),
            "presupuesto_disponible": presupuesto_max,
            "historial_resultados_anteriores": historial_resultados_anteriores + self.historial_resultados[-5:],
            "rendimiento_combinaciones_pasadas": dict(self.rendimiento_combinaciones),
        }

    def elegir_componentes_q(
        self,
        catalogo_vendedores,
        presupuesto_max=1000.0,
        bloqueos_exclusividad=None,
        contratos_activos=None,
        historial_resultados_anteriores=None,
        estado_q=None,
        estrategia_compra=None,
        nivel_exploracion=0.1,
        carrera_actual=1,
        total_carreras=10,
    ):
        if bloqueos_exclusividad is None:
            bloqueos_exclusividad = {}
        if contratos_activos is None:
            contratos_activos = []

        perfil_arranque = sum(ord(caracter) for caracter in self.nombre) % 4
        objetivos_presupuesto_arranque = [0.18, 0.26, 0.34, 0.42]
        objetivos_calidad_arranque = [0.26, 0.34, 0.42, 0.50]
        objetivo_presupuesto_rel = objetivos_presupuesto_arranque[perfil_arranque]
        objetivo_calidad_rel = objetivos_calidad_arranque[perfil_arranque]

        umbral_top_calidad = {}
        for slot in ["chasis", "motor", "ruedas"]:
            calidades = sorted((datos[slot] for datos in catalogo_vendedores.values()), reverse=True)
            umbral_top_calidad[slot] = calidades[1] if len(calidades) > 1 else (calidades[0] if calidades else 0.0)

        contratos_por_slot = {
            contrato["slot"]: contrato["vendedor"]
            for contrato in contratos_activos
            if contrato.get("piloto") == self.nombre
        }

        estado = self.construir_estado_compra(
            catalogo_vendedores,
            presupuesto_max,
            contratos_activos=contratos_activos,
            historial_resultados_anteriores=historial_resultados_anteriores,
        )
        if estrategia_compra is None:
            estrategia_compra = self._seleccionar_estrategia_compra(estado)
        perfil_estrategia = self._perfil_estrategia_compra(estrategia_compra)
        segmento_presupuesto = self._segmento_presupuesto(estado["presupuesto_disponible"])
        estrategia_segmento = self.memoria["estrategia_presupuesto"][segmento_presupuesto]
        carreras_restantes = max(0, total_carreras - carrera_actual)
        coste_minimo_kart = self._coste_minimo_kart_actual(catalogo_vendedores, bloqueos_exclusividad)
        presupuesto_objetivo_futuro = (
            0.0 if coste_minimo_kart is None else (carreras_restantes * coste_minimo_kart)
        )

        # Si el presupuesto no alcanza el coste mínimo, seguiremos buscando alternativas
        # más baratas en el loop de combinaciones (no nos 'plantamos' en el sentido de saltar la compra).

        combinaciones_validas = []
        combinaciones_disponibles = []
        vendedores_disponibles = sorted(catalogo_vendedores.keys())
        
        for v_ch in vendedores_disponibles:
            for v_mo in vendedores_disponibles:
                for v_ru in vendedores_disponibles:
                    if v_ch in bloqueos_exclusividad.get("chasis", set()):
                        continue
                    if v_mo in bloqueos_exclusividad.get("motor", set()):
                        continue
                    if v_ru in bloqueos_exclusividad.get("ruedas", set()):
                        continue

                    p_ch = catalogo_vendedores[v_ch]["precios"]["chasis"]
                    p_mo = catalogo_vendedores[v_mo]["precios"]["motor"]
                    p_ru = catalogo_vendedores[v_ru]["precios"]["ruedas"]
                    
                    componentes = [
                        {"slot": "chasis", "vendedor": v_ch, "precio": p_ch},
                        {"slot": "motor", "vendedor": v_mo, "precio": p_mo},
                        {"slot": "ruedas", "vendedor": v_ru, "precio": p_ru},
                    ]

                    precio_total = calcular_coste_bruto(componentes)
                    gasto_imputable = calcular_coste_imputable(componentes, contratos_activos)
                    
                    cal_ch = catalogo_vendedores[v_ch]["chasis"]
                    cal_mo = catalogo_vendedores[v_mo]["motor"]
                    cal_ru = catalogo_vendedores[v_ru]["ruedas"]
                    calidad_total = cal_ch + cal_mo + cal_ru
                    
                    eficiencia_mercado = calidad_total / (precio_total if precio_total > 0 else 1)
                    
                    valor_combo_pasado_raw = estado["rendimiento_combinaciones_pasadas"].get(f"{v_ch},{v_mo},{v_ru}", 0.0)
                    if isinstance(valor_combo_pasado_raw, dict):
                        valor_combo_pasado = float(valor_combo_pasado_raw.get("media", 0.0))
                    else:
                        valor_combo_pasado = float(valor_combo_pasado_raw)
                    pos_combo = self.memoria["combos_posicion"].get(f"{v_ch},{v_mo},{v_ru}", {"media": 3.0})
                    bonus_posicion_combo = (4.0 - pos_combo["media"]) / 3.0

                    eq_v_ch = self.memoria["equilibrio_vendedor"].get(v_ch, {"media": 0.0})["media"]
                    eq_v_mo = self.memoria["equilibrio_vendedor"].get(v_mo, {"media": 0.0})["media"]
                    eq_v_ru = self.memoria["equilibrio_vendedor"].get(v_ru, {"media": 0.0})["media"]
                    bonus_equilibrio_vendedor = (eq_v_ch + eq_v_mo + eq_v_ru) / 3.0

                    n_ch = self.memoria["equilibrio_vendedor"].get(v_ch, {"n": 0}).get("n", 0)
                    n_mo = self.memoria["equilibrio_vendedor"].get(v_mo, {"n": 0}).get("n", 0)
                    n_ru = self.memoria["equilibrio_vendedor"].get(v_ru, {"n": 0}).get("n", 0)
                    estabilidad_proveedor = min(1.0, (n_ch + n_mo + n_ru) / 24.0)

                    b_ch = self.memoria["bloqueos_frecuentes"]["chasis"].get(v_ch, 0)
                    b_mo = self.memoria["bloqueos_frecuentes"]["motor"].get(v_mo, 0)
                    b_ru = self.memoria["bloqueos_frecuentes"]["ruedas"].get(v_ru, 0)
                    riesgo_exclusividad = min(1.0, (b_ch + b_mo + b_ru) / 15.0)

                    sinergia_historial = max(
                        -1.0,
                        min(
                            1.5,
                            (0.45 * bonus_posicion_combo)
                            + (0.35 * bonus_equilibrio_vendedor)
                            + (0.20 * (valor_combo_pasado / 8.0)),
                        ),
                    )

                    # Tendencia de precios: penalizamos combos cuyos vendedores hayan subido precios
                    tendencia = self.memoria.get("tendencia_precios", {})
                    def pct_subida(vendor, slot):
                        hist = tendencia.get(vendor, {}).get(slot, [])
                        if len(hist) >= 2 and hist[0] > 0:
                            return (hist[-1] - hist[0]) / max(1.0, hist[0])
                        return 0.0
                    subida_media = (
                        pct_subida(v_ch, "chasis") + pct_subida(v_mo, "motor") + pct_subida(v_ru, "ruedas")
                    ) / 3.0


                    puntos_esperados_ajustados = (eficiencia_mercado * 3.5) * (0.8 + estrategia_segmento["preferencia_rendimiento"])
                    control_gasto_ajustado = gasto_imputable * (1.0 + (estrategia_segmento["preferencia_ahorro"] - 0.5) * 0.3)

                    valor_objetivo = self.funcion_objetivo_compra(
                        puntos_esperados=puntos_esperados_ajustados,
                        gasto_imputable=control_gasto_ajustado,
                        presupuesto_max=estado["presupuesto_disponible"],
                        valor_largo_plazo=valor_combo_pasado,
                        estrategia=estrategia_compra,
                    )

                    # Funcion de valor para decidir combinaciones con memoria util.
                    valor_combinacion = self.funcion_valor_combinacion(
                        calidad_total=calidad_total,
                        precio_total=precio_total,
                        gasto_imputable=gasto_imputable,
                        estabilidad_proveedor=estabilidad_proveedor,
                        riesgo_exclusividad=riesgo_exclusividad,
                        sinergia_historial=sinergia_historial,
                        presupuesto_max=estado["presupuesto_disponible"],
                    )
                    combo_key = f"{v_ch},{v_mo},{v_ru}"
                    valor_q = 0.0 if estado_q is None else self.obtener_valor_q(estado_q, combo_key, contexto="compra")
                    valor_futuro = (
                        (0.40 * valor_combo_pasado)
                        + (0.35 * estabilidad_proveedor)
                        + (0.15 * (1.0 - riesgo_exclusividad))
                        + (0.10 * sinergia_historial)
                    )
                    contratos_usados = sum(
                        1
                        for slot, vendedor in (("chasis", v_ch), ("motor", v_mo), ("ruedas", v_ru))
                        if contratos_por_slot.get(slot) == vendedor
                    )
                    plan = self._estimar_utilidad_esperada_compra(
                        valor_objetivo=valor_objetivo,
                        valor_combinacion=valor_combinacion,
                        valor_q=valor_q,
                        valor_futuro=valor_futuro,
                        estrategia_compra=estrategia_compra,
                    )
                    saldo_post_compra = presupuesto_max - gasto_imputable
                    if presupuesto_objetivo_futuro <= 0:
                        cobertura_futura = 1.0
                        deficit_futuro = 0.0
                    else:
                        cobertura_futura = max(0.0, min(1.0, saldo_post_compra / presupuesto_objetivo_futuro))
                        deficit_futuro = max(0.0, presupuesto_objetivo_futuro - saldo_post_compra)

                    penalizacion_sostenibilidad = 0.0
                    if coste_minimo_kart and deficit_futuro > 0:
                        penalizacion_sostenibilidad = (deficit_futuro / max(1.0, coste_minimo_kart)) * 0.90

                    bonus_sostenibilidad = 0.18 * cobertura_futura
                    info_combo = self.memoria.get("combos_posicion", {}).get(combo_key, {"n": 0, "media": 3.0, "ultimo": 3})
                    uso_combo = info_combo.get("n", 0)
                    media_pos_combo = info_combo.get("media", 3.0)
                    ultima_pos_combo = info_combo.get("ultimo", media_pos_combo)
                    penalizacion_repeticion = 0.0
                    if ultima_pos_combo > 10.0:
                        penalizacion_repeticion += 0.65
                    elif ultima_pos_combo > 5.0:
                        penalizacion_repeticion += 0.30

                    if uso_combo >= 2 and media_pos_combo > 10.0:
                        penalizacion_repeticion += 0.12 * min(4, uso_combo - 1) * min(1.0, (media_pos_combo - 10.0) / 10.0)
                    puntuacion_final = (
                        plan["utilidad_total"]
                        + (0.12 * contratos_usados)
                        + bonus_sostenibilidad
                        - penalizacion_sostenibilidad
                        - (0.5 * max(0.0, subida_media))
                        - penalizacion_repeticion
                    )

                    if carrera_actual == 1:
                        precio_relativo = precio_total / max(1.0, presupuesto_max)
                        calidad_relativa = calidad_total / 30.0
                        ajuste_presupuesto = max(0.0, 1.0 - (abs(precio_relativo - objetivo_presupuesto_rel) / 0.16))
                        ajuste_calidad = max(0.0, 1.0 - (abs(calidad_relativa - objetivo_calidad_rel) / 0.14))
                        piezas_top = sum(
                            1
                            for slot, vendedor in (("chasis", v_ch), ("motor", v_mo), ("ruedas", v_ru))
                            if catalogo_vendedores[vendedor][slot] >= umbral_top_calidad[slot]
                        )
                        puntuacion_final += (0.60 * ajuste_presupuesto) + (0.35 * ajuste_calidad) - (0.30 * piezas_top)
                        if precio_relativo <= 0.32:
                            puntuacion_final += 0.12
                        if precio_relativo >= 0.48:
                            puntuacion_final -= 0.18

                    if gasto_imputable <= presupuesto_max:
                        combinaciones_validas.append({
                            "key": combo_key,
                            "v_ch": v_ch, "v_mo": v_mo, "v_ru": v_ru,
                            "puntuacion": puntuacion_final, "precio": precio_total, "gasto_imputable": gasto_imputable,
                            "calidad_total": calidad_total,
                            "valor_calidad_precio": calidad_total / max(1.0, gasto_imputable),
                            "contratos_usados": contratos_usados,
                            "valor_q": valor_q,
                            "utilidad_inmediata": plan["utilidad_inmediata"],
                            "utilidad_futura": plan["utilidad_futura"],
                            "utilidad_total": plan["utilidad_total"],
                            "cobertura_futura": cobertura_futura,
                            "deficit_futuro": deficit_futuro,
                        })

                    combinaciones_disponibles.append({
                        "key": combo_key,
                        "v_ch": v_ch, "v_mo": v_mo, "v_ru": v_ru,
                        "puntuacion": puntuacion_final, "precio": precio_total, "gasto_imputable": gasto_imputable,
                        "calidad_total": calidad_total,
                        "valor_calidad_precio": calidad_total / max(1.0, gasto_imputable),
                        "contratos_usados": contratos_usados,
                        "valor_q": valor_q,
                        "utilidad_inmediata": plan["utilidad_inmediata"],
                        "utilidad_futura": plan["utilidad_futura"],
                        "utilidad_total": plan["utilidad_total"],
                        "cobertura_futura": cobertura_futura,
                        "deficit_futuro": deficit_futuro,
                    })

        if combinaciones_validas:
            # Penalizamos combos sobrepreciados cuando existe una alternativa claramente mejor en valor:
            # al menos 20% más barata y con una perdida de calidad muy pequena.
            for combo in combinaciones_validas:
                dominantes_valor = 0
                for alternativa in combinaciones_validas:
                    if alternativa["key"] == combo["key"]:
                        continue
                    ahorro_relativo = 1.0 - (alternativa["gasto_imputable"] / max(1.0, combo["gasto_imputable"]))
                    perdida_calidad = combo["calidad_total"] - alternativa["calidad_total"]
                    if ahorro_relativo >= 0.20 and perdida_calidad <= 1.5:
                        dominantes_valor += 1

                if dominantes_valor > 0:
                    combo["puntuacion"] -= min(1.8, 0.55 * dominantes_valor)

        if not combinaciones_validas:
            if combinaciones_disponibles:
                # Preferimos alternativas con menor gasto y menor tendencia alcista de sus vendedores
                tendencia = self.memoria.get("tendencia_precios", {})
                def tendencia_combo(c):
                    vch, vmo, vru = c["v_ch"], c["v_mo"], c["v_ru"]
                    def pct_sub(v, s):
                        hist = tendencia.get(v, {}).get(s, [])
                        if len(hist) >= 2 and hist[0] > 0:
                            return (hist[-1] - hist[0]) / max(1.0, hist[0])
                        return 0.0
                    return (pct_sub(vch, "chasis") + pct_sub(vmo, "motor") + pct_sub(vru, "ruedas")) / 3.0

                alternativa = min(
                    combinaciones_disponibles,
                    key=lambda x: (tendencia_combo(x), x["gasto_imputable"], x["precio"]),
                )
                razon = (
                    "⚠️ [Ajuste de emergencia] Sin combinación dentro de presupuesto; "
                    f"se elige la alternativa que mejor reutiliza contratos y menos coste imputable tiene ({alternativa['contratos_usados']} contrato(s), {round(alternativa['gasto_imputable'], 2)}€ imputable, {round(alternativa['precio'], 2)}€ bruto)."
                )
                return EleccionKart(f"[{estrategia_compra}] {razon}", alternativa["v_ch"], alternativa["v_mo"], alternativa["v_ru"])

            vendedor_respaldo = next(iter(sorted(catalogo_vendedores.keys())), "A")
            return EleccionKart(
                f"[{estrategia_compra}] Mercado bloqueado por exclusividades. Sin proveedores disponibles.",
                vendedor_respaldo,
                vendedor_respaldo,
                vendedor_respaldo,
            )

        combinaciones_ordenadas = sorted(combinaciones_validas, key=lambda x: x["puntuacion"], reverse=True)
        mejor_opcion_absoluta = combinaciones_ordenadas[0]

        def puntuacion_exploracion(combo):
            uso_combo = self.memoria.get("combos_posicion", {}).get(combo["key"], {"n": 0}).get("n", 0)
            novedad = 1.0 / (1.0 + uso_combo)
            cobertura = combo.get("cobertura_futura", 0.0)
            deficit = combo.get("deficit_futuro", 0.0)
            return (
                combo["puntuacion"]
                + (0.24 * novedad)
                + (0.05 * cobertura)
                - (0.03 * min(deficit, estado["presupuesto_disponible"]) / max(1.0, estado["presupuesto_disponible"]))
            )

        limite = min(10 if carrera_actual == 1 else 5, len(combinaciones_ordenadas))
        candidatas_exploracion = combinaciones_ordenadas[:limite]
        elegida = max(candidatas_exploracion, key=puntuacion_exploracion)

        if elegida["key"] == mejor_opcion_absoluta["key"]:
            tipo_decision = "🧠 [Selección Estable] Se elige la mejor utilidad esperada ajustada por memoria."
        else:
            tipo_decision = "🔬 [Exploración Guiada] Se prioriza una alternativa con novedad y mejor cobertura futura."

        razon = (
            f"[{estrategia_compra}] {tipo_decision} "
            f"utilidad esperada {round(elegida['utilidad_total'], 3)} "
            f"(inmediata {round(elegida['utilidad_inmediata'], 3)} | futura {round(elegida['utilidad_futura'], 3)}) "
            f"Gasto bruto: {round(elegida['precio'], 2)}€ | coste economico: {round(elegida['gasto_imputable'], 2)}€ "
            f"| cobertura futura: {round(elegida.get('cobertura_futura', 1.0) * 100, 1)}%"
        )
        return EleccionKart(razon, elegida["v_ch"], elegida["v_mo"], elegida["v_ru"])

    def aprender_de_resultado_rendimiento(self, elecciones_hechas, rendimiento_pista, media_parrilla, posicion_podio, gasto_economico=None, presupuesto_disponible=None):
        """Implementa tu nueva norma estricta de castigos y recompensas por podio."""
        
        # Guardamos en el historial para mantener la métrica de evolución propia
        self.historico_rendimientos.append(rendimiento_pista)

        v_ch = elecciones_hechas["chasis"]
        v_mo = elecciones_hechas["motor"]
        v_ru = elecciones_hechas["ruedas"]
        combo_key = f"{v_ch},{v_mo},{v_ru}"

        stats_combo = self.rendimiento_combinaciones.get(combo_key, {"media": 0.0, "n": 0})
        nuevo_n = stats_combo["n"] + 1
        nueva_media = stats_combo["media"] + ((rendimiento_pista - stats_combo["media"]) / nuevo_n)
        self.rendimiento_combinaciones[combo_key] = {"media": round(nueva_media, 4), "n": nuevo_n}
        stats_pos_combo = self.memoria["combos_posicion"].get(combo_key, {"media": 3.0, "n": 0})
        nuevo_n_pos = stats_pos_combo["n"] + 1
        nueva_media_pos = stats_pos_combo["media"] + ((posicion_podio - stats_pos_combo["media"]) / nuevo_n_pos)
        self.memoria["combos_posicion"][combo_key] = {"media": round(nueva_media_pos, 4), "n": nuevo_n_pos, "ultimo": posicion_podio}

        for vendedor in [v_ch, v_mo, v_ru]:
            stats_eq = self.memoria["equilibrio_vendedor"].get(vendedor, {"media": 0.0, "n": 0})
            nuevo_n_eq = stats_eq["n"] + 1
            score_equilibrio = (rendimiento_pista / max(1.0, posicion_podio))
            nueva_media_eq = stats_eq["media"] + ((score_equilibrio - stats_eq["media"]) / nuevo_n_eq)
            self.memoria["equilibrio_vendedor"][vendedor] = {"media": round(nueva_media_eq, 4), "n": nuevo_n_eq}

        if gasto_economico is not None and presupuesto_disponible is not None and presupuesto_disponible > 0:
            segmento = self._segmento_presupuesto(presupuesto_disponible)
            estrategia = self.memoria["estrategia_presupuesto"][segmento]
            ratio_gasto = gasto_economico / presupuesto_disponible
            exito_ahorro = 1.0 if ratio_gasto <= 0.85 else 0.0
            exito_rendimiento = 1.0 if posicion_podio == 1 else (0.5 if posicion_podio == 2 else 0.0)

            estrategia["n"] += 1
            estrategia["preferencia_ahorro"] = round(estrategia["preferencia_ahorro"] * 0.85 + exito_ahorro * 0.15, 4)
            estrategia["preferencia_rendimiento"] = round(estrategia["preferencia_rendimiento"] * 0.85 + exito_rendimiento * 0.15, 4)
        self.historial_resultados.append(
            {
                "posicion": posicion_podio,
                "rendimiento": round(rendimiento_pista, 4),
                "media_parrilla": round(media_parrilla, 4),
                "combinacion": combo_key,
            }
        )

        # Actualizamos corto plazo con el último rendimiento y contratos
        corto = self.memoria.get("corto_plazo", {})
        corto["ultimo_rendimiento"] = round(rendimiento_pista, 4)
        ultimo_obs = self.memoria.get("ultima_observacion", {})
        corto["ultimo_contrato"] = ultimo_obs.get("contratos_activos", [])
        self.memoria["corto_plazo"] = corto

        accion_reciente = self.historial_acciones[-1] if self.historial_acciones else {}
        estrategia_actual = accion_reciente.get("estrategia_compra", "equilibrada")
        stats_estrategia = self.memoria["estrategias_compra"].get(estrategia_actual, {"media": 0.0, "n": 0})
        nuevo_n_estrategia = stats_estrategia["n"] + 1
        score_estrategia = 1.0 if posicion_podio == 1 else (0.3 if posicion_podio == 2 else (-1.2 if posicion_podio > 10 else -0.8))
        nueva_media_estrategia = stats_estrategia["media"] + ((score_estrategia - stats_estrategia["media"]) / nuevo_n_estrategia)
        self.memoria["estrategias_compra"][estrategia_actual] = {"media": round(nueva_media_estrategia, 4), "n": nuevo_n_estrategia}

        evaluacion = self._evaluar_post_ronda_compra(
            elecciones_hechas=elecciones_hechas,
            rendimiento_pista=rendimiento_pista,
            media_parrilla=media_parrilla,
            posicion_podio=posicion_podio,
            gasto_economico=gasto_economico,
            presupuesto_disponible=presupuesto_disponible,
        )
        self.memoria["ultima_evaluacion_post_ronda"] = evaluacion
        
        # --- TU NUEVA REGLA DE PODIO DE AGENTES ---
        if posicion_podio == 1:
            # 1º Puesto: Recompensa positiva contundente para afianzar las piezas
            recompensa = 8.0  
        elif posicion_podio == 2:
            # 2º Puesto: TOTALMENTE NEUTRO. No altera los valores Q de la memoria.
            return  
        else:
            # 3º Puesto: Castigo competitivo severo para forzar la devaluación del setup
            recompensa = -6.0  

        # Al tener un alpha bajo (0.15), los cambios son más suaves y estables en el tiempo
        self.q_chasis[v_ch] = self.q_chasis[v_ch] + self.alpha * (recompensa - self.q_chasis[v_ch])
        self.q_motor[v_mo] = self.q_motor[v_mo] + self.alpha * (recompensa - self.q_motor[v_mo])
        self.q_ruedas[v_ru] = self.q_ruedas[v_ru] + self.alpha * (recompensa - self.q_ruedas[v_ru])
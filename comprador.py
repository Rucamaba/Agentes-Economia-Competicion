import random
import math

class EleccionKart:
    def __init__(self, razonamiento, vendedor_chasis, seller_motor, vendedor_ruedas):
        self.razonamiento = razonamiento
        self.vendedor_chasis = vendedor_chasis
        self.vendedor_motor = seller_motor
        self.vendedor_ruedas = vendedor_ruedas

class AgenteComprador:
    def __init__(self, nombre):
        self.nombre = nombre
        # --- MEMORIA A LARGO PLAZO ---
        # Bajamos alpha a 0.15 para que recuerden los éxitos pasados y no tengan amnesia
        self.alpha = 0.15  
        self.temperatura = 0.7  # Un pelo más frío para consolidar los setups campeones
        
        self.q_chasis = {"A": 0.0, "B": 0.0, "C": 0.0}
        self.q_motor = {"A": 0.0, "B": 0.0, "C": 0.0}
        self.q_ruedas = {"A": 0.0, "B": 0.0, "C": 0.0}
        
        self.historico_rendimientos = []

    def elegir_componentes_q(self, catalogo_vendedores):
        combinaciones_validas = []
        
        for v_ch in ["A", "B", "C"]:
            for v_mo in ["A", "B", "C"]:
                for v_ru in ["A", "B", "C"]:
                    p_ch = catalogo_vendedores[v_ch]["precios"]["chasis"]
                    p_mo = catalogo_vendedores[v_mo]["precios"]["motor"]
                    p_ru = catalogo_vendedores[v_ru]["precios"]["ruedas"]
                    
                    precio_total = p_ch + p_mo + p_ru
                    
                    if precio_total <= 100.0:
                        cal_ch = catalogo_vendedores[v_ch]["chasis"]
                        cal_mo = catalogo_vendedores[v_mo]["motor"]
                        cal_ru = catalogo_vendedores[v_ru]["ruedas"]
                        calidad_total = cal_ch + cal_mo + cal_ru
                        
                        eficiencia_mercado = calidad_total / (precio_total if precio_total > 0 else 1)
                        
                        experiencia_acumulada = (
                            self.q_chasis[v_ch] + 
                            self.q_motor[v_mo] + 
                            self.q_ruedas[v_ru]
                        )
                        
                        # Equilibrio de pesos: Eficiencia del día + Sabiduría histórica
                        puntuacion_final = (eficiencia_mercado * 3.5) + experiencia_acumulada
                        
                        combinaciones_validas.append({
                            "key": f"{v_ch},{v_mo},{v_ru}",
                            "v_ch": v_ch, "v_mo": v_mo, "v_ru": v_ru,
                            "puntuacion": puntuacion_final, "precio": precio_total
                        })

        if not combinaciones_validas:
            return EleccionKart("Mercado inflado de emergencia", "B", "B", "B")

        try:
            exp_valores = [math.exp(c["puntuacion"] / self.temperatura) for c in combinaciones_validas]
        except OverflowError:
            exp_valores = [math.exp(700 / self.temperatura) for _ in combinaciones_validas]
            
        suma_exp = sum(exp_valores)
        probabilidades = [ev / suma_exp for ev in exp_valores]

        elegida = random.choices(combinaciones_validas, weights=probabilidades, k=1)[0]
        
        mejor_opcion_absoluta = max(combinaciones_validas, key=lambda x: x["puntuacion"])
        if elegida["key"] == mejor_opcion_absoluta["key"]:
            tipo_decision = "🧠 [Explotación Óptima] Rendimiento/Precio maximizado al límite."
        else:
            tipo_decision = "🔬 [Exploración Ponderada] Buscando mejora marginal inteligente."

        razon = f"{tipo_decision} Gasto: {round(elegida['precio'], 2)}€"
        return EleccionKart(razon, elegida["v_ch"], elegida["v_mo"], elegida["v_ru"])

    def aprender_de_resultado_rendimiento(self, elecciones_hechas, rendimiento_pista, media_parrilla, posicion_podio):
        """Implementa tu nueva norma estricta de castigos y recompensas por podio."""
        
        # Guardamos en el historial para mantener la métrica de evolución propia
        self.historico_rendimientos.append(rendimiento_pista)
        
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

        v_ch = elecciones_hechas["chasis"]
        v_mo = elecciones_hechas["motor"]
        v_ru = elecciones_hechas["ruedas"]

        # Al tener un alpha bajo (0.15), los cambios son más suaves y estables en el tiempo
        self.q_chasis[v_ch] = self.q_chasis[v_ch] + self.alpha * (recompensa - self.q_chasis[v_ch])
        self.q_motor[v_mo] = self.q_motor[v_mo] + self.alpha * (recompensa - self.q_motor[v_mo])
        self.q_ruedas[v_ru] = self.q_ruedas[v_ru] + self.alpha * (recompensa - self.q_ruedas[v_ru])
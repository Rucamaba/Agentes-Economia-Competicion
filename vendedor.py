import random

class DecisionVendedor:
    def __init__(self, variacion_chasis, variacion_motor, variacion_ruedas, razonamiento):
        self.variacion_chasis = variacion_chasis
        self.variacion_motor = variacion_motor
        self.variacion_ruedas = variacion_ruedas
        self.razonamiento = razonamiento

class AgenteVendedor:
    def __init__(self, letra):
        self.letra = letra
        self.sensibilidad_precio = random.uniform(0.06, 0.12)

    def decidir_variacion_q(self, demandas_ultimas, uso_ganador, cuota_mercado_ultima):
        variaciones = {}
        razonamientos = []
        
        # El pánico global por marginación absoluta (<15% de ingresos totales) se mantiene como salvaguarda
        guerra_de_precios_global = cuota_mercado_ultima < 15.0 and cuota_mercado_ultima >= 0.0
        
        for slot in ["chasis", "motor", "ruedas"]:
            demanda_pieza = demandas_ultimas[slot][self.letra]
            pieza_fue_ganadora = uso_ganador[slot] == self.letra
            
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
                # Equilibrio competitivo (1 comprador): Ajuste leve orgánico
                variaciones[slot] = random.uniform(-0.02, 0.02)
                razonamientos.append(f"{slot}: Posición estable")

        return DecisionVendedor(
            variacion_chasis=variaciones["chasis"],
            variacion_motor=variaciones["motor"],
            variacion_ruedas=variaciones["ruedas"],
            razonamiento=f"Tienda {self.letra} -> " + " | ".join(razonamientos)
        )
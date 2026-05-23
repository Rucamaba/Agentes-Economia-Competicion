from abc import ABC, abstractmethod
import json


class AgenteBase(ABC):
    def __init__(self, nombre, parametros_aprendizaje=None):
        self.nombre = nombre
        self.memoria = {}
        self.historial_acciones = []
        self.historial_recompensas = []
        self.parametros_aprendizaje = parametros_aprendizaje or {}
        self.q_table = {}
        self.q_learning_rate = self.parametros_aprendizaje.get("alpha", 0.15)
        self.q_discount = self.parametros_aprendizaje.get("gamma", 0.0)

    @abstractmethod
    def observar(self, entorno):
        raise NotImplementedError

    @abstractmethod
    def decidir(self, observacion):
        raise NotImplementedError

    @abstractmethod
    def aprender(self, resultado):
        raise NotImplementedError

    def registrar_accion(self, accion):
        self.historial_acciones.append(accion)

    def registrar_recompensa(self, recompensa):
        self.historial_recompensas.append(recompensa)

    def _serializar_q(self, valor):
        if valor is None:
            return "∅"
        if isinstance(valor, dict):
            return json.dumps(
                {clave: self._serializar_q(contenido) for clave, contenido in sorted(valor.items())},
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        if isinstance(valor, (list, tuple)):
            return json.dumps([self._serializar_q(item) for item in valor], ensure_ascii=False, separators=(",", ":"))
        if isinstance(valor, set):
            return json.dumps(sorted(self._serializar_q(item) for item in valor), ensure_ascii=False, separators=(",", ":"))
        return str(valor)

    def _clave_q(self, estado, accion, contexto=""):
        return "|".join(
            [self._serializar_q(contexto), self._serializar_q(estado), self._serializar_q(accion)]
            if contexto
            else [self._serializar_q(estado), self._serializar_q(accion)]
        )

    def obtener_valor_q(self, estado, accion, contexto=""):
        return self.q_table.get(self._clave_q(estado, accion, contexto), 0.0)

    def _mejor_valor_siguiente(self, siguiente_estado, contexto=""):
        prefijo = f"{self._serializar_q(contexto)}|" if contexto else ""
        estado_serializado = self._serializar_q(siguiente_estado)
        prefijo_estado = f"{prefijo}{estado_serializado}|" if contexto else f"{estado_serializado}|"

        candidatos = [
            valor
            for clave, valor in self.q_table.items()
            if clave.startswith(prefijo_estado)
        ]
        return max(candidatos) if candidatos else 0.0

    def actualizar_q(self, estado, accion, recompensa, siguiente_estado=None, contexto=""):
        clave = self._clave_q(estado, accion, contexto)
        valor_actual = self.q_table.get(clave, 0.0)
        mejor_siguiente = 0.0 if siguiente_estado is None else self._mejor_valor_siguiente(siguiente_estado, contexto)
        objetivo = recompensa + (self.q_discount * mejor_siguiente)
        nuevo_valor = valor_actual + self.q_learning_rate * (objetivo - valor_actual)
        self.q_table[clave] = round(nuevo_valor, 4)
        return self.q_table[clave]

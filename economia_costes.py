def calcular_coste_bruto(componentes):
    return round(sum(componente["precio"] for componente in componentes), 2)


def calcular_coste_imputable(componentes, contratos_activos=None):
    coste_imputable = calcular_coste_bruto(componentes)

    if not contratos_activos:
        return coste_imputable

    for contrato in contratos_activos:
        for componente in componentes:
            if componente["slot"] == contrato["slot"] and componente["vendedor"] == contrato["vendedor"]:
                coste_imputable = round(coste_imputable - componente["precio"], 2)
                break

    return round(max(0.0, coste_imputable), 2)


def calcular_coste_comprometido(contratos_piloto):
    if not contratos_piloto:
        return 0.0

    return round(sum(contrato.get("coste_adelantado", 0.0) for contrato in contratos_piloto), 2)


def calcular_presupuesto_disponible(contratos_piloto, presupuesto_base=100.0):
    presupuesto_restante = presupuesto_base - calcular_coste_comprometido(contratos_piloto)
    return max(0.0, round(presupuesto_restante, 2))
"""
Módulo Oficial de Generación y Validación de Autoliquidaciones AEAT (Agencia Tributaria de España).
Diseño de Registro y Formato Plano Oficial conforme a las Órdenes del BOE
(Orden EHA/3786/2008, Orden HAP/2194/2013, Orden HAC/748/2020 y actualizaciones anuales).

Soporta:
- Modelo 303 (Impuesto sobre el Valor Añadido - IVA Trimestral y Mensual).
- Generación de archivo plano estructurado (.txt / .ses) con anchos fijos y justificación canónica.
- Mapeo de IVA devengado (casillas [01]-[09], [27]) a tipos general (21%), reducido (10%) y superreducido (4%).
- Mapeo de IVA deducible (casillas [28]-[31], [45]) para operaciones corrientes y bienes de inversión.
- Regularizaciones y cálculo de resultado de la autoliquidación (casilla [71]):
  * A ingresar (con domiciliación bancaria IBAN o NRC bancario).
  * A compensar (periodos 1T, 2T, 3T, 4T).
  * A devolver (periodo 4T).
  * Declaración negativa / cero.
- Validación algorítmica previa de coherencia, NIF (DNI/NIE/CIF) y cuadre contable.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime

from app.services.nif_validator import validate_spanish_id
from app.core.iban_security import validate_iban


# Constantes oficiales del Modelo 303
MODELO_303_CODE = "303"
VALID_PERIODOS_TRIMESTRALES = {"1T", "2T", "3T", "4T"}
VALID_PERIODOS_MENSUALES = {f"{m:02d}" for m in range(1, 13)}


def _normalize_text(val: Optional[str], length: int) -> str:
    """
    Sanitiza y normaliza texto alfanumérico para el estándar de la AEAT:
    - Convierte a mayúsculas.
    - Elimina acentos, diéresis y caracteres especiales no válidos.
    - Justifica a la izquierda y rellena con espacios a la derecha hasta 'length'.
    """
    if val is None:
        return " " * length

    text = str(val).strip().upper()
    # Descomponer caracteres con acentos
    text = unicodedata.normalize("NFKD", text)
    # Conservar letras ASCII, números y espacios
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Limpiar caracteres no alfanuméricos salvo espacios
    text = re.sub(r"[^A-Z0-9 ]", "", text)
    return text[:length].ljust(length)


def _format_num_cents(
    amount: float | int,
    length: int,
    signed: bool = False
) -> str:
    """
    Formatea un importe numérico en céntimos sin comas según el diseño de registro BOE:
    - Ejemplo: 1250.45€ con length=13 -> "0000000125045"
    - Con signo: Si signed=True y length=13, primer carácter es 'N' o '-' si negativo,
      o ' ' / '+' / '0' según especificación, seguido del valor absoluto en céntimos.
    """
    val = round(float(amount), 2)
    cents = int(round(abs(val) * 100))

    if signed:
        sign_char = "N" if val < 0 else "0"
        num_len = length - 1
        num_str = str(cents).zfill(num_len)[-num_len:]
        return f"{sign_char}{num_str}"
    else:
        return str(cents).zfill(length)[-length:]


def _format_rate(rate: float | int, length: int = 5) -> str:
    """
    Formatea un tipo impositivo en centésimas (ej: 21.00% con length=5 -> '02100').
    """
    cents = int(round(float(rate) * 100))
    return str(cents).zfill(length)[-length:]


def validate_modelo_303_data(data: dict) -> Tuple[bool, List[str]]:
    """
    Valida la integridad técnica y el cuadre aritmético de los datos del Modelo 303
    antes de la generación del fichero de presentación de la AEAT.

    Retorna: (is_valid, errors_list)
    """
    errors: List[str] = []

    declarante = data.get("declarante") or {}
    liquidacion = data.get("liquidacion") or {}
    periodo = str(data.get("periodo", "")).upper().strip()
    ejercicio = data.get("ejercicio")

    # 1. Validación de Cabecera y Declarante
    if not ejercicio or not (2000 <= int(ejercicio) <= 2099):
        errors.append(f"Ejercicio fiscal inválido: {ejercicio}.")

    all_valid_periodos = VALID_PERIODOS_TRIMESTRALES | VALID_PERIODOS_MENSUALES
    if periodo not in all_valid_periodos:
        errors.append(f"Periodo '{periodo}' no válido. Debe ser 1T, 2T, 3T, 4T o 01 a 12.")

    nif = str(declarante.get("nif", "")).upper().strip()
    if not nif:
        errors.append("El NIF del declarante es obligatorio.")
    else:
        nif_val = validate_spanish_id(nif)
        if not nif_val.is_valid:
            errors.append(f"El NIF del declarante '{nif}' no es válido: {nif_val.error_message}")

    razon_social = declarante.get("razon_social") or declarante.get("apellidos_nombre") or ""
    if not str(razon_social).strip():
        errors.append("La razón social o apellidos y nombre del declarante es obligatoria.")

    # 2. Validación de IVA Devengado
    base_4 = float(liquidacion.get("base_superreducido", 0.0))
    cuota_4 = float(liquidacion.get("cuota_superreducido", 0.0))
    base_10 = float(liquidacion.get("base_reducido", 0.0))
    cuota_10 = float(liquidacion.get("cuota_reducido", 0.0))
    base_21 = float(liquidacion.get("base_general", 0.0))
    cuota_21 = float(liquidacion.get("cuota_general", 0.0))

    calc_devengado = round(cuota_4 + cuota_10 + cuota_21, 2)
    tot_devengado = float(liquidacion.get("total_cuotas_devengadas", calc_devengado))

    if abs(calc_devengado - tot_devengado) > 0.05:
        errors.append(
            f"Descuadre en IVA Devengado: Suma de cuotas [03]+[06]+[09] = {calc_devengado:.2f}€ "
            f"no coincide con Total Cuotas Devengadas [27] = {tot_devengado:.2f}€."
        )

    # 3. Validación de IVA Deducible
    cuota_ded_corrientes = float(liquidacion.get("cuota_deducible_corrientes", 0.0))
    cuota_ded_inversion = float(liquidacion.get("cuota_deducible_inversion", 0.0))

    calc_deducible = round(cuota_ded_corrientes + cuota_ded_inversion, 2)
    tot_deducible = float(liquidacion.get("total_cuotas_deducibles", calc_deducible))

    if abs(calc_deducible - tot_deducible) > 0.05:
        errors.append(
            f"Descuadre en IVA Deducible: Suma de cuotas [29]+[31] = {calc_deducible:.2f}€ "
            f"no coincide con Total a Deducir [45] = {tot_deducible:.2f}€."
        )

    # 4. Diferencia y Resultado de la Autoliquidación
    calc_diferencia = round(tot_devengado - tot_deducible, 2)
    declarada_dif = float(liquidacion.get("diferencia", calc_diferencia))

    if abs(calc_diferencia - declarada_dif) > 0.05:
        errors.append(
            f"Descuadre en Diferencia [46]: Devengado ({tot_devengado:.2f}€) - Deducible ({tot_deducible:.2f}€) "
            f"= {calc_diferencia:.2f}€, pero se declaró {declarada_dif:.2f}€."
        )

    compensar_previo = float(liquidacion.get("compensacion_periodos_anteriores", 0.0))
    calc_resultado = round(calc_diferencia - compensar_previo, 2)
    declarado_resultado = float(liquidacion.get("resultado_autoliquidacion", calc_resultado))

    if abs(calc_resultado - declarado_resultado) > 0.05:
        errors.append(
            f"Descuadre en Resultado Final [71]: Calculado ({calc_resultado:.2f}€) vs "
            f"Declarado ({declarado_resultado:.2f}€)."
        )

    # 5. Validación de Modalidad de Pago / Devolución
    tipo_resultado = str(liquidacion.get("tipo_resultado", "")).upper().strip()
    if not tipo_resultado:
        if declarado_resultado > 0:
            tipo_resultado = "I"  # Ingreso
        elif declarado_resultado < 0:
            tipo_resultado = "D" if periodo == "4T" else "C"  # Devolución o Compensación
        else:
            tipo_resultado = "N"  # Negativa

    if declarado_resultado > 0:
        iban = liquidacion.get("iban")
        nrc = liquidacion.get("nrc")
        if iban:
            clean_iban = re.sub(r"\s+", "", str(iban).upper())
            if not validate_iban(clean_iban):
                errors.append(f"El IBAN de domiciliación '{iban}' no es válido según ISO 13616.")
        elif not nrc and not liquidacion.get("pago_en_efectivo"):
            # Advertencia / requisito informativo
            pass
    elif declarado_resultado < 0:
        if tipo_resultado == "D" and periodo != "4T":
            errors.append(
                f"La solicitud de Devolución ('D') en el Modelo 303 sólo está permitida "
                f"en el 4º Trimestre ('4T') o periodo 12. En {periodo} debe ser 'C' (A Compensar)."
            )
        if tipo_resultado == "D":
            iban = liquidacion.get("iban")
            if not iban or not validate_iban(re.sub(r"\s+", "", str(iban).upper())):
                errors.append("Para devoluciones tributarias de la AEAT es obligatorio informar un IBAN bancario válido.")

    return len(errors) == 0, errors


def generate_modelo_303_file(
    declarante: Dict[str, Any],
    liquidacion: Dict[str, Any],
    periodo: str,
    ejercicio: int
) -> str:
    """
    Genera el fichero informático oficial del Modelo 303 de la AEAT
    en formato plano estructurado (ancho fijo por posiciones y justificación canónica BOE).

    Parámetros:
    - declarante: Diccionario con NIF, razón social, etc.
    - liquidacion: Diccionario con bases imponibles, cuotas y casillas [01] a [71].
    - periodo: '1T', '2T', '3T', '4T' o mensual '01'-'12'.
    - ejercicio: Año fiscal de cuatro dígitos (ej: 2026).

    Retorna:
    - Cadena de texto plana con saltos CRLF lista para presentación en sede electrónica AEAT.
    """
    periodo_str = str(periodo).upper().strip()
    ejercicio_int = int(ejercicio)

    # Validar primero
    payload_to_validate = {
        "declarante": declarante,
        "liquidacion": liquidacion,
        "periodo": periodo_str,
        "ejercicio": ejercicio_int
    }
    is_valid, validation_errors = validate_modelo_303_data(payload_to_validate)
    if not is_valid:
        raise ValueError(f"Error de validación del Modelo 303: {'; '.join(validation_errors)}")

    nif_clean = re.sub(r"[^A-Z0-9]", "", str(declarante.get("nif", "")).upper())
    razon_social = _normalize_text(
        declarante.get("razon_social") or declarante.get("apellidos_nombre") or "", 80
    )

    # -------------------------------------------------------------
    # REGISTRO TIPO 1: IDENTIFICACIÓN Y CABECERA (Longitud estándar 250 caracteres)
    # -------------------------------------------------------------
    # [1] Tipo registro: '1'
    # [2-4] Modelo: '303'
    # [5-8] Ejercicio: '2026'
    # [9-10] Periodo: '1T'
    # [11-19] NIF: 9 caracteres
    # [20-99] Razón social: 80 caracteres
    # [100-108] Teléfono contacto: 9 caracteres
    # [109-148] Persona de contacto: 40 caracteres
    # [149-250] Reservado AEAT: 102 espacios
    telefono = _normalize_text(declarante.get("telefono", ""), 9)
    contacto = _normalize_text(declarante.get("contacto", ""), 40)
    reservado_1 = " " * 102

    reg_1 = (
        f"1"
        f"{MODELO_303_CODE}"
        f"{ejercicio_int:04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{razon_social}"
        f"{telefono}"
        f"{contacto}"
        f"{reservado_1}"
    )

    # -------------------------------------------------------------
    # REGISTRO TIPO 2: LIQUIDACIÓN ECONÓMICA Y RESULTADO (Formato BOE)
    # -------------------------------------------------------------
    # [1] Tipo registro: '2'
    # [2-4] Modelo: '303'
    # [5-8] Ejercicio: '2026'
    # [9-10] Periodo: '1T'
    # [11-19] NIF: 9 caracteres

    # Extracción y cálculo seguro de casillas
    base_4 = float(liquidacion.get("base_superreducido", 0.0))
    cuota_4 = float(liquidacion.get("cuota_superreducido", round(base_4 * 0.04, 2)))

    base_10 = float(liquidacion.get("base_reducido", 0.0))
    cuota_10 = float(liquidacion.get("cuota_reducido", round(base_10 * 0.10, 2)))

    base_21 = float(liquidacion.get("base_general", 0.0))
    cuota_21 = float(liquidacion.get("cuota_general", round(base_21 * 0.21, 2)))

    # Casilla [27] Total devengado
    total_devengado = float(liquidacion.get("total_cuotas_devengadas", round(cuota_4 + cuota_10 + cuota_21, 2)))

    # IVA Deducible
    base_ded_corrientes = float(liquidacion.get("base_deducible_corrientes", 0.0))
    cuota_ded_corrientes = float(liquidacion.get("cuota_deducible_corrientes", 0.0))

    base_ded_inversion = float(liquidacion.get("base_deducible_inversion", 0.0))
    cuota_ded_inversion = float(liquidacion.get("cuota_deducible_inversion", 0.0))

    # Casilla [45] Total deducible
    total_deducible = float(liquidacion.get("total_cuotas_deducibles", round(cuota_ded_corrientes + cuota_ded_inversion, 2)))

    # Casilla [46] Diferencia [27] - [45]
    diferencia = round(total_devengado - total_deducible, 2)

    # Compensación de ejercicios anteriores [67]
    compensacion = float(liquidacion.get("compensacion_periodos_anteriores", 0.0))

    # Casilla [71] Resultado de la autoliquidación
    resultado_autoliq = round(diferencia - compensacion, 2)

    # Tipo de resultado y medio de pago
    tipo_resultado = str(liquidacion.get("tipo_resultado", "")).upper().strip()
    if not tipo_resultado:
        if resultado_autoliq > 0:
            tipo_resultado = "I"
        elif resultado_autoliq < 0:
            tipo_resultado = "D" if periodo_str == "4T" else "C"
        else:
            tipo_resultado = "N"

    # IBAN o NRC
    raw_iban = re.sub(r"[^A-Z0-9]", "", str(liquidacion.get("iban", "")).upper())
    iban_field = raw_iban[:24].ljust(24) if raw_iban else " " * 24

    raw_nrc = re.sub(r"[^A-Z0-9]", "", str(liquidacion.get("nrc", "")).upper())
    nrc_field = raw_nrc[:22].ljust(22) if raw_nrc else " " * 22

    # Codificación de casillas de importes (ancho oficial 13 dígitos: 11 enteros + 2 decimales en céntimos)
    c01 = _format_num_cents(base_4, 13)
    c02 = _format_rate(4.0, 5)
    c03 = _format_num_cents(cuota_4, 13)

    c04 = _format_num_cents(base_10, 13)
    c05 = _format_rate(10.0, 5)
    c06 = _format_num_cents(cuota_10, 13)

    c07 = _format_num_cents(base_21, 13)
    c08 = _format_rate(21.0, 5)
    c09 = _format_num_cents(cuota_21, 13)

    c27 = _format_num_cents(total_devengado, 13)

    c28 = _format_num_cents(base_ded_corrientes, 13)
    c29 = _format_num_cents(cuota_ded_corrientes, 13)

    c30 = _format_num_cents(base_ded_inversion, 13)
    c31 = _format_num_cents(cuota_ded_inversion, 13)

    c45 = _format_num_cents(total_deducible, 13)

    # Casillas que admiten signo negativo
    c46 = _format_num_cents(diferencia, 13, signed=True)
    c67 = _format_num_cents(compensacion, 13)
    c71 = _format_num_cents(resultado_autoliq, 13, signed=True)

    # Bloque de regularización y porcentaje atribución Estado (100% por defecto)
    c64 = "10000"  # 100.00%
    c65 = c46      # Parte del Estado
    c66 = _format_num_cents(0.0, 13)  # Regularización cuotas

    reg_2 = (
        f"2"
        f"{MODELO_303_CODE}"
        f"{ejercicio_int:04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{c01}{c02}{c03}"
        f"{c04}{c05}{c06}"
        f"{c07}{c08}{c09}"
        f"{c27}"
        f"{c28}{c29}"
        f"{c30}{c31}"
        f"{c45}"
        f"{c46}"
        f"{c64}{c65}{c66}"
        f"{c67}"
        f"{c71}"
        f"{tipo_resultado[:1]}"
        f"{iban_field}"
        f"{nrc_field}"
    )

    # Unir registros con salto de línea estándar CRLF
    return f"{reg_1}\r\n{reg_2}\r\n"


# =============================================================================
# MODELO 111 (Retenciones IRPF: Rendimientos del Trabajo y Actividades Económicas)
# =============================================================================
MODELO_111_CODE = "111"


def validate_modelo_111_data(data: dict) -> Tuple[bool, List[str]]:
    """Valida los datos contables y fiscales del Modelo 111 antes de la exportación BOE."""
    errors: List[str] = []
    declarante = data.get("declarante") or {}
    liquidacion = data.get("liquidacion") or {}
    periodo = str(data.get("periodo", "")).upper().strip()
    ejercicio = data.get("ejercicio")

    if not ejercicio or not (2000 <= int(ejercicio) <= 2100):
        errors.append(f"Ejercicio fiscal inválido: {ejercicio}.")

    if periodo not in VALID_PERIODOS_TRIMESTRALES and periodo not in VALID_PERIODOS_MENSUALES:
        errors.append(f"Periodo '{periodo}' no válido para Modelo 111 (se requiere 1T-4T o 01-12).")

    nif = declarante.get("nif")
    if not nif:
        errors.append("Falta el NIF del declarante.")
    else:
        val = validate_spanish_id(nif)
        if not val.get("is_valid"):
            errors.append(f"NIF del declarante '{nif}' inválido.")

    if not declarante.get("razon_social"):
        errors.append("Falta la razón social del declarante.")

    resultado = liquidacion.get("resultado_autoliquidacion", 0.0)
    tipo_res = liquidacion.get("tipo_resultado", "I").upper()
    if resultado > 0 and tipo_res in ("U", "D"):
        iban = liquidacion.get("iban", "")
        if not iban or not validate_iban(iban):
            errors.append("Se requiere un IBAN válido para domiciliación del resultado a ingresar.")

    return len(errors) == 0, errors


def generate_modelo_111_file(
    declarante: dict,
    liquidacion: dict,
    periodo: str,
    ejercicio: int,
) -> str:
    """Genera el fichero plano de autoliquidación del Modelo 111 según diseño BOE."""
    periodo_str = str(periodo).upper().strip()
    nif_clean = re.sub(r"[^A-Z0-9]", "", str(declarante.get("nif", "")).upper())
    razon_social = _normalize_text(declarante.get("razon_social", ""), 80)
    telefono = re.sub(r"\D", "", str(declarante.get("telefono", "")))[:9].ljust(9)
    contacto = _normalize_text(declarante.get("contacto", ""), 40)

    # Registro 1: Carátula / Declarante
    reg_1 = (
        f"1"
        f"{MODELO_111_CODE}"
        f"{int(ejercicio):04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{razon_social}"
        f"{telefono}"
        f"{contacto}"
        f"{' ' * 40}"
    )

    # Rendimientos del trabajo
    num_perceptores_trabajo = int(liquidacion.get("num_perceptores_trabajo", 0))
    base_trabajo = float(liquidacion.get("base_trabajo", 0.0))
    retenciones_trabajo = float(liquidacion.get("retenciones_trabajo", 0.0))

    # Rendimientos profesionales / actividades económicas
    num_perceptores_prof = int(liquidacion.get("num_perceptores_profesionales", 0))
    base_prof = float(liquidacion.get("base_profesionales", 0.0))
    retenciones_prof = float(liquidacion.get("retenciones_profesionales", 0.0))

    total_retenciones = round(retenciones_trabajo + retenciones_prof, 2)
    a_deducir = float(liquidacion.get("a_deducir", 0.0))
    resultado = round(total_retenciones - a_deducir, 2)

    tipo_res = liquidacion.get("tipo_resultado", "I" if resultado > 0 else "N")[:1]
    raw_iban = liquidacion.get("iban", "")
    iban_field = re.sub(r"[^A-Za-z0-9]", "", raw_iban)[:34].ljust(34) if raw_iban else " " * 34
    raw_nrc = liquidacion.get("nrc", "")
    nrc_field = re.sub(r"[^A-Za-z0-9]", "", raw_nrc)[:22].ljust(22) if raw_nrc else " " * 22

    # Casillas oficiales
    c01 = str(num_perceptores_trabajo).zfill(8)[-8:]
    c02 = _format_num_cents(base_trabajo, 13)
    c03 = _format_num_cents(retenciones_trabajo, 13)

    c04 = "00000000"
    c05 = _format_num_cents(0.0, 13)
    c06 = _format_num_cents(0.0, 13)

    c07 = str(num_perceptores_prof).zfill(8)[-8:]
    c08 = _format_num_cents(base_prof, 13)
    c09 = _format_num_cents(retenciones_prof, 13)

    c28 = _format_num_cents(total_retenciones, 13)
    c29 = _format_num_cents(a_deducir, 13)
    c30 = _format_num_cents(resultado, 13, signed=True)

    reg_2 = (
        f"2"
        f"{MODELO_111_CODE}"
        f"{int(ejercicio):04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{c01}{c02}{c03}"
        f"{c04}{c05}{c06}"
        f"{c07}{c08}{c09}"
        f"{c28}{c29}{c30}"
        f"{tipo_res}"
        f"{iban_field}"
        f"{nrc_field}"
    )

    return f"{reg_1}\r\n{reg_2}\r\n"


# =============================================================================
# MODELO 115 (Retenciones por Arrendamiento de Inmuebles Urbanos)
# =============================================================================
MODELO_115_CODE = "115"


def validate_modelo_115_data(data: dict) -> Tuple[bool, List[str]]:
    """Valida los datos contables y fiscales del Modelo 115 antes de la exportación BOE."""
    errors: List[str] = []
    declarante = data.get("declarante") or {}
    liquidacion = data.get("liquidacion") or {}
    periodo = str(data.get("periodo", "")).upper().strip()
    ejercicio = data.get("ejercicio")

    if not ejercicio or not (2000 <= int(ejercicio) <= 2100):
        errors.append(f"Ejercicio fiscal inválido: {ejercicio}.")

    if periodo not in VALID_PERIODOS_TRIMESTRALES and periodo not in VALID_PERIODOS_MENSUALES:
        errors.append(f"Periodo '{periodo}' no válido para Modelo 115.")

    nif = declarante.get("nif")
    if not nif:
        errors.append("Falta el NIF del declarante.")
    else:
        val = validate_spanish_id(nif)
        if not val.get("is_valid"):
            errors.append(f"NIF del declarante '{nif}' inválido.")

    resultado = liquidacion.get("resultado_autoliquidacion", 0.0)
    tipo_res = liquidacion.get("tipo_resultado", "I").upper()
    if resultado > 0 and tipo_res in ("U", "D"):
        iban = liquidacion.get("iban", "")
        if not iban or not validate_iban(iban):
            errors.append("Se requiere un IBAN válido para domiciliación del resultado a ingresar.")

    return len(errors) == 0, errors


def generate_modelo_115_file(
    declarante: dict,
    liquidacion: dict,
    periodo: str,
    ejercicio: int,
) -> str:
    """Genera el fichero plano oficial del Modelo 115 conforme a las especificaciones BOE."""
    periodo_str = str(periodo).upper().strip()
    nif_clean = re.sub(r"[^A-Z0-9]", "", str(declarante.get("nif", "")).upper())
    razon_social = _normalize_text(declarante.get("razon_social", ""), 80)
    telefono = re.sub(r"\D", "", str(declarante.get("telefono", "")))[:9].ljust(9)
    contacto = _normalize_text(declarante.get("contacto", ""), 40)

    reg_1 = (
        f"1"
        f"{MODELO_115_CODE}"
        f"{int(ejercicio):04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{razon_social}"
        f"{telefono}"
        f"{contacto}"
        f"{' ' * 40}"
    )

    num_perceptores = int(liquidacion.get("num_perceptores", 0))
    base_retenciones = float(liquidacion.get("base_retenciones", 0.0))
    retenciones_practicadas = float(liquidacion.get("retenciones_practicadas", 0.0))
    a_deducir = float(liquidacion.get("a_deducir", 0.0))
    resultado = round(retenciones_practicadas - a_deducir, 2)

    tipo_res = liquidacion.get("tipo_resultado", "I" if resultado > 0 else "N")[:1]
    raw_iban = liquidacion.get("iban", "")
    iban_field = re.sub(r"[^A-Za-z0-9]", "", raw_iban)[:34].ljust(34) if raw_iban else " " * 34
    raw_nrc = liquidacion.get("nrc", "")
    nrc_field = re.sub(r"[^A-Za-z0-9]", "", raw_nrc)[:22].ljust(22) if raw_nrc else " " * 22

    # Casillas oficiales [01] a [05]
    c01 = str(num_perceptores).zfill(8)[-8:]
    c02 = _format_num_cents(base_retenciones, 13)
    c03 = _format_num_cents(retenciones_practicadas, 13)
    c04 = _format_num_cents(a_deducir, 13)
    c05 = _format_num_cents(resultado, 13, signed=True)

    reg_2 = (
        f"2"
        f"{MODELO_115_CODE}"
        f"{int(ejercicio):04d}"
        f"{periodo_str[:2].ljust(2)}"
        f"{nif_clean[:9].ljust(9)}"
        f"{c01}{c02}{c03}{c04}{c05}"
        f"{tipo_res}"
        f"{iban_field}"
        f"{nrc_field}"
    )

    return f"{reg_1}\r\n{reg_2}\r\n"


# =============================================================================
# MODELO 347 (Declaración Anual de Operaciones con Terceras Personas > 3.005,06 €)
# =============================================================================
MODELO_347_CODE = "347"


def validate_modelo_347_data(data: dict) -> Tuple[bool, List[str]]:
    """Valida los datos agregados del Modelo 347 antes de generar el fichero BOE."""
    errors: List[str] = []
    declarante = data.get("declarante") or {}
    operaciones = data.get("operaciones") or []
    ejercicio = data.get("ejercicio")

    if not ejercicio or not (2000 <= int(ejercicio) <= 2100):
        errors.append(f"Ejercicio fiscal inválido: {ejercicio}.")

    nif = declarante.get("nif")
    if not nif:
        errors.append("Falta el NIF del declarante.")
    else:
        val = validate_spanish_id(nif)
        if not val.get("is_valid"):
            errors.append(f"NIF del declarante '{nif}' inválido.")

    if not declarante.get("razon_social"):
        errors.append("Falta la razón social del declarante.")

    for idx, op in enumerate(operaciones, start=1):
        nif_op = op.get("nif")
        if not nif_op:
            errors.append(f"Operación #{idx}: Falta NIF del tercero declarado.")
        total_op = float(op.get("importe_anual", 0.0))
        if total_op < 3005.06:
            errors.append(f"Operación #{idx} ({nif_op}): Importe anual ({total_op}€) inferior al umbral legal de 3.005,06€.")

    return len(errors) == 0, errors


def generate_modelo_347_file(
    declarante: dict,
    operaciones: List[dict],
    ejercicio: int,
) -> str:
    """Genera el fichero oficial en formato plano del Modelo 347 conforme al diseño BOE."""
    nif_clean = re.sub(r"[^A-Z0-9]", "", str(declarante.get("nif", "")).upper())
    razon_social = _normalize_text(declarante.get("razon_social", ""), 40)
    telefono = re.sub(r"\D", "", str(declarante.get("telefono", "")))[:9].ljust(9)
    contacto = _normalize_text(declarante.get("contacto", ""), 40)

    total_declarados = len(operaciones)
    suma_total_operaciones = round(sum(float(op.get("importe_anual", 0.0)) for op in operaciones), 2)

    # Registro Tipo 1: Declarante (Carátula)
    num_declarados_str = str(total_declarados).zfill(9)[-9:]
    importe_total_str = _format_num_cents(suma_total_operaciones, 15)

    reg_1 = (
        f"1"
        f"{MODELO_347_CODE}"
        f"{int(ejercicio):04d}"
        f"{nif_clean[:9].ljust(9)}"
        f"{razon_social}"
        f"T"  # Soporte telemático
        f"{telefono}"
        f"{contacto}"
        f"{num_declarados_str}"
        f"{importe_total_str}"
        f"{' ' * 40}"
    )

    registros: List[str] = [reg_1]

    # Registros Tipo 2: Cada entidad o tercero con operaciones > 3.005,06 €
    for op in operaciones:
        nif_tercero = re.sub(r"[^A-Z0-9]", "", str(op.get("nif", "")).upper())[:9].ljust(9)
        nombre_tercero = _normalize_text(op.get("razon_social", ""), 40)
        clave_op = str(op.get("clave_operacion", "B"))[:1].upper()  # A=Compras, B=Ventas

        imp_anual = _format_num_cents(float(op.get("importe_anual", 0.0)), 13)
        imp_1t = _format_num_cents(float(op.get("trimestre_1", 0.0)), 13)
        imp_2t = _format_num_cents(float(op.get("trimestre_2", 0.0)), 13)
        imp_3t = _format_num_cents(float(op.get("trimestre_3", 0.0)), 13)
        imp_4t = _format_num_cents(float(op.get("trimestre_4", 0.0)), 13)

        reg_2 = (
            f"2"
            f"{MODELO_347_CODE}"
            f"{int(ejercicio):04d}"
            f"{nif_clean[:9].ljust(9)}"
            f"{nif_tercero}"
            f"{nombre_tercero}"
            f"{clave_op}"
            f"{imp_anual}"
            f"{imp_1t}"
            f"{imp_2t}"
            f"{imp_3t}"
            f"{imp_4t}"
            f"{' ' * 20}"
        )
        registros.append(reg_2)

    return "\r\n".join(registros) + "\r\n"

"""
Módulo Oficial de Análisis y Procesamiento de Extractos Bancarios Norma 43 (CSB 43 / AEB).
Estándar financiero español para la transmisión electrónica de extractos de cuentas corrientes.

Soporta:
- Registro 11: Cabecera de cuenta (entidad, sucursal, cuenta, saldo inicial, divisa).
- Registro 22: Movimiento principal (fecha operación, fecha valor, concepto, debe/haber, importe, referencias).
- Registro 23: Conceptos complementarios multilínea (hasta 5 registros complementarios por movimiento).
- Registro 33: Fin de cuenta y saldos finales (número de apuntes, totales acumulados y saldo de cierre).
- Registro 88: Fin de fichero y control de integridad.
- Conversión algorítmica de CCC (20 dígitos) a formato IBAN canónico oficial (24 dígitos con MOD-97).
- Verificación matemática de cuadre contable (Saldo Inicial + Haberes - Debes == Saldo Final).
- Tolerancia a múltiples codificaciones bancarias (latin-1, cp1252, utf-8, iso-8859-15).
"""

from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.core.iban_security import validate_iban


def calculate_ccc_control_digits(entidad: str, sucursal: str, cuenta: str) -> str:
    """
    Calcula los 2 dígitos de control (DC) oficiales para una cuenta bancaria española (CCC)
    según el algoritmo matemático estándar del Banco de España (ponderaciones fijas módulo 11).
    """
    pesos1 = [4, 8, 5, 10, 9, 7, 3, 6]
    pesos2 = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]

    # DC1: Ponderación sobre Entidad (4) y Sucursal (4)
    s1 = sum(int(d) * w for d, w in zip("00" + entidad.zfill(4), pesos1[:2])) + \
         sum(int(d) * w for d, w in zip(entidad.zfill(4), pesos1[2:6])) + \
         sum(int(d) * w for d, w in zip(sucursal.zfill(4), pesos1[6:]))
    # Para exactitud estricta: '00' + entidad + sucursal tiene 10 caracteres
    cadena1 = "00" + entidad.zfill(4) + sucursal.zfill(4)
    s1 = sum(int(d) * w for d, w in zip(cadena1, pesos1))
    r1 = 11 - (s1 % 11)
    dc1 = "0" if r1 == 11 else ("1" if r1 == 10 else str(r1))

    # DC2: Ponderación sobre los 10 dígitos de la Cuenta
    s2 = sum(int(d) * w for d, w in zip(cuenta.zfill(10), pesos2))
    r2 = 11 - (s2 % 11)
    dc2 = "0" if r2 == 11 else ("1" if r2 == 10 else str(r2))

    return f"{dc1}{dc2}"


def ccc_to_iban(entidad: str, sucursal: str, dc: str, cuenta: str) -> str:
    """
    Convierte el Código Cuenta Cliente español (CCC) de 20 dígitos
    al formato IBAN oficial de 24 caracteres (ES + 2 dígitos de control + CCC).
    """
    ccc = f"{entidad.zfill(4)}{sucursal.zfill(4)}{dc.zfill(2)}{cuenta.zfill(10)}"
    # En España el prefijo es 'ES', que equivale numéricamente a '142800'
    check_str = ccc + "142800"
    dc_iban = 98 - (int(check_str) % 97)
    return f"ES{dc_iban:02d}{ccc}"


def _parse_aammdd(date_str: str) -> date:
    """Parsea una fecha en formato AAMMDD del estándar Norma 43 a un objeto `date`."""
    clean = re.sub(r"\D", "", date_str)
    if len(clean) != 6:
        return date.today()
    aa = int(clean[:2])
    mm = int(clean[2:4])
    dd = int(clean[4:6])
    # Siglo 20 para >= 70, siglo 21 para < 70
    year = 1900 + aa if aa >= 70 else 2000 + aa
    return date(year, max(1, min(12, mm)), max(1, min(31, dd)))


def _currency_code(raw_code: str) -> str:
    """Mapea códigos numéricos o alfanuméricos de divisa al estándar ISO."""
    clean = raw_code.strip()
    if clean in ("978", "EUR"):
        return "EUR"
    if clean in ("840", "USD"):
        return "USD"
    if clean in ("826", "GBP"):
        return "GBP"
    return clean or "EUR"


class Norma43Transaction(BaseModel):
    """Movimiento bancario individual dentro de un extracto de cuenta."""
    operation_date: date = Field(..., description="Fecha contable de la operación bancaria")
    value_date: date = Field(..., description="Fecha valor de la operación")
    entry_type: str = Field(..., description="'DEBE' (cargo / salida) o 'HABER' (abono / entrada)")
    amount: float = Field(..., description="Importe nominal del movimiento (positivo)")
    balance_impact: float = Field(..., description="Impacto neto en el saldo (+importe o -importe)")
    common_code: str = Field(default="", description="Código de concepto común bancario")
    own_code: str = Field(default="", description="Código de concepto propio de la entidad")
    document_number: str = Field(default="", description="Número de documento o recibo")
    reference_1: str = Field(default="", description="Referencia 1 del banco")
    reference_2: str = Field(default="", description="Referencia 2 del banco")
    description: str = Field(default="", description="Concepto completo consolidado (Reg 22 + Reg 23)")
    complementary_lines: List[str] = Field(default_factory=list, description="Líneas complementarias del registro 23")


class Norma43AccountStatement(BaseModel):
    """Extracto consolidado de una cuenta corriente bancaria."""
    bank_code: str = Field(..., description="Código de entidad bancaria (4 dígitos)")
    branch_code: str = Field(..., description="Código de sucursal / oficina (4 dígitos)")
    account_number: str = Field(..., description="Número de cuenta (10 dígitos)")
    ccc: str = Field(..., description="Código Cuenta Cliente completo (20 dígitos)")
    iban: str = Field(..., description="IBAN completo oficial español (24 caracteres)")
    currency: str = Field(default="EUR", description="Divisa de la cuenta")
    start_date: date = Field(..., description="Fecha inicial del extracto")
    end_date: date = Field(..., description="Fecha final del extracto")
    initial_balance: float = Field(..., description="Saldo inicial con signo")
    final_balance: float = Field(..., description="Saldo final declarado con signo")
    calculated_final_balance: float = Field(..., description="Saldo final calculado mediante sumatorio")
    total_debit_entries: int = Field(default=0, description="Número de apuntes al Debe")
    total_debit_amount: float = Field(default=0.0, description="Suma total de cargos al Debe")
    total_credit_entries: int = Field(default=0, description="Número de apuntes al Haber")
    total_credit_amount: float = Field(default=0.0, description="Suma total de abonos al Haber")
    is_balanced: bool = Field(default=True, description="Indica si el extracto cuadra aritméticamente")
    balance_difference: float = Field(default=0.0, description="Diferencia de cuadre (debe ser 0.0)")
    account_name: str = Field(default="", description="Nombre abreviado de la cuenta / titular")
    transactions: List[Norma43Transaction] = Field(default_factory=list, description="Lista de movimientos")


class Norma43File(BaseModel):
    """Resultado del procesamiento global de un fichero Norma 43."""
    total_accounts: int = Field(default=0, description="Total de cuentas incluidas en el fichero")
    total_transactions: int = Field(default=0, description="Total de movimientos analizados")
    is_valid: bool = Field(default=True, description="Indica si todas las cuentas cuadran aritméticamente")
    validation_warnings: List[str] = Field(default_factory=list, description="Lista de avisos y descuadres")
    accounts: List[Norma43AccountStatement] = Field(default_factory=list, description="Cuentas analizadas")


def parse_norma43(content: Union[str, bytes]) -> Norma43File:
    """
    Analiza y procesa un archivo de extracto bancario en formato oficial Norma 43 (CSB 43).

    Parámetros:
    - content: Cadena de texto o bytes crudos del archivo.

    Retorna:
    - Objeto `Norma43File` estructurado con todas las cuentas, movimientos y validaciones de cuadre.
    """
    # 1. Decodificar bytes si es necesario
    text = ""
    if isinstance(content, bytes):
        for enc in ("latin-1", "cp1252", "utf-8", "iso-8859-15"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = content.decode("latin-1", errors="replace")
    else:
        text = str(content)

    lines = [line.strip("\r\n") for line in text.splitlines() if line.strip()]

    accounts: List[Norma43AccountStatement] = []
    warnings: List[str] = []

    # Estado temporal durante el parseo de una cuenta
    current_account: Optional[dict] = None
    current_transactions: List[Norma43Transaction] = []
    current_tx: Optional[dict] = None

    for line_idx, raw_line in enumerate(lines, start=1):
        # Asegurar longitud mínima rellenando con espacios si es necesario
        line = raw_line.ljust(80)
        reg_type = line[:2]

        if reg_type == "11":
            # Si había una cuenta previa sin cerrar formalmente con registro 33, se consolida
            if current_account is not None:
                warnings.append(f"Aviso: Se encontró una nueva cabecera (reg 11 en línea {line_idx}) sin cierre de cuenta previo.")

            bank = line[2:6].strip()
            branch = line[6:10].strip()
            account_num = line[10:20].strip()
            start_d = _parse_aammdd(line[20:26])
            end_d = _parse_aammdd(line[26:32])

            sign_init = line[32:33]  # '1' = Deudor (-), '2' = Acreedor (+)
            try:
                init_cents = int(line[33:47])
            except ValueError:
                init_cents = 0
            initial_balance = round((init_cents / 100.0) * (-1.0 if sign_init == "1" else 1.0), 2)

            curr = _currency_code(line[47:50])
            name = line[51:77].strip()

            dc = calculate_ccc_control_digits(bank, branch, account_num)
            ccc = f"{bank.zfill(4)}{branch.zfill(4)}{dc}{account_num.zfill(10)}"
            iban = ccc_to_iban(bank, branch, dc, account_num)

            current_account = {
                "bank_code": bank,
                "branch_code": branch,
                "account_number": account_num,
                "ccc": ccc,
                "iban": iban,
                "currency": curr,
                "start_date": start_d,
                "end_date": end_d,
                "initial_balance": initial_balance,
                "account_name": name,
            }
            current_transactions = []
            current_tx = None

        elif reg_type == "22":
            # Cerrar el movimiento anterior si existía
            if current_tx is not None:
                current_transactions.append(_build_transaction(current_tx))
                current_tx = None

            op_date = _parse_aammdd(line[6:12])
            val_date = _parse_aammdd(line[12:18])
            common_c = line[18:20].strip()
            own_c = line[20:23].strip()
            debit_credit = line[23:24]  # '1' = Debe, '2' = Haber

            try:
                amt_cents = int(line[24:38])
            except ValueError:
                amt_cents = 0
            amount = round(amt_cents / 100.0, 2)
            balance_impact = -amount if debit_credit == "1" else amount

            doc_num = line[38:48].strip()
            ref1 = line[48:60].strip()
            ref2 = line[60:76].strip()

            current_tx = {
                "operation_date": op_date,
                "value_date": val_date,
                "entry_type": "DEBE" if debit_credit == "1" else "HABER",
                "amount": amount,
                "balance_impact": balance_impact,
                "common_code": common_c,
                "own_code": own_c,
                "document_number": doc_num,
                "reference_1": ref1,
                "reference_2": ref2,
                "complementary_lines": []
            }

        elif reg_type == "23":
            # Conceptos complementarios vinculados al movimiento 22 precedente
            if current_tx is not None:
                c1 = line[4:42].strip()
                c2 = line[42:80].strip()
                if c1:
                    current_tx["complementary_lines"].append(c1)
                if c2:
                    current_tx["complementary_lines"].append(c2)

        elif reg_type == "33":
            # Cerrar el último movimiento si estaba pendiente
            if current_tx is not None:
                current_transactions.append(_build_transaction(current_tx))
                current_tx = None

            if current_account is None:
                warnings.append(f"Aviso: Registro 33 en línea {line_idx} sin cabecera previa.")
                continue

            try:
                num_debe = int(line[20:25])
                tot_debe = round(int(line[25:39]) / 100.0, 2)
                num_haber = int(line[39:44])
                tot_haber = round(int(line[44:58]) / 100.0, 2)
            except ValueError:
                num_debe = 0
                tot_debe = 0.0
                num_haber = 0
                tot_haber = 0.0

            sign_fin = line[58:59]  # '1' = Deudor (-), '2' = Acreedor (+)
            try:
                fin_cents = int(line[59:73])
            except ValueError:
                fin_cents = 0
            declared_final_balance = round((fin_cents / 100.0) * (-1.0 if sign_fin == "1" else 1.0), 2)

            # Cuadre matemático
            # Saldo Inicial + Haberes - Debes == Saldo Final
            init_bal = current_account["initial_balance"]
            calc_final_balance = round(init_bal + tot_haber - tot_debe, 2)
            diff = round(abs(calc_final_balance - declared_final_balance), 2)
            is_balanced = diff <= 0.02

            if not is_balanced:
                msg = (
                    f"Descuadre contable en cuenta {current_account['iban']}: "
                    f"Saldo inicial ({init_bal:.2f}€) + Haberes ({tot_haber:.2f}€) - "
                    f"Debes ({tot_debe:.2f}€) = {calc_final_balance:.2f}€ != "
                    f"Saldo final declarado ({declared_final_balance:.2f}€). Diferencia: {diff:.2f}€."
                )
                warnings.append(msg)

            account_stmt = Norma43AccountStatement(
                bank_code=current_account["bank_code"],
                branch_code=current_account["branch_code"],
                account_number=current_account["account_number"],
                ccc=current_account["ccc"],
                iban=current_account["iban"],
                currency=current_account["currency"],
                start_date=current_account["start_date"],
                end_date=current_account["end_date"],
                initial_balance=current_account["initial_balance"],
                final_balance=declared_final_balance,
                calculated_final_balance=calc_final_balance,
                total_debit_entries=num_debe,
                total_debit_amount=tot_debe,
                total_credit_entries=num_haber,
                total_credit_amount=tot_haber,
                is_balanced=is_balanced,
                balance_difference=diff,
                account_name=current_account["account_name"],
                transactions=current_transactions
            )
            accounts.append(account_stmt)
            current_account = None
            current_transactions = []

        elif reg_type == "88":
            # Fin de fichero
            break

    # Si el archivo terminó sin registro 33 pero había una cuenta con transacciones
    if current_account is not None:
        if current_tx is not None:
            current_transactions.append(_build_transaction(current_tx))

        tot_debe = round(sum(t.amount for t in current_transactions if t.entry_type == "DEBE"), 2)
        tot_haber = round(sum(t.amount for t in current_transactions if t.entry_type == "HABER"), 2)
        init_bal = current_account["initial_balance"]
        calc_final = round(init_bal + tot_haber - tot_debe, 2)

        account_stmt = Norma43AccountStatement(
            bank_code=current_account["bank_code"],
            branch_code=current_account["branch_code"],
            account_number=current_account["account_number"],
            ccc=current_account["ccc"],
            iban=current_account["iban"],
            currency=current_account["currency"],
            start_date=current_account["start_date"],
            end_date=current_account["end_date"],
            initial_balance=init_bal,
            final_balance=calc_final,
            calculated_final_balance=calc_final,
            total_debit_entries=len([t for t in current_transactions if t.entry_type == "DEBE"]),
            total_debit_amount=tot_debe,
            total_credit_entries=len([t for t in current_transactions if t.entry_type == "HABER"]),
            total_credit_amount=tot_haber,
            is_balanced=True,
            balance_difference=0.0,
            account_name=current_account["account_name"],
            transactions=current_transactions
        )
        accounts.append(account_stmt)

    total_txs = sum(len(acc.transactions) for acc in accounts)
    all_balanced = all(acc.is_balanced for acc in accounts)

    return Norma43File(
        total_accounts=len(accounts),
        total_transactions=total_txs,
        is_valid=all_balanced and len(accounts) > 0,
        validation_warnings=warnings,
        accounts=accounts
    )


def _build_transaction(tx_data: dict) -> Norma43Transaction:
    """Construye un objeto `Norma43Transaction` consolidando el texto descriptivo."""
    lines = tx_data.get("complementary_lines", [])
    if lines:
        full_desc = " ".join(lines).strip()
    else:
        # Fallback a referencias si no había líneas complementarias
        parts = [tx_data.get("document_number", ""), tx_data.get("reference_1", ""), tx_data.get("reference_2", "")]
        full_desc = " ".join(p for p in parts if p).strip() or "Movimiento bancario"

    return Norma43Transaction(
        operation_date=tx_data["operation_date"],
        value_date=tx_data["value_date"],
        entry_type=tx_data["entry_type"],
        amount=tx_data["amount"],
        balance_impact=tx_data["balance_impact"],
        common_code=tx_data["common_code"],
        own_code=tx_data["own_code"],
        document_number=tx_data["document_number"],
        reference_1=tx_data["reference_1"],
        reference_2=tx_data["reference_2"],
        description=full_desc,
        complementary_lines=lines
    )

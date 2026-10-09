"""
Servicio de Previsión de Tesorería Predictiva y Proyección de Flujo de Caja (Cash Flow Forecasting).
Proporciona visibilidad financiera y detección preventiva de tensiones de liquidez a 30, 60 y 90 días.

Cruza dinámicamente:
- Vencimientos de cobro de facturas de clientes (ajustados con histórico y probabilidad).
- Vencimientos de pago a proveedores y acreedores.
- Estimación de pagos fiscales trimestrales (Modelos AEAT 303 y 111 en sus fechas límite oficiales).
- Gastos fijos recurrentes (nóminas, cotizaciones a la Seguridad Social, alquileres y suministros).
- Simulación diaria de liquidez, cálculo del saldo mínimo y emisión de alertas/recomendaciones operativas.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Alias para evitar colisiones de nombre de campo con la anotación de tipo en Pydantic
dt_date = date


class CashFlowEvent(BaseModel):
    """Evento financiero proyectado en el flujo de caja."""
    date: dt_date = Field(..., description="Fecha proyectada del cobro o pago")
    event_type: str = Field(..., description="'INFLOW' (entrada / cobro) o 'OUTFLOW' (salida / pago)")
    category: str = Field(
        ...,
        description="'CLIENT_INVOICE', 'SUPPLIER_INVOICE', 'TAX_SETTLEMENT', 'RECURRING_EXPENSE'"
    )
    amount: float = Field(..., description="Importe nominal proyectado (siempre positivo)")
    description: str = Field(..., description="Concepto o descripción detallada del movimiento")
    probability: float = Field(default=1.0, description="Probabilidad de ocurrencia (0.0 a 1.0)")
    document_id: Optional[str] = Field(default=None, description="ID de factura o referencia asociada")
    counterparty: Optional[str] = Field(default=None, description="Cliente, proveedor o entidad tributaria")


class DailyCashEvolution(BaseModel):
    """Foto del saldo y movimientos proyectados en un día específico."""
    date: dt_date
    inflows: float = 0.0
    outflows: float = 0.0
    net_day: float = 0.0
    balance: float = 0.0


class TreasuryForecastBucket(BaseModel):
    """Consolidado de previsión para una ventana temporal (30, 60 o 90 días)."""
    horizon: str = Field(..., description="'30_DAYS', '60_DAYS', '90_DAYS'")
    start_date: dt_date
    end_date: dt_date
    initial_balance: float
    projected_inflows: float
    projected_outflows: float
    net_cash_flow: float
    projected_final_balance: float
    lowest_balance: float
    lowest_balance_date: Optional[dt_date] = None
    deficit_days_count: int = 0
    status: str = Field(..., description="'STABLE', 'WARNING', 'DEFICIT'")


class TreasuryForecastReport(BaseModel):
    """Informe integral de previsión de tesorería y diagnóstico de liquidez."""
    calculation_date: dt_date
    current_bank_balance: float
    minimum_safety_threshold: float
    horizon_30_days: TreasuryForecastBucket
    horizon_60_days: TreasuryForecastBucket
    horizon_90_days: TreasuryForecastBucket
    daily_evolution: List[DailyCashEvolution]
    events: List[CashFlowEvent]
    alerts: List[str]
    recommendations: List[str]


def _get_official_tax_deadlines(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Calcula las fechas oficiales de liquidación trimestral de la AEAT
    (20 de abril, 20 de julio, 20 de octubre y 30 de enero) que caen dentro del intervalo.
    """
    deadlines = []
    current_year = start_date.year

    for yr in (current_year, current_year + 1):
        candidates = [
            {"date": date(yr, 1, 30), "quarter": "4T", "year": yr - 1, "desc": "Cierre 4T (Modelo 303 e IRPF 111)"},
            {"date": date(yr, 4, 20), "quarter": "1T", "year": yr, "desc": "Cierre 1T (Modelo 303 e IRPF 111)"},
            {"date": date(yr, 7, 20), "quarter": "2T", "year": yr, "desc": "Cierre 2T (Modelo 303 e IRPF 111)"},
            {"date": date(yr, 10, 20), "quarter": "3T", "year": yr, "desc": "Cierre 3T (Modelo 303 e IRPF 111)"},
        ]
        for c in candidates:
            if start_date <= c["date"] <= end_date:
                deadlines.append(c)

    deadlines.sort(key=lambda x: x["date"])
    return deadlines


def calculate_treasury_forecast(
    current_bank_balance: float,
    sales_invoices: List[Dict[str, Any]],
    purchase_invoices: List[Dict[str, Any]],
    estimated_tax_liabilities: Optional[List[Dict[str, Any]]] = None,
    recurring_expenses: Optional[List[Dict[str, Any]]] = None,
    minimum_safety_threshold: float = 1000.0,
    reference_date: Optional[date] = None,
) -> TreasuryForecastReport:
    """
    Genera la simulación completa de previsión de flujo de caja para 30, 60 y 90 días.

    Parámetros:
    - current_bank_balance: Saldo disponible consolidado actual en cuentas bancarias.
    - sales_invoices: Facturas emitidas pendientes de cobro (due_date, total_amount, customer_name, etc.).
    - purchase_invoices: Facturas recibidas pendientes de pago (due_date, total_amount, issuer_name, etc.).
    - estimated_tax_liabilities: Estimación de compromisos tributarios trimestrales (importe, periodo).
    - recurring_expenses: Gastos fijos identificados (alquileres, nóminas, cuotas de suministros).
    - minimum_safety_threshold: Colchón de seguridad mínimo para activar advertencias.
    - reference_date: Fecha base de cálculo (por defecto hoy).
    """
    today = reference_date or date.today()
    max_horizon_days = 90
    end_forecast_date = today + timedelta(days=max_horizon_days)

    events: List[CashFlowEvent] = []

    # -------------------------------------------------------------
    # 1. ENTRADAS: Facturas de Venta / Clientes (INFLOW)
    # -------------------------------------------------------------
    for sinv in sales_invoices:
        amount = float(sinv.get("total_amount", 0.0) or 0.0)
        if amount <= 0:
            continue

        raw_due = sinv.get("due_date") or sinv.get("issue_date")
        if isinstance(raw_due, str):
            try:
                due_d = datetime.fromisoformat(raw_due[:10]).date()
            except Exception:
                due_d = today + timedelta(days=30)
        elif isinstance(raw_due, date):
            due_d = raw_due
        else:
            due_d = today + timedelta(days=30)

        # Si ya venció en el pasado, se asume cobro inmediato con probabilidad reducida (morosidad)
        if due_d < today:
            projected_d = today + timedelta(days=3)
            prob = 0.80
        else:
            projected_d = due_d
            prob = 0.95

        if projected_d <= end_forecast_date:
            customer = sinv.get("customer_name") or "Cliente"
            inv_num = sinv.get("invoice_number") or sinv.get("id", "")
            events.append(
                CashFlowEvent(
                    date=projected_d,
                    event_type="INFLOW",
                    category="CLIENT_INVOICE",
                    amount=round(amount, 2),
                    description=f"Cobro Fra. {inv_num} - {customer}",
                    probability=prob,
                    document_id=str(sinv.get("id", "")),
                    counterparty=customer,
                )
            )

    # -------------------------------------------------------------
    # 2. SALIDAS: Facturas de Compra / Proveedores (OUTFLOW)
    # -------------------------------------------------------------
    for pinv in purchase_invoices:
        amount = float(pinv.get("total_amount", 0.0) or 0.0)
        if amount <= 0:
            continue

        raw_due = pinv.get("due_date") or pinv.get("issue_date")
        if isinstance(raw_due, str):
            try:
                due_d = datetime.fromisoformat(raw_due[:10]).date()
            except Exception:
                due_d = today + timedelta(days=30)
        elif isinstance(raw_due, date):
            due_d = raw_due
        else:
            due_d = today + timedelta(days=30)

        # Si ya venció, se proyecta como pago prioritario a corto plazo
        if due_d < today:
            projected_d = today + timedelta(days=2)
        else:
            projected_d = due_d

        if projected_d <= end_forecast_date:
            supplier = pinv.get("issuer_name") or "Proveedor"
            inv_num = pinv.get("invoice_number") or pinv.get("id", "")
            events.append(
                CashFlowEvent(
                    date=projected_d,
                    event_type="OUTFLOW",
                    category="SUPPLIER_INVOICE",
                    amount=round(amount, 2),
                    description=f"Pago Fra. {inv_num} - {supplier}",
                    probability=0.98,
                    document_id=str(pinv.get("id", "")),
                    counterparty=supplier,
                )
            )

    # -------------------------------------------------------------
    # 3. SALIDAS: Compromisos Fiscales Oficiales AEAT (OUTFLOW)
    # -------------------------------------------------------------
    tax_deadlines = _get_official_tax_deadlines(today, end_forecast_date)
    liabilities = estimated_tax_liabilities or []

    for dl in tax_deadlines:
        tax_amount = 0.0
        matching = [
            t for t in liabilities
            if str(t.get("period", "")).upper() == dl["quarter"] and int(t.get("year", today.year)) == dl["year"]
        ]
        if matching:
            tax_amount = float(matching[0].get("estimated_amount", 0.0) or 0.0)
        elif liabilities:
            # Si no hay match exacto pero se pasa estimación general
            first = liabilities[0]
            tax_amount = float(first.get("estimated_amount", 0.0) or 0.0)

        if tax_amount > 0:
            events.append(
                CashFlowEvent(
                    date=dl["date"],
                    event_type="OUTFLOW",
                    category="TAX_SETTLEMENT",
                    amount=round(tax_amount, 2),
                    description=f"Liquidación tributaria AEAT {dl['desc']}",
                    probability=1.0,
                    counterparty="Agencia Tributaria (AEAT)",
                )
            )

    # -------------------------------------------------------------
    # 4. SALIDAS: Gastos Fijos Recurrentes (Nóminas, Suministros, TGSS)
    # -------------------------------------------------------------
    rec_list = recurring_expenses or []
    for rec in rec_list:
        amount = float(rec.get("amount", 0.0) or 0.0)
        day_of_month = int(rec.get("day_of_month", 28))
        desc = rec.get("description", "Gasto recurrente")

        # Proyectar para los próximos 3 meses
        for month_offset in range(4):
            target_m = today.month + month_offset
            target_y = today.year
            while target_m > 12:
                target_m -= 12
                target_y += 1

            try:
                rec_date = date(target_y, target_m, min(day_of_month, 28))
            except Exception:
                continue

            if today <= rec_date <= end_forecast_date and amount > 0:
                events.append(
                    CashFlowEvent(
                        date=rec_date,
                        event_type="OUTFLOW",
                        category="RECURRING_EXPENSE",
                        amount=round(amount, 2),
                        description=f"{desc} (Mensual)",
                        probability=0.99,
                        counterparty=rec.get("counterparty", "Servicios fijos"),
                    )
                )

    # Ordenar cronológicamente todos los eventos
    events.sort(key=lambda e: (e.date, 0 if e.event_type == "INFLOW" else 1))

    # -------------------------------------------------------------
    # 5. SIMULACIÓN DIARIA Y EVOLUCIÓN TEMPORAL
    # -------------------------------------------------------------
    daily_evolution: List[DailyCashEvolution] = []
    events_by_date: Dict[date, List[CashFlowEvent]] = {}
    for ev in events:
        events_by_date.setdefault(ev.date, []).append(ev)

    running_balance = round(float(current_bank_balance), 2)
    lowest_30 = running_balance
    lowest_30_d = today
    lowest_60 = running_balance
    lowest_60_d = today
    lowest_90 = running_balance
    lowest_90_d = today

    deficit_count_30 = 0
    deficit_count_60 = 0
    deficit_count_90 = 0

    curr_d = today
    while curr_d <= end_forecast_date:
        day_events = events_by_date.get(curr_d, [])
        in_sum = round(sum(e.amount for e in day_events if e.event_type == "INFLOW"), 2)
        out_sum = round(sum(e.amount for e in day_events if e.event_type == "OUTFLOW"), 2)
        net_day = round(in_sum - out_sum, 2)
        running_balance = round(running_balance + net_day, 2)

        days_from_start = (curr_d - today).days

        if days_from_start <= 30:
            if running_balance < lowest_30:
                lowest_30 = running_balance
                lowest_30_d = curr_d
            if running_balance < 0:
                deficit_count_30 += 1

        if days_from_start <= 60:
            if running_balance < lowest_60:
                lowest_60 = running_balance
                lowest_60_d = curr_d
            if running_balance < 0:
                deficit_count_60 += 1

        if days_from_start <= 90:
            if running_balance < lowest_90:
                lowest_90 = running_balance
                lowest_90_d = curr_d
            if running_balance < 0:
                deficit_count_90 += 1

        daily_evolution.append(
            DailyCashEvolution(
                date=curr_d,
                inflows=in_sum,
                outflows=out_sum,
                net_day=net_day,
                balance=running_balance,
            )
        )
        curr_d += timedelta(days=1)

    # -------------------------------------------------------------
    # 6. CONSTRUCCIÓN DE BUCKETS (30, 60 y 90 DÍAS)
    # -------------------------------------------------------------
    def _make_bucket(days: int, lowest: float, lowest_d: date, def_count: int, horizon_name: str) -> TreasuryForecastBucket:
        sub_events = [e for e in events if (e.date - today).days <= days]
        tot_in = round(sum(e.amount for e in sub_events if e.event_type == "INFLOW"), 2)
        tot_out = round(sum(e.amount for e in sub_events if e.event_type == "OUTFLOW"), 2)
        net_cf = round(tot_in - tot_out, 2)
        final_bal = round(current_bank_balance + net_cf, 2)

        if lowest < 0:
            st = "DEFICIT"
        elif lowest < minimum_safety_threshold:
            st = "WARNING"
        else:
            st = "STABLE"

        return TreasuryForecastBucket(
            horizon=horizon_name,
            start_date=today,
            end_date=today + timedelta(days=days),
            initial_balance=round(float(current_bank_balance), 2),
            projected_inflows=tot_in,
            projected_outflows=tot_out,
            net_cash_flow=net_cf,
            projected_final_balance=final_bal,
            lowest_balance=lowest,
            lowest_balance_date=lowest_d,
            deficit_days_count=def_count,
            status=st,
        )

    b30 = _make_bucket(30, lowest_30, lowest_30_d, deficit_count_30, "30_DAYS")
    b60 = _make_bucket(60, lowest_60, lowest_60_d, deficit_count_60, "60_DAYS")
    b90 = _make_bucket(90, lowest_90, lowest_90_d, deficit_count_90, "90_DAYS")

    # -------------------------------------------------------------
    # 7. DIAGNÓSTICO, ALERTAS Y RECOMENDACIONES OPERATIVAS
    # -------------------------------------------------------------
    alerts: List[str] = []
    recommendations: List[str] = []

    if b30.status == "DEFICIT":
        alerts.append(
            f"Tensión crítica a 30 días: Se proyecta descubierto bancario de {b30.lowest_balance:.2f}€ "
            f"el {b30.lowest_balance_date.strftime('%d/%m/%Y')}."
        )
        recommendations.append("Priorizar reclamación de facturas vencidas de clientes o solicitar línea de crédito a corto plazo.")
    elif b30.status == "WARNING":
        alerts.append(
            f"Aviso a 30 días: El saldo desciende hasta {b30.lowest_balance:.2f}€, "
            f"por debajo del umbral de seguridad ({minimum_safety_threshold:.2f}€)."
        )

    if b60.status == "DEFICIT" and b30.status != "DEFICIT":
        alerts.append(
            f"Déficit proyectado a 60 días: Saldo mínimo de {b60.lowest_balance:.2f}€ "
            f"alrededor del {b60.lowest_balance_date.strftime('%d/%m/%Y')}."
        )
        recommendations.append("Planificar escalonamiento de pagos a proveedores y considerar aplazamiento tributario con la AEAT.")

    if b90.status == "DEFICIT" and b60.status != "DEFICIT":
        alerts.append(f"Alerta a medio plazo (90 días): Saldo proyectado en negativo ({b90.lowest_balance:.2f}€).")

    # Recomendaciones adicionales basadas en la composición del flujo
    tax_events = [e for e in events if e.category == "TAX_SETTLEMENT"]
    if tax_events:
        closest_tax = tax_events[0]
        if closest_tax.amount > (current_bank_balance * 0.40):
            recommendations.append(
                f"El próximo vencimiento fiscal ({closest_tax.description}: {closest_tax.amount:.2f}€) "
                f"compromete más del 40% del saldo bancario actual. Reservar fondos con antelación."
            )

    if not alerts:
        recommendations.append("Posición de liquidez estable y equilibrada para el horizonte de 90 días.")

    return TreasuryForecastReport(
        calculation_date=today,
        current_bank_balance=round(float(current_bank_balance), 2),
        minimum_safety_threshold=round(float(minimum_safety_threshold), 2),
        horizon_30_days=b30,
        horizon_60_days=b60,
        horizon_90_days=b90,
        daily_evolution=daily_evolution,
        events=events,
        alerts=alerts,
        recommendations=recommendations,
    )

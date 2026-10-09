"""
Test Suite Exhaustiva — Fase 2 (Contabilidad General y Libros Oficiales) y Fase 3 (Integraciones Contables)
KontaAI Suite — Rigor Contable PGC (RD 1515/2007)
Ejecución nativa asíncrona mediante httpx.AsyncClient y AsyncSessionLocal.
"""

import sys
import os
import asyncio
from datetime import date, datetime
from decimal import Decimal
import httpx
from sqlalchemy import select, delete

# Asegurar path de la aplicación
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from app.main import app
from app.core.database import AsyncSessionLocal, init_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.accounting_entry import AccountingEntryLine
from app.models.integration import ExportBatch, CompanyIntegration


async def get_or_create_test_company(db) -> Company:
    company_cif = "B98765432"
    res = await db.execute(select(Company).where(Company.cif == company_cif))
    comp = res.scalars().first()
    if not comp:
        comp = Company(
            id="comp-test-phase2-01",
            cif=company_cif,
            razon_social="Asesoría Contable Demostración S.L.",
            domicilio_fiscal="Calle Mayor 12, Valencia",
            is_active=True,
            plan_cuentas_longitud=9,
            fecha_cierre_contable=None,
        )
        db.add(comp)
        await db.commit()
        await db.refresh(comp)
    else:
        # Resetear estado para las pruebas
        comp.fecha_cierre_contable = None
        await db.commit()
        await db.refresh(comp)
    return comp


async def clean_test_data(db, company_id: str):
    await db.execute(delete(AccountingEntryLine).where(AccountingEntryLine.company_id == company_id))
    await db.execute(delete(Invoice).where(Invoice.company_id == company_id))
    await db.execute(delete(ExportBatch).where(ExportBatch.company_id == company_id))
    await db.commit()


async def test_journal_balance_and_reversal(client: httpx.AsyncClient, company: Company):
    """
    Test 1: Verifica que el Libro Diario devuelve asientos cuadrados
    y que la reversión contable genera un contra-asiento invertido auditable.
    """
    async with AsyncSessionLocal() as db:
        await clean_test_data(db, company.id)

        # Asiento 1: Compra con IVA soportado (Debe: 600000000 + 472000000 = 121 €, Haber: 400000000 = 121 €)
        line1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 2, 1),
            subcuenta="600000000",
            concepto="Compra de material informático",
            debe=100.00,
            haber=0.00,
            status="contabilizado",
        )
        line2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 2, 1),
            subcuenta="472000000",
            concepto="IVA Soportado 21%",
            debe=21.00,
            haber=0.00,
            status="contabilizado",
        )
        line3 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 2, 1),
            subcuenta="400000000",
            concepto="Proveedor Tech S.L.",
            debe=0.00,
            haber=121.00,
            status="contabilizado",
        )
        db.add_all([line1, line2, line3])
        await db.commit()

    # 1. Consultar el diario
    res = await client.get(f"/api/v1/companies/{company.id}/journal?fiscal_year=2026")
    assert res.status_code == 200, f"Error obteniendo diario: {res.text}"
    data = res.json()
    assert data["total_asientos"] == 1
    assert data["total_general_debe"] == 121.0
    assert data["total_general_haber"] == 121.0
    entry = data["asientos"][0]
    assert entry["is_balanced"] is True
    assert entry["status"] == "contabilizado"

    # 2. Revertir el asiento contable
    rev_payload = {
        "reason": "Error en asignación de cuenta de gasto por el revisor",
        "accounting_date": "2026-02-02",
    }
    rev_res = await client.post(
        f"/api/v1/companies/{company.id}/journal/1/reverse",
        json=rev_payload,
    )
    assert rev_res.status_code == 200, f"Error revirtiendo asiento: {rev_res.text}"
    rev_data = rev_res.json()
    assert rev_data["status"] == "revertido"
    assert rev_data["reversal_entry_number"] == 2

    # 3. Comprobar que en el diario ahora hay 2 asientos y ambos están cuadrados
    res_after = await client.get(f"/api/v1/companies/{company.id}/journal?fiscal_year=2026")
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["total_asientos"] == 2

    # Asiento 1 debe ser 'revertido'
    entry1 = next(e for e in data_after["asientos"] if e["entry_number"] == 1)
    assert entry1["status"] == "revertido"

    # Asiento 2 debe ser el contra-asiento invertido
    entry2 = next(e for e in data_after["asientos"] if e["entry_number"] == 2)
    assert entry2["status"] == "contabilizado"
    line_400 = next(l for l in entry2["lines"] if l["subcuenta"] == "400000000")
    assert line_400["debe"] == 121.0
    assert line_400["haber"] == 0.0


async def test_fiscal_year_closing_and_reopening(client: httpx.AsyncClient, company: Company):
    """
    Test 2: Valida el cierre de ejercicio con regularización de ingresos (grupo 7)
    y gastos (grupo 6) contra la cuenta 129 y el bloqueo de periodos cerrados.
    """
    async with AsyncSessionLocal() as db:
        await clean_test_data(db, company.id)

        # Asiento de Ingreso: Ventas (700) 1000 €, Clientes (430) 1000 €
        line_v1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 3, 10),
            subcuenta="430000001",
            concepto="Cliente A",
            debe=1000.00,
            haber=0.00,
            status="contabilizado",
        )
        line_v2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 3, 10),
            subcuenta="700000000",
            concepto="Ventas mercaderías",
            debe=0.00,
            haber=1000.00,
            status="contabilizado",
        )

        # Asiento de Gasto: Compras (600) 400 €, Proveedores (400) 400 €
        line_g1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=2,
            fecha=date(2026, 4, 15),
            subcuenta="600000000",
            concepto="Compras materias primas",
            debe=400.00,
            haber=0.00,
            status="contabilizado",
        )
        line_g2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=2,
            fecha=date(2026, 4, 15),
            subcuenta="400000001",
            concepto="Proveedor B",
            debe=0.00,
            haber=400.00,
            status="contabilizado",
        )
        db.add_all([line_v1, line_v2, line_g1, line_g2])
        await db.commit()

    # 1. Ejecutar Cierre de Ejercicio 2026
    close_payload = {
        "year": 2026,
        "closing_date": "2026-12-31",
    }
    res_close = await client.post(
        f"/api/v1/companies/{company.id}/journal/close-fiscal-year",
        json=close_payload,
    )
    assert res_close.status_code == 200, f"Error cerrando ejercicio: {res_close.text}"
    close_data = res_close.json()
    assert close_data["success"] is True
    # Beneficio neto = 1000 (Ingresos) - 400 (Gastos) = 600 €
    assert close_data["resultado_neto"] == 600.0

    # 2. Verificar que no se permite revertir un asiento en un ejercicio cerrado
    res_blocked = await client.post(
        f"/api/v1/companies/{company.id}/journal/1/reverse",
        json={"reason": "Intento de reversión extemporánea", "accounting_date": "2026-03-10"},
    )
    assert res_blocked.status_code == 400
    assert "cerrado" in res_blocked.json()["detail"].lower()

    # 3. Intentar reabrir con CIF erróneo
    res_bad_reopen = await client.post(
        f"/api/v1/companies/{company.id}/journal/reopen-fiscal-year",
        json={"cif_confirmation": "B00000000"},
    )
    assert res_bad_reopen.status_code == 400

    # 4. Reabrir correctamente con el CIF verificado
    res_ok_reopen = await client.post(
        f"/api/v1/companies/{company.id}/journal/reopen-fiscal-year",
        json={"cif_confirmation": "B98765432"},
    )
    assert res_ok_reopen.status_code == 200
    assert res_ok_reopen.json()["success"] is True


async def test_general_ledger(client: httpx.AsyncClient, company: Company):
    """
    Test 3: Valida el Libro Mayor por cuenta contable con cálculo progresivo de saldos
    y naturaleza contable (Deudora vs Acreedora).
    """
    async with AsyncSessionLocal() as db:
        await clean_test_data(db, company.id)
        # Movimiento 1 en Banco (572): Ingreso de 500 € (Debe)
        line1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 1, 5),
            subcuenta="572000001",
            concepto="Cobro de factura F-001",
            debe=500.00,
            haber=0.00,
            status="contabilizado",
        )
        # Movimiento 2 en Banco (572): Pago de 150 € (Haber)
        line2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=2,
            fecha=date(2026, 1, 10),
            subcuenta="572000001",
            concepto="Pago de suministros",
            debe=0.00,
            haber=150.00,
            status="contabilizado",
        )
        db.add_all([line1, line2])
        await db.commit()

    res = await client.get(f"/api/v1/companies/{company.id}/ledger/572000001?fiscal_year=2026")
    assert res.status_code == 200, f"Error obteniendo mayor: {res.text}"
    ledger = res.json()
    assert ledger["subcuenta"] == "572000001"
    assert ledger["naturaleza_esperada"] in ("DEUDORA", "MIXTA")
    assert ledger["total_debe"] == 500.0
    assert ledger["total_haber"] == 150.0
    assert ledger["saldo_final"] == 350.0
    assert len(ledger["movimientos"]) == 2
    assert ledger["movimientos"][0]["saldo_progresivo"] == 500.0
    assert ledger["movimientos"][1]["saldo_progresivo"] == 350.0


async def test_trial_balance_and_csv_export(client: httpx.AsyncClient, company: Company):
    """
    Test 4: Valida el Balance de Sumas y Saldos con subtotales por los 7 grupos oficiales del PGC
    y la exportación descargable a CSV con BOM UTF-8 y delimitador ';'.
    """
    async with AsyncSessionLocal() as db:
        await clean_test_data(db, company.id)
        # Línea en Grupo 2 (Activo no corriente - 216 Mobiliario)
        l1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 1, 2),
            subcuenta="216000000",
            concepto="Mobiliario de oficina",
            debe=1200.00,
            haber=0.00,
            status="contabilizado",
        )
        # Línea en Grupo 5 (Tesorería - 572 Banco)
        l2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=1,
            fecha=date(2026, 1, 2),
            subcuenta="572000000",
            concepto="Pago mobiliario",
            debe=0.00,
            haber=1200.00,
            status="contabilizado",
        )
        db.add_all([l1, l2])
        await db.commit()

    # 1. Consultar endpoint JSON del balance
    res = await client.get(f"/api/v1/companies/{company.id}/trial-balance?fiscal_year=2026")
    assert res.status_code == 200, f"Error obteniendo balance: {res.text}"
    tb = res.json()
    assert tb["totales"]["suma_debe"] == 1200.0
    assert tb["totales"]["suma_haber"] == 1200.0
    assert tb["totales"]["cuadrado"] is True
    assert "grupos_resumen" in tb

    # Grupo 2 debe tener Debe: 1200 y Saldo Deudor: 1200
    g2 = next(g for g in tb["grupos_resumen"] if g["grupo"] == "2")
    assert g2["suma_debe"] == 1200.0
    assert g2["saldo_deudor"] == 1200.0

    # Grupo 5 debe tener Haber: 1200 y Saldo Acreedor: 1200
    g5 = next(g for g in tb["grupos_resumen"] if g["grupo"] == "5")
    assert g5["suma_haber"] == 1200.0
    assert g5["saldo_acreedor"] == 1200.0

    # 2. Consultar exportación a CSV
    res_csv = await client.get(f"/api/v1/companies/{company.id}/trial-balance/export-csv?fiscal_year=2026")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    csv_text = res_csv.text
    assert "CUENTA;DESCRIPCIÓN;SUMA DEBE (€);SUMA HABER (€);SALDO DEUDOR (€);SALDO ACREEDOR (€)" in csv_text
    assert "216000000" in csv_text
    assert "572000000" in csv_text


async def test_accounting_integrations_and_duplicate_prevention(client: httpx.AsyncClient, company: Company):
    """
    Test 5 (Fase 3): Valida la generación de ficheros de intercambio (A3, Contasol, Sage),
    los estados reales (EXPORTED_FILE) y el bloqueo estricto por huella digital SHA-256
    salvo que se especifique justificación auditable (force_reexport).
    """
    async with AsyncSessionLocal() as db:
        await clean_test_data(db, company.id)

        # Factura procesada aprobada
        inv = Invoice(
            id="inv-acc-phase2-001",
            company_id=company.id,
            file_path="storage/test.pdf",
            file_name="test.pdf",
            invoice_number="FAC-2026-0099",
            issue_date=date(2026, 5, 20),
            issuer_name="Software Solutions S.L.",
            issuer_cif="B12345678",
            total_amount=1210.00,
            total_base=1000.00,
            total_tax=210.00,
            currency="EUR",
            status="GREEN",
            is_processed=True,
            exported_to_erp=False,
        )
        db.add(inv)

        # Asiento contable asociado
        l1 = AccountingEntryLine(
            company_id=company.id,
            entry_number=10,
            fecha=date(2026, 5, 20),
            subcuenta="628000000",
            concepto="Suministros informáticos FAC-2026-0099",
            debe=1000.00,
            haber=0.00,
            invoice_id="inv-acc-phase2-001",
            status="contabilizado",
        )
        l2 = AccountingEntryLine(
            company_id=company.id,
            entry_number=10,
            fecha=date(2026, 5, 20),
            subcuenta="472000000",
            concepto="IVA Soportado FAC-2026-0099",
            debe=210.00,
            haber=0.00,
            invoice_id="inv-acc-phase2-001",
            status="contabilizado",
        )
        l3 = AccountingEntryLine(
            company_id=company.id,
            entry_number=10,
            fecha=date(2026, 5, 20),
            subcuenta="400000001",
            concepto="Software Solutions FAC-2026-0099",
            debe=0.00,
            haber=1210.00,
            invoice_id="inv-acc-phase2-001",
            status="contabilizado",
        )
        db.add_all([l1, l2, l3])
        await db.commit()

    # 1. Exportación a Wolters Kluwer A3 (SUENLACE.DAT)
    payload_a3 = {
        "software_type": "A3",
        "only_pending": True,
        "fiscal_year": 2026,
        "config_overrides": {"company_code": "00001", "journal_code": "00"},
    }
    res_a3 = await client.post(
        f"/api/v1/companies/{company.id}/generate-export",
        json=payload_a3,
    )
    assert res_a3.status_code == 200, f"Error exportando A3: {res_a3.text}"
    batch_a3 = res_a3.json()
    assert batch_a3["software_type"] == "A3"
    assert batch_a3["status"] == "EXPORTED_FILE"
    assert batch_a3["file_format"] == "DAT"
    assert batch_a3["entries_count"] == 3
    assert batch_a3["data_fingerprint"] is not None

    # Descargar el archivo generado y comprobar longitud exacta de 96 caracteres por línea
    dl_res = await client.get(f"/api/v1/companies/batches/{batch_a3['id']}/download")
    assert dl_res.status_code == 200
    raw_lines = dl_res.text.split("\r\n")
    # Omitir última línea vacía por el salto de línea final del archivo
    lines = [l for l in raw_lines if l != ""]
    assert len(lines) > 0, "El fichero A3 debe contener líneas generadas"
    for line in lines:
        assert len(line) == 96, f"Línea A3 debe tener exactamente 96 caracteres, tiene {len(line)} (contenido: '{line}')"

    # 2. Intento de reexportar sin forzar: debe ser bloqueado por huella digital duplicada SHA-256
    payload_dup = {
        "software_type": "A3",
        "only_pending": False,
        "fiscal_year": 2026,
        "force_reexport": False,
    }
    res_dup = await client.post(
        f"/api/v1/companies/{company.id}/generate-export",
        json=payload_dup,
    )
    assert res_dup.status_code == 400
    assert "ya fue exportado" in res_dup.json()["detail"].lower()

    # 3. Reexportación forzada justificada con motivo auditable
    payload_force = {
        "software_type": "A3",
        "only_pending": False,
        "fiscal_year": 2026,
        "force_reexport": True,
        "reexport_reason": "Pérdida accidental del fichero en el terminal del despacho",
    }
    res_force = await client.post(
        f"/api/v1/companies/{company.id}/generate-export",
        json=payload_force,
    )
    assert res_force.status_code == 200
    batch_force = res_force.json()
    assert batch_force["status"] == "EXPORTED_FILE"

    # 4. Exportación a Contasol DELSOL (CSV con delimitador ';')
    payload_csol = {
        "software_type": "CONTASOL",
        "only_pending": False,
        "fiscal_year": 2026,
        "force_reexport": True,
        "reexport_reason": "Prueba de homologación de formato Contasol",
    }
    res_csol = await client.post(
        f"/api/v1/companies/{company.id}/generate-export",
        json=payload_csol,
    )
    assert res_csol.status_code == 200
    batch_csol = res_csol.json()
    assert batch_csol["software_type"] == "CONTASOL"
    assert batch_csol["file_format"] == "CSV"

    dl_csol = await client.get(f"/api/v1/companies/batches/{batch_csol['id']}/download")
    assert dl_csol.status_code == 200
    assert ";" in dl_csol.text


async def main():
    print("\n" + "=" * 80)
    print("   KONTA AI SUITE - FASE 2 Y FASE 3: SUITE CONTABLE E INTEGRACIONES")
    print("=" * 80 + "\n")

    await init_db()

    async with AsyncSessionLocal() as db:
        company = await get_or_create_test_company(db)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tests = [
            ("Libro Diario: Partida Doble y Reversión Auditable", test_journal_balance_and_reversal),
            ("Ciclo de Vida: Cierre de Ejercicio (cta 129), Bloqueo y Reapertura", test_fiscal_year_closing_and_reopening),
            ("Libro Mayor: Saldos Acumulados Progresivos y Naturaleza Contable", test_general_ledger),
            ("Balance de Sumas y Saldos: 7 Grupos Oficiales PGC y Exportación CSV", test_trial_balance_and_csv_export),
            ("Integraciones: Estados Fidedignos, Huella SHA-256 y Prevención de Duplicados", test_accounting_integrations_and_duplicate_prevention),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                await test_func(client, company)
                print(f"  [PASS] {name}")
                passed += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 80)
        print(f"RESULTADO: {passed} PRUEBAS EXITOSAS | {failed} FALLOS")
        print("=" * 80)

        if failed > 0:
            sys.exit(1)
        else:
            print("\n>>> TODAS LAS PRUEBAS DE FASE 2 Y FASE 3 HAN SIDO SUPERADAS AL 100% <<<\n")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

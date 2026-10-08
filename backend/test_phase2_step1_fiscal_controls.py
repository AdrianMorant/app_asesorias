import asyncio
import os
import sys
from datetime import date, datetime

# Añadir ruta del backend al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal, init_db
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.models.supplier import Supplier
from app.models.account import Account
from app.schemas.invoice_extraction import InvoiceExtractionResult, TaxBreakdownItem
from app.services.validator import (
    find_next_free_supplier_account,
    get_generic_supplier_account,
    get_first_open_business_day,
    evaluate_invoice_rules,
    validate_invoice_integrity
)
from app.services.accounting_engine import generate_accounting_entry_lines


async def test_step2_1():
    print("=" * 70)
    print("TEST PASO 2.1: CONTROLES FISCALES, CASUÍSTICAS Y DUPLICADOS")
    print("=" * 70)

    await init_db()

    async with AsyncSessionLocal() as db:
        # 1. Crear empresa de prueba con longitud de 9 dígitos y cierre contable al 31/12/2025
        company_cif = "B99887766"
        comp_res = await db.execute(select(Company).where(Company.cif == company_cif))
        company = comp_res.scalars().first()
        if not company:
            company = Company(
                cif=company_cif,
                razon_social="EMPRESA PRUEBA FASE 2 SL",
                plan_cuentas_longitud=9,
                storage_base_path="storage_test",
                fecha_cierre_contable=date(2025, 12, 31),
                subcuenta_suplidos_defecto="554000000"
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)
        else:
            company.fecha_cierre_contable = date(2025, 12, 31)
            company.plan_cuentas_longitud = 9
            await db.commit()

        print(f"1. Empresa configurada: {company.razon_social} ({company.cif}), Longitud: {company.plan_cuentas_longitud} dígitos, Cierre: {company.fecha_cierre_contable}")

        # Limpiar datos previos de prueba de esta empresa
        await db.execute(delete(AccountingEntryLine).where(AccountingEntryLine.company_id == company.id))
        await db.execute(delete(InvoiceTaxBreakdown))
        await db.execute(delete(Invoice).where(Invoice.company_id == company.id))
        await db.execute(delete(Account).where(Account.company_id == company.id))
        await db.commit()

        # 2. Test getNextSubaccount (Proveedor nuevo correlativo vs genérico)
        gen_sub = get_generic_supplier_account("410", 9)
        assert gen_sub == "410000000", f"Error en genérica: {gen_sub}"

        next_sub_1 = await find_next_free_supplier_account(company.id, 9, db, prefix="410")
        assert next_sub_1 == "410000001", f"Error en siguiente libre 1: {next_sub_1}"
        print(f"2. Subcuenta correlativa libre inicial (sin proveedores): {next_sub_1} | Genérica: {gen_sub}")

        # Simular que se crea la cuenta 410000001 y 410000002
        acc1 = Account(company_id=company.id, codigo="410000001", descripcion="Acreedor 1", tipo="ACREEDOR")
        acc2 = Account(company_id=company.id, codigo="410000002", descripcion="Acreedor 2", tipo="ACREEDOR")
        db.add_all([acc1, acc2])
        await db.commit()

        next_sub_2 = await find_next_free_supplier_account(company.id, 9, db, prefix="410")
        assert next_sub_2 == "410000003", f"Error en siguiente correlativa libre: esperado 410000003, obtenido {next_sub_2}"
        print(f"   Tras registrar cuentas 410000001 y 410000002, la siguiente libre es: {next_sub_2} (OK)")

        # 3. Test Retención IRPF (Modelo 111 / 190 con importe negativo)
        ext_retention = InvoiceExtractionResult(
            issuer_name="PROFESIONAL ABOGADOS SC",
            issuer_tax_id="E11223344",
            invoice_number="AB-2026-01",
            issue_date="2026-02-15",
            total_base=1000.0,
            total_tax=210.0,
            retention_amount=150.0,
            total_amount=1060.0,
            tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=1000.0, tax_amount=210.0)]
        )
        entries_ret = generate_accounting_entry_lines(
            extraction=ext_retention,
            plan_longitud=9,
            entry_date=date(2026, 2, 15),
            retention_model="111/190"
        )
        ret_line = next((e for e in entries_ret if e.subcuenta.startswith("4751")), None)
        assert ret_line is not None, "Debe existir apunte en la 4751 para retención IRPF"
        assert ret_line.haber == 150.0, f"Retención esperada al haber: 150.0, obtenido {ret_line.haber}"
        assert "111/190" in ret_line.concepto, f"Concepto debe mencionar 111/190: {ret_line.concepto}"
        prov_line = next((e for e in entries_ret if e.subcuenta.startswith("410") or e.subcuenta.startswith("400")), None)
        assert prov_line.haber == 1060.0, f"Abono al proveedor debe ser el neto (1060.0): obtenido {prov_line.haber}"
        print(f"3. Retención IRPF generada con éxito: Cta {ret_line.subcuenta}, Haber: {ret_line.haber} €, Proveedor: {prov_line.haber} € (OK)")

        # 4. Test Suplidos (Cuenta 554, sin IVA, suma en el total)
        ext_suplidos = InvoiceExtractionResult(
            issuer_name="GESTORIA ASOCIADA SL",
            issuer_tax_id="B88776655",
            invoice_number="GEST-2026-09",
            issue_date="2026-03-01",
            total_base=500.0,
            total_tax=105.0,
            total_amount=655.0,
            tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=500.0, tax_amount=105.0)]
        )
        entries_supl = generate_accounting_entry_lines(
            extraction=ext_suplidos,
            plan_longitud=9,
            entry_date=date(2026, 3, 1),
            suplidos_amount=50.0,
            custom_suplidos_account="554000000"
        )
        supl_line = next((e for e in entries_supl if e.subcuenta == "554000000"), None)
        assert supl_line is not None, "Debe existir apunte de suplidos en cuenta 554000000"
        assert supl_line.debe == 50.0, f"Suplidos al debe esperado 50.0, obtenido {supl_line.debe}"
        prov_supl_line = next((e for e in entries_supl if e.subcuenta.startswith("410") or e.subcuenta.startswith("400")), None)
        assert prov_supl_line.haber == 655.0, f"Abono a proveedor debe incluir suplidos (655.0): {prov_supl_line.haber}"
        print(f"4. Suplidos generados con éxito: Cta {supl_line.subcuenta}, Debe: {supl_line.debe} €, Proveedor: {prov_supl_line.haber} € (OK)")

        # 5. Test Factura Rectificativa (Abono contable con importes negativos)
        ext_rect = InvoiceExtractionResult(
            issuer_name="PROVEEDOR TECNOLOGICO SL",
            issuer_tax_id="B77665544",
            invoice_number="RECT-2026-01",
            issue_date="2026-03-10",
            total_base=200.0,
            total_tax=42.0,
            total_amount=242.0,
            tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=200.0, tax_amount=42.0)]
        )
        entries_rect = generate_accounting_entry_lines(
            extraction=ext_rect,
            plan_longitud=9,
            entry_date=date(2026, 3, 10),
            is_rectificativa=True
        )
        gasto_rect = next((e for e in entries_rect if e.subcuenta.startswith("6")), None)
        iva_rect = next((e for e in entries_rect if e.subcuenta.startswith("472")), None)
        prov_rect = next((e for e in entries_rect if e.subcuenta.startswith("410") or e.subcuenta.startswith("400")), None)

        assert gasto_rect.debe == -200.0, f"Gasto rectificativo esperado -200.0, obtenido {gasto_rect.debe}"
        assert iva_rect.debe == -42.0, f"IVA rectificativo esperado -42.0, obtenido {iva_rect.debe}"
        assert prov_rect.haber == -242.0, f"Proveedor rectificativo esperado -242.0, obtenido {prov_rect.haber}"
        print(f"5. Factura Rectificativa generada con éxito con signos negativos en Debe ({gasto_rect.debe} €) y Haber ({prov_rect.haber} €) (OK)")

        # 6. Test Detección de Duplicados en Tiempo Real
        inv1 = Invoice(
            company_id=company.id,
            file_path="storage_test/factura1.pdf",
            file_name="factura1.pdf",
            file_hash="hash_sha256_duplicado_test_123",
            invoice_number="FAC-2026-999",
            issue_date=date(2026, 3, 15),
            issuer_name="PROVEEDOR REPETIDO SL",
            issuer_cif="B12345674",
            total_base=100.0,
            total_tax=21.0,
            total_amount=121.0,
            status="GREEN"
        )
        db.add(inv1)
        await db.commit()
        await db.refresh(inv1)

        ext_dup = InvoiceExtractionResult(
            issuer_name="PROVEEDOR REPETIDO SL",
            issuer_tax_id="B12345674",
            invoice_number="FAC-2026-999",
            issue_date="2026-03-15",
            total_base=100.0,
            total_tax=21.0,
            total_amount=121.0,
            tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=100.0, tax_amount=21.0)]
        )
        rules_dup = await evaluate_invoice_rules(
            extraction=ext_dup,
            company_id=company.id,
            db=db,
            current_invoice_id="nueva_factura_temporal_id",
            file_hash="otro_hash_distinto"
        )
        assert rules_dup.is_duplicate is True, "Debe detectar duplicado por tupla (CIF + Número)"
        assert rules_dup.status.value == "RED", "El semáforo debe ser ROJO ante duplicados"
        assert rules_dup.duplicate_of_id == inv1.id, f"Debe apuntar a inv1.id ({inv1.id})"
        assert any("duplicad" in r.lower() for r in rules_dup.reasons), "Debe incluir razón de duplicidad"
        print(f"6. Detección de duplicados exitosa: is_duplicate={rules_dup.is_duplicate}, status={rules_dup.status.value}, duplicate_of={rules_dup.duplicate_of_id} (OK)")

        # 7. Test Bloqueo Contable de Fechas por Cierre Contable
        ext_closed = InvoiceExtractionResult(
            issuer_name="PROVEEDOR ANTIGUO SL",
            issuer_tax_id="B99999999",
            invoice_number="FAC-2025-01",
            issue_date="2025-10-15",
            total_base=100.0,
            total_tax=21.0,
            total_amount=121.0,
            tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=100.0, tax_amount=21.0)]
        )
        rules_closed = await evaluate_invoice_rules(
            extraction=ext_closed,
            company_id=company.id,
            db=db
        )
        assert rules_closed.date_lock_applied is True, "Debe aplicar bloqueo por cierre contable"
        assert rules_closed.adjusted_fecha_contable is not None, "Debe tener fecha contable ajustada"
        assert rules_closed.adjusted_fecha_contable == "2026-01-02", f"Esperado 2026-01-02, obtenido {rules_closed.adjusted_fecha_contable}"
        print(f"7. Bloqueo contable de fechas exitoso: Fecha emisión=2025-10-15 -> Fecha contable ajustada={rules_closed.adjusted_fecha_contable} (OK)")

    print("=" * 70)
    print("¡TODAS LAS PRUEBAS DEL PASO 2.1 HAN PASADO CON ÉXITO!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_step2_1())

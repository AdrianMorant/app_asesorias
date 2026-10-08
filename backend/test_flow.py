import asyncio
import sys
from datetime import date
from app.core.database import init_db, AsyncSessionLocal
from app.models.company import Company
from app.models.supplier import Supplier
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.schemas.invoice_extraction import InvoiceExtractionResult, TaxBreakdownItem
from app.services.rules_engine import evaluate_invoice_rules
from app.services.accounting_engine import generate_accounting_entry_lines
from app.services.exporters.contasol_csv import export_invoices_to_contasol_csv
from app.services.exporters.a3_suenlace import export_invoices_to_a3_suenlace
from app.services.nif_validator import validate_spanish_id

async def run_tests():
    print("=" * 70)
    print("INICIANDO SUITE DE PRUEBAS DE VALIDACIÓN Y CONTABILIZACIÓN FISCAL")
    print("=" * 70)

    # 1. Inicializar base de datos
    await init_db()
    print("[1] Base de datos SQLite inicializada con éxito.")

    async with AsyncSessionLocal() as db:
        # Crear empresa de prueba
        company = Company(
            cif="A28015865",  # CIF válido
            razon_social="Gestoría y Asesoría Fiscal Central S.A.",
            plan_cuentas_longitud=9
        )
        db.add(company)
        await db.flush()

        # Crear proveedor habitual
        supplier = Supplier(
            company_id=company.id,
            cif="B87654323",
            nombre="Tecnologías Cloud Iberia S.L.",
            subcuenta_proveedor="400000042",
            subcuenta_gasto_defecto="629000001"
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(company)
        await db.refresh(supplier)
        print(f"[2] Empresa creada: {company.razon_social} (ID: {company.id})")
        print(f"[2] Proveedor dado de alta: {supplier.nombre} (CIF: {supplier.cif})")

        # -------------------------------------------------------------
        # ESCENARIO 1: FACTURA VERDE (Cuadre 100%, NIF válido, Proveedor en DB)
        # -------------------------------------------------------------
        ext_green = InvoiceExtractionResult(
            issuer_name="Tecnologías Cloud Iberia S.L.",
            issuer_tax_id="B87654323",
            invoice_number="INV-2024-001",
            issue_date="2024-03-15",
            taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=1000.0, tax_amount=210.0)],
            total_base=1000.0,
            total_tax=210.0,
            retention_rate=0.0,
            retention_amount=0.0,
            total_amount=1210.0,
            concept_summary="Servidor dedicado"
        )
        eval_green = await evaluate_invoice_rules(ext_green, company.id, db)
        print(f"\n[ESCENARIO 1 - Factura Estándar]")
        print(f"  Estado obtenido: {eval_green.status.value} (Esperado: GREEN)")
        print(f"  Motivos: {eval_green.reasons}")
        assert eval_green.status.value == "GREEN", "Fallo en escenario GREEN"

        # Guardar en DB para probar duplicados después
        inv_green = Invoice(
            company_id=company.id,
            supplier_id=supplier.id,
            file_path="uploads/test1.pdf",
            file_name="test1.pdf",
            invoice_number="INV-2024-001",
            issue_date=date(2024, 3, 15),
            issuer_name=ext_green.issuer_name,
            issuer_cif="B87654323",
            total_base=1000.0,
            total_tax=210.0,
            total_retention=0.0,
            total_amount=1210.0,
            status="GREEN",
            status_reasons=eval_green.reasons,
            is_processed=True
        )
        db.add(inv_green)
        await db.flush()

        # Generar asiento contable y verificar Debe == Haber
        entries = generate_accounting_entry_lines(ext_green, company.plan_cuentas_longitud, supplier)
        total_debe = sum(e.debe for e in entries)
        total_haber = sum(e.haber for e in entries)
        print(f"  Asiento contable generado ({len(entries)} líneas):")
        for e in entries:
            print(f"    Cuenta {e.subcuenta} | Debe: {e.debe:.2f} | Haber: {e.haber:.2f} | {e.concepto}")
            db.add(AccountingEntryLine(
                invoice_id=inv_green.id,
                entry_number=e.entry_number,
                fecha=e.fecha,
                subcuenta=e.subcuenta,
                concepto=e.concepto,
                debe=e.debe,
                haber=e.haber,
                documento=e.documento
            ))
        print(f"  Cuadre Debe ({total_debe:.2f} €) == Haber ({total_haber:.2f} €): {abs(total_debe - total_haber) < 0.01}")
        assert abs(total_debe - total_haber) < 0.01, "El asiento contable no cuadra"
        await db.commit()

        # -------------------------------------------------------------
        # ESCENARIO 2: FACTURA AMARILLA (Proveedor desconocido)
        # -------------------------------------------------------------
        ext_yellow_supp = InvoiceExtractionResult(
            issuer_name="Suministros del Norte S.L.",
            issuer_tax_id="B12345674",  # CIF válido pero no dado de alta en esta empresa
            invoice_number="TEL-2024-888",
            issue_date="2024-03-20",
            taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=100.0, tax_amount=21.0)],
            total_base=100.0,
            total_tax=21.0,
            total_amount=121.0
        )
        eval_yellow_supp = await evaluate_invoice_rules(ext_yellow_supp, company.id, db)
        print(f"\n[ESCENARIO 2 - Proveedor no registrado]")
        print(f"  Estado obtenido: {eval_yellow_supp.status.value} (Esperado: YELLOW)")
        print(f"  Motivo: {eval_yellow_supp.reasons}")
        assert eval_yellow_supp.status.value == "YELLOW"

        # -------------------------------------------------------------
        # ESCENARIO 3: FACTURA AMARILLA (> 3.000 € Modelo 347)
        # -------------------------------------------------------------
        ext_yellow_347 = InvoiceExtractionResult(
            issuer_name="Tecnologías Cloud Iberia S.L.",
            issuer_tax_id="B87654323",
            invoice_number="INV-2024-002",
            issue_date="2024-03-22",
            taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=4000.0, tax_amount=840.0)],
            total_base=4000.0,
            total_tax=840.0,
            total_amount=4840.0
        )
        eval_yellow_347 = await evaluate_invoice_rules(ext_yellow_347, company.id, db)
        print(f"\n[ESCENARIO 3 - Operación superior a 3.000 €]")
        print(f"  Estado obtenido: {eval_yellow_347.status.value} (Esperado: YELLOW)")
        print(f"  Motivo: {eval_yellow_347.reasons}")
        assert eval_yellow_347.status.value == "YELLOW"

        # -------------------------------------------------------------
        # ESCENARIO 4: FACTURA ROJA (Descuadre Aritmético)
        # -------------------------------------------------------------
        ext_red_arith = InvoiceExtractionResult(
            issuer_name="Tecnologías Cloud Iberia S.L.",
            issuer_tax_id="B87654323",
            invoice_number="INV-2024-003",
            issue_date="2024-03-25",
            taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=100.0, tax_amount=21.0)],
            total_base=100.0,
            total_tax=21.0,
            total_amount=150.0  # ¡Descuadre de 29 €!
        )
        eval_red_arith = await evaluate_invoice_rules(ext_red_arith, company.id, db)
        print(f"\n[ESCENARIO 4 - Descuadre Aritmético]")
        print(f"  Estado obtenido: {eval_red_arith.status.value} (Esperado: RED)")
        print(f"  Motivo: {eval_red_arith.reasons}")
        assert eval_red_arith.status.value == "RED"

        # -------------------------------------------------------------
        # ESCENARIO 5: FACTURA ROJA (NIF/CIF Inválido)
        # -------------------------------------------------------------
        ext_red_cif = InvoiceExtractionResult(
            issuer_name="Falso Proveedor",
            issuer_tax_id="B12345670",  # Dígito de control incorrecto
            invoice_number="INV-2024-004",
            issue_date="2024-03-26",
            total_base=100.0,
            total_tax=21.0,
            total_amount=121.0
        )
        eval_red_cif = await evaluate_invoice_rules(ext_red_cif, company.id, db)
        print(f"\n[ESCENARIO 5 - CIF Inválido]")
        print(f"  Estado obtenido: {eval_red_cif.status.value} (Esperado: RED)")
        print(f"  Motivo: {eval_red_cif.reasons}")
        assert eval_red_cif.status.value == "RED"

        # -------------------------------------------------------------
        # ESCENARIO 6: FACTURA ROJA (Duplicada)
        # -------------------------------------------------------------
        ext_red_dup = InvoiceExtractionResult(
            issuer_name="Tecnologías Cloud Iberia S.L.",
            issuer_tax_id="B87654323",
            invoice_number="INV-2024-001",  # Ya existe en DB para esta empresa
            issue_date="2024-03-15",
            total_base=1000.0,
            total_tax=210.0,
            total_amount=1210.0
        )
        eval_red_dup = await evaluate_invoice_rules(ext_red_dup, company.id, db)
        print(f"\n[ESCENARIO 6 - Factura Duplicada]")
        print(f"  Estado obtenido: {eval_red_dup.status.value} (Esperado: RED)")
        print(f"  Motivo: {eval_red_dup.reasons}")
        assert eval_red_dup.status.value == "RED"

        # -------------------------------------------------------------
        # ESCENARIO 7: FACTURA CON RETENCIÓN IRPF (Profesionales)
        # -------------------------------------------------------------
        ext_retention = InvoiceExtractionResult(
            issuer_name="Abogados & Asesores S.L.",
            issuer_tax_id="B87654323",
            invoice_number="PROF-2024-010",
            issue_date="2024-03-28",
            taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=1000.0, tax_amount=210.0)],
            total_base=1000.0,
            total_tax=210.0,
            retention_rate=15.0,
            retention_amount=150.0,
            total_amount=1060.0  # 1000 + 210 - 150 = 1060
        )
        eval_retention = await evaluate_invoice_rules(ext_retention, company.id, db)
        print(f"\n[ESCENARIO 7 - Retención IRPF]")
        print(f"  Estado obtenido: {eval_retention.status.value}")
        ret_entries = generate_accounting_entry_lines(ext_retention, 9, supplier)
        ret_debe = sum(e.debe for e in ret_entries)
        ret_haber = sum(e.haber for e in ret_entries)
        print(f"  Cuadre Debe ({ret_debe:.2f} €) == Haber ({ret_haber:.2f} €): {abs(ret_debe - ret_haber) < 0.01}")
        assert abs(ret_debe - ret_haber) < 0.01

        # -------------------------------------------------------------
        # ESCENARIO 8: EXPORTACIÓN CONTASOL Y A3 SUENLACE
        # -------------------------------------------------------------
        # Cargar factura inv_green con apuntes
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        res = await db.execute(select(Invoice).options(selectinload(Invoice.accounting_entries)))
        invoices_to_export = res.scalars().all()

        contasol_csv = export_invoices_to_contasol_csv(invoices_to_export)
        print("\n[ESCENARIO 8 - Fichero Contasol CSV Generado]:")
        for line in contasol_csv.splitlines()[:5]:
            print(f"   {line}")

        a3_dat = export_invoices_to_a3_suenlace(invoices_to_export)
        print("\n[ESCENARIO 8 - Fichero A3 SUENLACE.DAT Generado]:")
        for line in a3_dat.splitlines()[:3]:
            print(f"   {line}")

    print("\n" + "=" * 70)
    print("¡TODAS LAS PRUEBAS UNITARIAS Y DE REGLAS CONTABLES PASARON EXITOSAMENTE!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())

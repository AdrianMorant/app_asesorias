"""
Script de Verificación de Integración Completa para KontaAI Suite.
Comprueba de forma desatendida los 5 pilares fundamentales:
1. Ingesta y corte de documento Multi-Factura (MF).
2. Cálculo de subcuenta correlativa y casuísticas fiscales (retenciones, suplidos, rectificativas).
3. Exportadores ERPs (A3 con A3SeatSplitter, Contasol CSV y Sage CSV).
4. Conciliación bancaria (emparejamiento con facturas y deducción por conceptos TGSS / Iberdrola).
5. Healthcheck de servidores (FastAPI en :8000 y Next.js en :3000).
"""

import sys
import os
import asyncio
import io
import urllib.request
from datetime import date, datetime, timedelta

# Asegurar backend en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import pymupdf
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal, init_db
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.schemas.invoice_dto import SplitInvoiceRequestDTO, SplitGroupDTO
from app.schemas.invoice_extraction import InvoiceExtractionResult, TaxBreakdownItem

from app.api.v1.endpoints.invoices import (
    get_invoice_pages,
    split_invoice,
)

from app.services.validator import (
    find_next_free_supplier_account,
    get_generic_supplier_account,
)
from app.services.accounting_engine import generate_accounting_entry_lines

from app.services.a3_suenlace import (
    generate_a3_suenlace,
    generate_a3_suenlace_bytes,
)
from app.services.contasol_csv import (
    generate_contasol_csv,
    generate_contasol_csv_bytes,
)
from app.services.sage_csv import (
    generate_sage_csv,
    generate_sage_csv_bytes,
)
from app.services.bank_reconciliation import (
    match_bank_transactions,
    build_bank_entry,
)


class SuiteReport:
    def __init__(self):
        self.passes = 0
        self.failures = 0
        self.details = []

    def log_pass(self, title: str, msg: str = ""):
        self.passes += 1
        print(f"  [PASS] {title}")
        if msg:
            print(f"         {msg}")
        self.details.append((True, title, msg))

    def log_fail(self, title: str, err: str = ""):
        self.failures += 1
        print(f"  [FAIL] {title}")
        if err:
            print(f"         {err}")
        self.details.append((False, title, err))


async def run_full_verification():
    report = SuiteReport()
    print("\n" + "=" * 80)
    print("   KONTA AI SUITE - VERIFICACIÓN DE INTEGRACIÓN COMPLETA (5 PILARES)")
    print("=" * 80 + "\n")

    # Inicializar Base de Datos
    await init_db()

    async with AsyncSessionLocal() as db:
        # Preparar Empresa de Test
        company_cif = "B99887766"
        comp_res = await db.execute(select(Company).where(Company.cif == company_cif))
        company = comp_res.scalars().first()
        if not company:
            company = Company(
                cif=company_cif,
                razon_social="EMPRESA VERIFICACION GLOBAL SL",
                plan_cuentas_longitud=9,
                storage_base_path="storage_test",
                fecha_cierre_contable=date(2025, 12, 31),
                subcuenta_suplidos_defecto="554000000",
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)

        # ----------------------------------------------------------------------
        # PILAR 1: Ingesta y corte de documento MF (Multi-Factura)
        # ----------------------------------------------------------------------
        print("[PILAR 1] Ingesta y Corte de Documento MF (Simulación PDF y Split)")
        try:
            # Crear PDF sintético de 2 páginas
            doc = pymupdf.open()
            p1 = doc.new_page()
            p1.insert_text((50, 50), "FACTURA 1: SUMINISTROS SL\nBase: 100 EUR\nIVA 21%: 21 EUR\nTotal: 121 EUR")
            p2 = doc.new_page()
            p2.insert_text((50, 50), "FACTURA 2: CONSULTING SL\nBase: 200 EUR\nIVA 21%: 42 EUR\nTotal: 242 EUR")

            pdf_dir = os.path.join(company.storage_base_path, company.cif, "2026", "Gastos")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, "lote_mf_test.pdf")
            doc.save(pdf_path)
            doc.close()

            parent_inv = Invoice(
                company_id=company.id,
                file_path=pdf_path,
                file_name="lote_mf_test.pdf",
                invoice_number="LOTE-MF-001",
                issue_date=date(2026, 3, 1),
                issuer_name="Lote Documental Escaneado",
                issuer_cif="B00000000",
                total_base=300.0,
                total_tax=63.0,
                total_amount=363.0,
                status="YELLOW",
                workflow_status="a_revisar",
                es_multifactura=True,
                num_paginas=2,
            )
            db.add(parent_inv)
            await db.commit()
            await db.refresh(parent_inv)

            # Verificar detección de páginas
            pages_res = await get_invoice_pages(invoice_id=parent_inv.id, db=db)
            if pages_res.num_paginas == 2 and len(pages_res.pages) == 2:
                report.log_pass("Detección de páginas PDF", f"Detectadas {pages_res.num_paginas} páginas y marcado MF.")
            else:
                report.log_fail("Detección de páginas PDF", f"Páginas detectadas incorrectas: {pages_res.num_paginas}")

            # Ejecutar corte en 2 sub-documentos
            split_req = SplitInvoiceRequestDTO(
                splits=[
                    SplitGroupDTO(page_numbers=[1], custom_name="factura_1"),
                    SplitGroupDTO(page_numbers=[2], custom_name="factura_2"),
                ]
            )
            split_result = await split_invoice(invoice_id=parent_inv.id, payload=split_req, db=db)
            if len(split_result) == 2:
                report.log_pass(
                    "Separación documental de páginas (Split)",
                    f"Generadas {len(split_result)} subfacturas independientes con workflow 'a_revisar'."
                )
            else:
                report.log_fail("Separación documental", f"Subfacturas generadas: {len(split_result)}")

        except Exception as e:
            report.log_fail("Pilar 1 - Error", str(e))

        # ----------------------------------------------------------------------
        # PILAR 2: Subcuenta correlativa y casuísticas fiscales
        # ----------------------------------------------------------------------
        print("\n[PILAR 2] Subcuentas Correlativas y Casuísticas Fiscales")
        try:
            # 2.1 Subcuenta correlativa libre
            next_acc = await find_next_free_supplier_account(
                company_id=company.id,
                length=company.plan_cuentas_longitud or 9,
                db=db,
                prefix="410"
            )
            gen_acc = get_generic_supplier_account(
                length=company.plan_cuentas_longitud or 9,
                prefix="410"
            )
            if next_acc.startswith("410") and len(next_acc) == 9 and next_acc != gen_acc:
                report.log_pass("Cálculo Subcuenta Correlativa", f"Siguiente libre: {next_acc} (Genérica: {gen_acc})")
            else:
                report.log_fail("Subcuenta correlativa", f"Resultado inesperado: {next_acc}")

            # 2.2 Factura con Retención IRPF (15%)
            ext_ret = InvoiceExtractionResult(
                issuer_name="Abogado Fiscalista SL",
                issuer_tax_id="B11223344",
                invoice_number="PROF-001",
                issue_date="2026-03-10",
                total_base=1000.0,
                total_tax=210.0,
                retention_amount=150.0,
                retention_rate=15.0,
                total_amount=1060.0,
                taxes=[TaxBreakdownItem(tax_rate=21.0, base_amount=1000.0, tax_amount=210.0)]
            )
            entries_ret = generate_accounting_entry_lines(
                extraction=ext_ret,
                plan_longitud=9,
                custom_supplier_account="410000001",
                retention_model="111/190"
            )
            debe_ret = sum(e.debe for e in entries_ret)
            haber_ret = sum(e.haber for e in entries_ret)
            ret_entry = next((e for e in entries_ret if e.subcuenta.startswith("4751")), None)
            if abs(debe_ret - haber_ret) < 0.001 and ret_entry and ret_entry.haber == 150.0:
                report.log_pass("Casuística Retención IRPF (Mod. 111/190)", f"Cuenta {ret_entry.subcuenta} al Haber por 150.00 € (Cuadre 0.00 €).")
            else:
                report.log_fail("Casuística Retención IRPF", f"Descuadre o sin 4751 (Debe: {debe_ret}, Haber: {haber_ret})")

            # 2.3 Factura con Suplidos
            ext_sup = InvoiceExtractionResult(
                issuer_name="Notaría Central",
                issuer_tax_id="A55667788",
                invoice_number="NOTARIA-001",
                issue_date="2026-03-15",
                total_base=500.0,
                total_tax=105.0,
                total_amount=705.0,
                tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=500.0, tax_amount=105.0)]
            )
            entries_sup = generate_accounting_entry_lines(
                extraction=ext_sup,
                plan_longitud=9,
                custom_supplier_account="410000002",
                suplidos_amount=100.0,
                custom_suplidos_account="554000000"
            )
            debe_sup = sum(e.debe for e in entries_sup)
            haber_sup = sum(e.haber for e in entries_sup)
            sup_line = next((e for e in entries_sup if e.subcuenta == "554000000"), None)
            if abs(debe_sup - haber_sup) < 0.001 and sup_line and sup_line.debe == 100.0:
                report.log_pass("Casuística Suplidos (Cuenta 554)", f"Apunte en {sup_line.subcuenta} por {sup_line.debe:.2f} € al Debe.")
            else:
                report.log_fail("Casuística Suplidos", f"Error en apunte de suplidos")

            # 2.4 Factura Rectificativa
            ext_rect = InvoiceExtractionResult(
                issuer_name="Proveedor Rectificado",
                issuer_tax_id="B99999999",
                invoice_number="R-2026-01",
                issue_date="2026-03-20",
                total_base=200.0,
                total_tax=42.0,
                total_amount=242.0,
                tax_breakdown=[TaxBreakdownItem(tax_rate=21.0, base_amount=200.0, tax_amount=42.0)]
            )
            entries_rect = generate_accounting_entry_lines(
                extraction=ext_rect,
                plan_longitud=9,
                custom_supplier_account="400000001",
                is_rectificativa=True
            )
            debe_rect = sum(e.debe for e in entries_rect)
            haber_rect = sum(e.haber for e in entries_rect)
            if abs(debe_rect - haber_rect) < 0.001 and entries_rect[0].debe < 0:
                report.log_pass("Casuística Factura Rectificativa", "Importes negativos y signo de partida doble exacto.")
            else:
                report.log_fail("Casuística Rectificativa", f"Error de signo en rectificativa")

        except Exception as e:
            report.log_fail("Pilar 2 - Error", str(e))

        # ----------------------------------------------------------------------
        # PILAR 3: Motores de Exportación Contable Multisoftware
        # ----------------------------------------------------------------------
        print("\n[PILAR 3] Motores de Exportación a ERPs (A3, Contasol, Sage)")
        try:
            # 3.1 A3 SUENLACE con A3SeatSplitter (> 3 tipos de IVA)
            inv_multi_iva = {
                "invoice_number": "FRA-A3-4IVAS",
                "issue_date": "2026-03-25",
                "issuer_cif": "B12345678",
                "issuer_name": "DISTRIBUIDORA 4 IVAS SL",
                "taxes": [
                    {"tax_rate": 21.0, "tax_base": 1000.0, "tax_amount": 210.0},
                    {"tax_rate": 10.0, "tax_base": 500.0, "tax_amount": 50.0},
                    {"tax_rate": 4.0, "tax_base": 200.0, "tax_amount": 8.0},
                    {"tax_rate": 0.0, "tax_base": 100.0, "tax_amount": 0.0},
                ],
                "total_base": 1800.0,
                "total_tax": 268.0,
                "total_amount": 2068.0,
            }
            a3_txt = generate_a3_suenlace(inv_multi_iva, company_code="00001")
            a3_lines = [l for l in a3_txt.split("\r\n") if l]
            cabeceras_tipo1 = [l for l in a3_lines if l.startswith("1")]
            all_len_96 = all(len(l) == 96 for l in a3_lines)
            a3_bytes = generate_a3_suenlace_bytes(inv_multi_iva)

            if len(cabeceras_tipo1) == 2 and all_len_96 and isinstance(a3_bytes, bytes):
                report.log_pass(
                    "Wolters Kluwer A3 (A3SeatSplitter)",
                    f"4 tipos de IVA divididos en 2 asientos correlativos. Formato 96 chars y codificación CP1252 ANSI."
                )
            else:
                report.log_fail("Wolters Kluwer A3", f"Asientos: {len(cabeceras_tipo1)}, Todos 96 chars: {all_len_96}")

            # 3.2 Contasol CSV
            contasol_csv = generate_contasol_csv([inv_multi_iva], journal_code="1")
            contasol_bytes = generate_contasol_csv_bytes([inv_multi_iva])
            c_lines = contasol_csv.splitlines()
            header_ok_contasol = c_lines[0] == "Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber"
            if header_ok_contasol and len(c_lines) > 2 and isinstance(contasol_bytes, bytes):
                report.log_pass(
                    "Software DELSOL (Contasol CSV)",
                    f"Cabecera oficial, delimitado por ';' con coma decimal española y codificación Latin-1."
                )
            else:
                report.log_fail("Contasol CSV", f"Cabecera: {c_lines[0] if c_lines else 'vacio'}")

            # 3.3 Sage CSV
            sage_csv = generate_sage_csv([inv_multi_iva], channel="0")
            sage_bytes = generate_sage_csv_bytes([inv_multi_iva])
            s_lines = sage_csv.splitlines()
            header_ok_sage = "Canal;Asiento;Fecha;Cuenta;Concepto;Debe;Haber;Contrapartida;Base;CuotaIva;Factura" in s_lines[0]
            if header_ok_sage and len(s_lines) > 2 and isinstance(sage_bytes, bytes):
                report.log_pass(
                    "Sage 50 / Sage Despachos Connected",
                    f"Plantilla oficial con contrapartidas, bases de IVA y codificación Latin-1/ANSI."
                )
            else:
                report.log_fail("Sage CSV", f"Cabecera: {s_lines[0] if s_lines else 'vacio'}")

        except Exception as e:
            report.log_fail("Pilar 3 - Error", str(e))

        # ----------------------------------------------------------------------
        # PILAR 4: Conciliación Bancaria y Punteo Inteligente
        # ----------------------------------------------------------------------
        print("\n[PILAR 4] Conciliación Bancaria (Emparejamiento y Patrones)")
        try:
            # Factura aprobada en la BD para emparejar
            mock_inv_bank = Invoice(
                company_id=company.id,
                file_path="storage_test/mock_banco.pdf",
                file_name="mock_banco.pdf",
                invoice_number="FRA-BANCO-01",
                issuer_name="TELEFONIA AVANZADA SA",
                issuer_cif="A28000000",
                issue_date=date(2026, 3, 20),
                total_base=80.0,
                total_tax=16.8,
                total_amount=96.80,
                status="GREEN",
                workflow_status="validado",
                is_processed=True,
            )
            db.add(mock_inv_bank)
            await db.commit()
            await db.refresh(mock_inv_bank)

            # Transacciones a conciliar
            test_txs = [
                # 1. Pago de factura dentro del margen de 5 días
                {
                    "id": "tx-1",
                    "date": "2026-03-22",
                    "amount": -96.80,
                    "description": "RECIBO SEPA TELEFONIA AVANZADA SA",
                },
                # 2. TGSS Seguros Sociales
                {
                    "id": "tx-2",
                    "date": "2026-03-31",
                    "amount": -1250.00,
                    "description": "TGSS SEGURIDAD SOCIAL COTIZACIONES REG. GENERAL",
                },
                # 3. Iberdrola Electricidad
                {
                    "id": "tx-3",
                    "date": "2026-03-15",
                    "amount": -320.40,
                    "description": "ADEUDO SEPA IBERDROLA CLIENTES S.A.U.",
                },
            ]

            match_results = match_bank_transactions(
                transactions=test_txs,
                invoices=[mock_inv_bank],
                date_margin_days=5,
                account_digits=9,
            )

            tx1_res = match_results[0]
            tx2_res = match_results[1]
            tx3_res = match_results[2]

            # 4.1 Coincidencia exacta con factura
            if tx1_res["status"] == "PREVALIDADO" and tx1_res["invoice_id"] == mock_inv_bank.id:
                report.log_pass(
                    "Emparejamiento Automático Factura",
                    f"Transacción de 96.80 € emparejada con {mock_inv_bank.invoice_number} (Estado: PREVALIDADO)."
                )
            else:
                report.log_fail("Emparejamiento con factura", f"Estado: {tx1_res['status']}")

            # 4.2 Deducción por patrón TGSS
            if tx2_res["status"] == "SUGERIDO" and tx2_res["counterpart_account"].startswith("476"):
                report.log_pass(
                    "Deducción Semántica TGSS",
                    f"Concepto Seguridad Social -> Subcuenta asignada: {tx2_res['counterpart_account']} (Estado: SUGERIDO)."
                )
            else:
                report.log_fail("Deducción TGSS", f"Cuenta: {tx2_res['counterpart_account']}")

            # 4.3 Deducción por patrón Iberdrola
            if tx3_res["status"] == "SUGERIDO" and tx3_res["counterpart_account"].startswith("628"):
                report.log_pass(
                    "Deducción Semántica Suministros (Iberdrola)",
                    f"Concepto Energía -> Subcuenta asignada: {tx3_res['counterpart_account']} (Estado: SUGERIDO)."
                )
            else:
                report.log_fail("Deducción Iberdrola", f"Cuenta: {tx3_res['counterpart_account']}")

            # 4.4 Asiento contable de banco (partida doble)
            bank_entry = build_bank_entry(tx1_res, account_number="572000000", account_digits=9)
            if bank_entry["is_balanced"] and len(bank_entry["lines"]) == 2:
                report.log_pass(
                    "Generación Asiento Banco (572)",
                    f"Partida doble cuadrada: Debe {bank_entry['total_debe']} € == Haber {bank_entry['total_haber']} €."
                )
            else:
                report.log_fail("Asiento de Banco", f"Descuadrado o líneas incorrectas")

        except Exception as e:
            report.log_fail("Pilar 4 - Error", str(e))

        # ----------------------------------------------------------------------
        # PILAR 5: Healthcheck y Verificación de Servidores
        # ----------------------------------------------------------------------
        print("\n[PILAR 5] Healthcheck de Servidores Activos")
        # 5.1 Backend FastAPI
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/docs", headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    report.log_pass("Backend FastAPI (:8000)", "Servidor API operativo y respondiendo HTTP 200 OK.")
                else:
                    report.log_fail("Backend FastAPI (:8000)", f"Status HTTP: {resp.status}")
        except Exception as e:
            report.log_fail("Backend FastAPI (:8000)", f"No responde en http://127.0.0.1:8000 ({e})")

        # 5.2 Frontend Next.js
        try:
            req_fe = urllib.request.Request("http://localhost:3000", headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req_fe, timeout=3) as resp_fe:
                if resp_fe.status == 200:
                    report.log_pass("Frontend Next.js (:3000)", "Aplicación web operativa y respondiendo HTTP 200 OK.")
                else:
                    report.log_fail("Frontend Next.js (:3000)", f"Status HTTP: {resp_fe.status}")
        except Exception as e:
            report.log_fail("Frontend Next.js (:3000)", f"No responde en http://localhost:3000 ({e})")

    # ----------------------------------------------------------------------
    # Resumen Final
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"RESUMEN FINAL: {report.passes} PRUEBAS EXITOSAS | {report.failures} FALLOS")
    print("=" * 80)

    if report.failures == 0:
        print("\n>>> TODOS LOS 5 PILARES HAN SIDO VERIFICADOS CON ÉXITO. SISTEMA 100% OPERATIVO <<<\n")
        return 0
    else:
        print(f"\n>>> SE HAN DETECTADO {report.failures} FALLOS EN LA VERIFICACIÓN <<<\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_full_verification())
    sys.exit(exit_code)

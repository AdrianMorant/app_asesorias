import asyncio
import os
import io
import pymupdf
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.api.v1.endpoints.invoices import (
    get_invoice_pages,
    get_page_thumbnail,
    split_invoice,
)
from app.schemas.invoice_dto import SplitInvoiceRequestDTO, SplitGroupDTO


async def run_tests():
    print("=== TEST FASE 1: MAQUETADOR MULTI-FACTURA (MF) Y MÁQUINA DE ESTADOS ===")

    # 1. Inicializar base de datos
    await init_db()
    print("-> Base de datos inicializada y migraciones ligeras aplicadas.")

    async with AsyncSessionLocal() as db:
        # Asegurar empresa de prueba
        res = await db.execute(select(Company))
        company = res.scalars().first()
        if not company:
            company = Company(
                cif="B99887766",
                razon_social="EMPRESA TEST FASE 1 S.L.",
                plan_cuentas_longitud=9,
                storage_base_path="storage",
                iva_periodicity="Trimestral",
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)

        # 2. Generar un PDF sintético de 3 páginas con PyMuPDF
        doc = pymupdf.open()
        p1 = doc.new_page()
        p1.insert_text((50, 50), "FACTURA F-001\nProveedor: SUMINISTROS ENERGETICOS S.L.\nCIF: B12345678\nBase: 100.00 EUR\nIVA 21%: 21.00 EUR\nTotal: 121.00 EUR")

        p2 = doc.new_page()
        p2.insert_text((50, 50), "FACTURA F-002\nProveedor: CONSULTORIA DIGITAL S.L.\nCIF: B87654321\nBase: 200.00 EUR\nIVA 21%: 42.00 EUR\nTotal: 242.00 EUR")

        p3 = doc.new_page()
        p3.insert_text((50, 50), "PAGINA DE PUBLICIDAD O ANEXO EN BLANCO\n(Descartable)")

        test_storage_dir = os.path.join("storage", company.cif, "2026", "1T", "Gastos")
        os.makedirs(test_storage_dir, exist_ok=True)
        test_pdf_path = os.path.join(test_storage_dir, "lote_multifacturas_test.pdf")
        doc.save(test_pdf_path)
        doc.close()
        print(f"-> PDF de prueba generado con 3 páginas en: {test_pdf_path}")

        # 3. Registrar documento en la base de datos simulando upload multi-página
        parent_invoice = Invoice(
            company_id=company.id,
            file_name="lote_multifacturas_test.pdf",
            file_path=test_pdf_path,
            invoice_number="LOTE-001",
            issuer_name="Lote Múltiple",
            issuer_cif="B00000000",
            total_base=300.0,
            total_tax=63.0,
            total_amount=363.0,
            status="YELLOW",
            workflow_status="a_revisar",
            es_multifactura=True,
            num_paginas=3,
        )
        db.add(parent_invoice)
        await db.commit()
        await db.refresh(parent_invoice)

        print(f"-> Factura padre creada: ID={parent_invoice.id}, es_multifactura={parent_invoice.es_multifactura}, workflow_status={parent_invoice.workflow_status}, num_paginas={parent_invoice.num_paginas}")
        assert parent_invoice.es_multifactura is True, "Debe ser multifactura"
        assert parent_invoice.workflow_status == "a_revisar", "Estado debe ser a_revisar"
        assert parent_invoice.num_paginas == 3, "Debe tener 3 páginas"

        # 4. Probar endpoint de páginas
        pages_dto = await get_invoice_pages(invoice_id=parent_invoice.id, db=db)
        print(f"-> Páginas detectadas en endpoint /pages: {pages_dto.num_paginas} (total: {len(pages_dto.pages)})")
        assert pages_dto.num_paginas == 3
        assert len(pages_dto.pages) == 3

        # 5. Probar generación de miniatura de la página 1
        thumb_response = await get_page_thumbnail(invoice_id=parent_invoice.id, page_number=1, db=db)
        assert thumb_response.media_type == "image/png"
        assert len(thumb_response.body) > 0
        print(f"-> Miniatura de página 1 generada exitosamente ({len(thumb_response.body)} bytes, PNG).")

        # 6. Probar endpoint de split: separar pág 1 en Factura 1, pág 2 en Factura 2, pág 3 descartada
        split_request = SplitInvoiceRequestDTO(
            splits=[
                SplitGroupDTO(custom_name="Factura Luz", page_numbers=[1]),
                SplitGroupDTO(custom_name="Factura Asesoría", page_numbers=[2]),
            ]
        )

        sub_invoices = await split_invoice(
            invoice_id=parent_invoice.id,
            payload=split_request,
            db=db
        )

        print(f"-> Disgregación completada. Sub-facturas generadas: {len(sub_invoices)}")
        assert len(sub_invoices) == 2, f"Se esperaban 2 sub-facturas, se obtuvieron {len(sub_invoices)}"

        for idx, sub in enumerate(sub_invoices, start=1):
            expected_name_pattern = f"_factura_{idx}.pdf"
            print(f"   Sub-factura {idx}: ID={sub.id}, file_name={sub.file_name}, parent_id={sub.parent_invoice_id}, pages={sub.num_paginas}, workflow_status={sub.workflow_status}")
            assert expected_name_pattern in sub.file_name, f"El archivo debe seguir el patrón [original]_factura_[index].pdf, tiene {sub.file_name}"
            assert sub.parent_invoice_id == parent_invoice.id, f"El parent_invoice_id debe apuntar a {parent_invoice.id}"
            assert sub.num_paginas == 1, "Cada sub-factura debe tener 1 página"
            assert os.path.exists(sub.file_path), f"El fichero físico debe existir en {sub.file_path}"

        # 7. Comprobar que la factura padre quedó archivada y marcada como multifactura
        await db.refresh(parent_invoice)
        print(f"-> Factura padre final: workflow_status={parent_invoice.workflow_status}, is_processed={parent_invoice.is_processed}")
        assert parent_invoice.workflow_status == "archivado", "Factura padre debe pasar a estado archivado tras split"
        assert parent_invoice.is_processed is True, "Factura padre debe marcarse como procesada"

    print("\n[OK] TODOS LOS TESTS DE LA FASE 1 HAN PASADO CON EXITO.")


if __name__ == "__main__":
    asyncio.run(run_tests())

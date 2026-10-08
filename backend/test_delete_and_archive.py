import requests
import io
import os
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"

def test_delete_and_archive_flow():
    print("=== TEST: VALIDACIÓN DE BORRADO DE FACTURA Y RUTA ANTES DE ARCHIVAR ===")
    
    # 1. Obtener empresas
    res_comps = requests.get(f"{BASE_URL}/companies")
    assert res_comps.status_code == 200, f"Error listando empresas: {res_comps.text}"
    companies = res_comps.json()
    assert len(companies) > 0, "No hay empresas en la base de datos"
    company = companies[0]
    company_id = company["id"]
    print(f"1. Empresa seleccionada: {company['razon_social']} ({company['cif']})")

    # 2. Subir una factura dummy para la prueba
    dummy_pdf_content = b"%PDF-1.4 dummy invoice test content for deletion and archive"
    files = {"file": ("factura_test_flujo.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")}
    data = {"company_id": company_id}
    print("2. Subiendo factura de prueba...")
    res_upload = requests.post(f"{BASE_URL}/invoices/upload", files=files, data=data)
    assert res_upload.status_code == 201, f"Error al subir factura: {res_upload.text}"
    invoice = res_upload.json()
    invoice_id = invoice["id"]
    file_path = invoice["file_path"]
    print(f" -> Factura creada con ID: {invoice_id}")
    print(f" -> Archivo físico generado en: {file_path}")
    assert Path(file_path).exists(), "El archivo físico debería existir en disco tras subirlo"

    # 3. Probar obtención de ruta propuesta antes de archivar (REQUISITO 2)
    print("\n3. Solicitando ruta propuesta antes de archivar (GET /invoices/{id}/proposed-archive-path)...")
    res_prop = requests.get(f"{BASE_URL}/invoices/{invoice_id}/proposed-archive-path")
    assert res_prop.status_code == 200, f"Error al obtener ruta propuesta: {res_prop.text}"
    prop_data = res_prop.json()
    print(f" -> Ruta base: {prop_data['base_path']}")
    print(f" -> Subcarpeta propuesta: {prop_data['subfolder']}")
    print(f" -> Nombre de archivo propuesto: {prop_data['filename']}")
    print(f" -> Ruta completa: {prop_data['full_path']}")
    assert prop_data["filename"].endswith(".pdf")
    assert company["cif"] in prop_data["subfolder"]

    # 4. Probar aprobación con ruta personalizada antes de archivar (REQUISITO 2)
    custom_sub = f"storage/{company['cif']}/2026/1T/recibidas_personalizadas"
    custom_fn = f"2026-03-01_{company['cif']}_CUSTOM-001.pdf"
    print(f"\n4. Aprobando y archivando con ruta personalizada:\n   Subcarpeta: {custom_sub}\n   Archivo: {custom_fn}")
    res_approve = requests.post(
        f"{BASE_URL}/invoices/{invoice_id}/approve",
        json={"custom_subfolder": custom_sub, "custom_filename": custom_fn}
    )
    assert res_approve.status_code == 200, f"Error al aprobar con ruta personalizada: {res_approve.text}"
    approved_invoice = res_approve.json()
    new_path = approved_invoice["file_path"]
    print(f" -> Factura aprobada. Nuevo file_path: {new_path}")
    assert approved_invoice["is_processed"] is True
    assert Path(new_path).exists(), f"El archivo movido {new_path} debe existir físicamente en disco"
    assert "CUSTOM-001.pdf" in new_path, "El archivo debe tener el nombre personalizado asignado"

    # 5. Probar borrado físico de la factura (REQUISITO 1)
    print(f"\n5. Eliminando la factura (DELETE /invoices/{invoice_id})...")
    res_del = requests.delete(f"{BASE_URL}/invoices/{invoice_id}")
    assert res_del.status_code == 200, f"Error al eliminar factura: {res_del.text}"
    del_result = res_del.json()
    print(f" -> Respuesta de borrado: {del_result}")
    assert del_result["success"] is True
    assert del_result["file_deleted"] is True, "El fichero físico debía ser eliminado"
    assert not Path(new_path).exists(), "El archivo físico NO debe existir en disco tras el borrado"

    # Verificar que ya no existe en la base de datos
    res_check = requests.get(f"{BASE_URL}/invoices/{invoice_id}")
    assert res_check.status_code == 404, "La factura no debe existir en la BD tras ser eliminada"
    print(" -> Comprobado en BD: Código HTTP 404 (Factura no encontrada).")

    print("\n=== TODAS LAS PRUEBAS DE BORRADO Y RUTA DE ARCHIVADO COMPLETADAS CON ÉXITO (100% OK) ===")

if __name__ == "__main__":
    test_delete_and_archive_flow()

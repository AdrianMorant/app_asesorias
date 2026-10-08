import io
from fastapi.testclient import TestClient
from app.main import app

def test_api():
    print("Iniciando prueba del endpoint POST /api/v1/invoices/upload...")
    client = TestClient(app)

    # 1. Comprobar health check
    res = client.get("/")
    assert res.status_code == 200
    print("[1] Health check OK:", res.json())

    # 2. Crear una empresa vía API
    comp_payload = {
        "cif": "B87654323",
        "razon_social": "Soluciones Digitales S.L.",
        "plan_cuentas_longitud": 9
    }
    comp_res = client.post("/api/v1/companies", json=comp_payload)
    if comp_res.status_code == 201:
        company_id = comp_res.json()["id"]
    else:
        companies_res = client.get("/api/v1/companies")
        company_id = companies_res.json()[0]["id"]
    print(f"[2] Empresa obtenida/creada: ID {company_id}")

    # 3. Dar de alta un proveedor
    supp_payload = {
        "company_id": company_id,
        "cif": "B12345674",
        "nombre": "Suministros del Norte S.L.",
        "subcuenta_proveedor": "400000001",
        "subcuenta_gasto_defecto": "629000001"
    }
    supp_res = client.post("/api/v1/suppliers", json=supp_payload)
    print(f"[3] Creación/verificación de proveedor: {supp_res.status_code}")

    # 4. Probar subida de factura (simulando PDF o imagen)
    dummy_pdf_content = b"%PDF-1.4 ... Factura de prueba ..."
    files = {
        "file": ("factura_001.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")
    }
    data = {
        "company_id": company_id
    }
    
    upload_res = client.post("/api/v1/invoices/upload", files=files, data=data)
    print(f"[4] Subida e ingesta de factura: status {upload_res.status_code}")
    assert upload_res.status_code == 201
    invoice_resp = upload_res.json()
    print("    ID Factura:", invoice_resp["id"])
    print("    Número:", invoice_resp["invoice_number"])
    print("    Emisor:", invoice_resp["issuer_name"], f"({invoice_resp['issuer_cif']})")
    print("    Total:", invoice_resp["total_amount"], "EUR")
    print("    Semáforo:", invoice_resp["status"])
    print("    Motivos del semáforo:", invoice_resp["status_reasons"])
    print("    Apuntes contables generados:", len(invoice_resp["accounting_entries"]))
    for line in invoice_resp["accounting_entries"]:
        print(f"       Subcuenta: {line['subcuenta']} | Debe: {line['debe']} | Haber: {line['haber']} | {line['concepto']}")

    # 5. Listar facturas
    list_res = client.get(f"/api/v1/invoices?company_id={company_id}")
    assert list_res.status_code == 200
    print(f"[5] Total facturas listadas: {len(list_res.json())}")

    # 6. Aprobar factura
    invoice_id = invoice_resp["id"]
    approve_res = client.post(f"/api/v1/invoices/{invoice_id}/approve")
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["is_processed"] is True
    print(f"[6] Factura {invoice_id} aprobada con éxito.")
    print(f"    Ruta de archivado automático: {approved_data['file_path']}")
    assert "storage" in approved_data["file_path"], "La factura no se archivó en la carpeta storage"
    assert "recibidas" in approved_data["file_path"], "La factura no se archivó en la subcarpeta 'recibidas'"

    # 7. Exportar Contasol CSV y A3 SUENLACE
    contasol_res = client.get(f"/api/v1/exports/contasol?company_id={company_id}")
    assert contasol_res.status_code == 200
    print(f"[7] Exportación Contasol CSV descargada con éxito ({len(contasol_res.text)} bytes).")

    a3_res = client.get(f"/api/v1/exports/a3-suenlace?company_id={company_id}")
    assert a3_res.status_code == 200
    print(f"[8] Exportación A3 SUENLACE.DAT descargada con éxito ({len(a3_res.text)} bytes).")

    print("\n¡Prueba completa del API REST terminada con 100% de éxito!")

if __name__ == "__main__":
    test_api()

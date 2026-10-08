import requests
import io
from pathlib import Path
from app.services.extractor_llm import convert_pdf_to_images
from app.services.pyme_pgc_seed import expand_account_code

BASE_URL = "http://localhost:8000/api/v1"

def test_critical_fixes():
    print("=== INICIANDO VALIDACIÓN DE LOS 3 PROBLEMAS CRÍTICOS ===")

    # -------------------------------------------------------------
    # 1. VERIFICACIÓN DE EXTRACCIÓN REAL: NO INVENTAR DATOS SI NO HAY API KEY
    # -------------------------------------------------------------
    print("\n--- 1. EXTRACCIÓN REAL: VALIDACIÓN DE ERROR EXPLÍCITO SIN API KEY ---")
    res_comps = requests.get(f"{BASE_URL}/companies")
    assert res_comps.status_code == 200
    companies = res_comps.json()
    assert len(companies) > 0
    company = companies[0]
    
    # Subir un PDF de prueba sin API key en .env
    pdf_dummy = b"%PDF-1.4 1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj 2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj 3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj xref 0 4 0000000000 65535 f 0000000010 00000 n 0000000060 00000 n 0000000117 00000 n trailer << /Size 4 /Root 1 0 R >> startxref 190 %%EOF"
    files = {"file": ("factura_sin_llave.pdf", io.BytesIO(pdf_dummy), "application/pdf")}
    data = {"company_id": company["id"]}
    
    res_upload = requests.post(f"{BASE_URL}/invoices/upload", files=files, data=data)
    print(f" -> Respuesta de subida sin clave de API: HTTP {res_upload.status_code}")
    print(f" -> Detalle devuelto al usuario: {res_upload.text}")
    assert res_upload.status_code == 400, "Debe rechazar con HTTP 400 en lugar de inventar datos"
    assert "backend/.env" in res_upload.text or "GEMINI_API_KEY" in res_upload.text, "Debe avisar claramente de la falta de clave en .env"
    print(" [OK] Verificado: El sistema ya no inventa datos mock y notifica la ausencia de clave de API.")

    # -------------------------------------------------------------
    # 2. VERIFICACIÓN DE PYMUPDF: RASTERIZACIÓN VISUAL DE PDF A IMÁGENES
    # -------------------------------------------------------------
    print("\n--- 2. CONVERSIÓN VISUAL DE PDF A IMÁGENES CON PYMUPDF (FITZ) ---")
    images = convert_pdf_to_images(pdf_dummy, max_pages=3)
    print(f" -> Páginas rasterizadas a PNG de alta resolución: {len(images)}")
    assert len(images) > 0, "PyMuPDF debe generar imágenes PNG del PDF"
    assert images[0].startswith(b"\x89PNG"), "El formato debe ser PNG válido"
    print(" [OK] Verificado: PyMuPDF rasteriza páginas a PNG para análisis visual multimodal.")

    # -------------------------------------------------------------
    # 3. VERIFICACIÓN DEL CATÁLOGO COMPLETO DEL PGC PYMES (ESPAÑA)
    # -------------------------------------------------------------
    print("\n--- 3. CATÁLOGO COMPLETO DEL PLAN GENERAL CONTABLE PYME ---")
    # Probar expansión a 8, 9 y 10 dígitos
    assert expand_account_code("628", 9) == "628000000"
    assert expand_account_code("628", 8) == "62800000"
    assert expand_account_code("628", 10) == "6280000000"
    assert expand_account_code("472.21", 9) == "472000021"
    assert expand_account_code("472.10", 9) == "472000010"
    assert expand_account_code("4751", 9) == "475100000"
    print(" -> Algoritmo de normalización de subcuentas a 8, 9 y 10 dígitos verificado.")

    # Precargar/sembrar cuentas en la empresa
    res_seed = requests.post(f"{BASE_URL}/companies/{company['id']}/chart-of-accounts/seed")
    print(f" -> Siembra de cuentas PGC: HTTP {res_seed.status_code} - {res_seed.json()}")
    assert res_seed.status_code == 200

    # Consultar cuentas de gastos (Grupo 6)
    res_gastos = requests.get(f"{BASE_URL}/companies/{company['id']}/accounts?tipo=GASTO&page_size=100")
    assert res_gastos.status_code == 200
    gastos = res_gastos.json()["items"]
    print(f" -> Cuentas de Gastos (Grupo 6) encontradas: {len(gastos)}")
    gastos_codes = [g["codigo"] for g in gastos]
    assert any(c.startswith("600") for c in gastos_codes), "Debe incluir 600 (Compras)"
    assert any(c.startswith("621") for c in gastos_codes), "Debe incluir 621 (Arrendamientos)"
    assert any(c.startswith("623") for c in gastos_codes), "Debe incluir 623 (Profesionales)"
    assert any(c.startswith("628") for c in gastos_codes), "Debe incluir 628 (Suministros)"
    assert any(c.startswith("629") for c in gastos_codes), "Debe incluir 629 (Otros servicios)"
    assert any(c.startswith("640") for c in gastos_codes), "Debe incluir 640 (Sueldos)"

    # Consultar cuentas de Acreedores y Tributarias (Grupo 4)
    res_trib = requests.get(f"{BASE_URL}/companies/{company['id']}/accounts?tipo=TRIBUTARIO&page_size=100")
    assert res_trib.status_code == 200
    trib = res_trib.json()["items"]
    print(f" -> Cuentas Tributarias encontradas: {len(trib)}")
    trib_codes = [t["codigo"] for t in trib]
    assert any(c.startswith("472") for c in trib_codes), "Debe incluir 472 (IVA soportado)"
    assert any(c.startswith("4751") for c in trib_codes), "Debe incluir 4751 (Retenciones IRPF)"
    assert any(c.startswith("477") for c in trib_codes), "Debe incluir 477 (IVA repercutido)"

    # Consultar cuentas de Tesorería (Grupo 5)
    res_fin = requests.get(f"{BASE_URL}/companies/{company['id']}/accounts?tipo=FINANCIERO&page_size=100")
    assert res_fin.status_code == 200
    fin = res_fin.json()["items"]
    print(f" -> Cuentas de Tesorería encontradas: {len(fin)}")
    fin_codes = [f["codigo"] for f in fin]
    assert any(c.startswith("570") for c in fin_codes), "Debe incluir 570 (Caja)"
    assert any(c.startswith("572") for c in fin_codes), "Debe incluir 572 (Bancos c/c)"

    print(" [OK] Verificado: El catálogo completo del PGC PYMES está precargado y adaptado a los dígitos de la empresa.")

    print("\n=== TODOS LOS CASOS DE PRUEBA HAN SIDO SATISFECHOS AL 100% ===")

if __name__ == "__main__":
    test_critical_fixes()

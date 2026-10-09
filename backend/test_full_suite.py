import requests
import io
import json

BASE_URL = "http://localhost:8000/api/v1"

def run_tests():
    print("=== INICIANDO SUITE DE PRUEBAS AUTOMATIZADAS ===")
    
    # 1. Crear Empresa de Prueba (CIF válido con dígito de control 2)
    test_cif = "B99887762"
    print(f"\n1. Limpiando y preparando empresa de prueba ({test_cif})...")
    # Limpiar si ya existía de una ejecución anterior
    res_list = requests.get(f"{BASE_URL}/companies")
    if res_list.status_code == 200:
        for c in res_list.json():
            if c["cif"] == test_cif:
                requests.delete(f"{BASE_URL}/companies/{c['id']}", json={"cif_confirmation": test_cif})
                print(f" -> Empresa anterior {test_cif} eliminada para prueba limpia.")

    res = requests.post(f"{BASE_URL}/companies", json={
        "cif": test_cif,
        "razon_social": "Empresa Automatizada Test S.L.",
        "plan_cuentas_longitud": 9,
        "storage_base_path": "storage_test"
    })
    assert res.status_code == 201, f"Error creando empresa: {res.text}"
    company = res.json()
    company_id = company["id"]
    print(f" -> Empresa creada con ID: {company_id}, longitud: {company['plan_cuentas_longitud']}")

    # 2. Validación de longitud estricta de cuentas contables
    print("\n2. Probando validación estricta de longitud de cuentas...")
    # 8 dígitos en empresa de 9 dígitos -> Debe fallar
    res_bad = requests.post(f"{BASE_URL}/companies/{company_id}/accounts", json={
        "codigo": "60000001", # 8 dígitos
        "descripcion": "Compras Mercaderías Inválida",
        "tipo": "GASTO_6"
    })
    print(f" -> Código de 8 dígitos devuelto: HTTP {res_bad.status_code} ({res_bad.text})")
    assert res_bad.status_code == 400, "Debería haber fallado por longitud errónea"

    # 9 dígitos en empresa de 9 dígitos -> Debe tener éxito
    res_good = requests.post(f"{BASE_URL}/companies/{company_id}/accounts", json={
        "codigo": "600000001", # 9 dígitos exactos
        "descripcion": "Compras Mercaderías Válida",
        "tipo": "GASTO_6"
    })
    assert res_good.status_code == 201, f"Error creando cuenta válida: {res_good.text}"
    account = res_good.json()
    print(f" -> Cuenta creada correctamente: {account['codigo']} - {account['descripcion']}")

    # 3. Importación masiva de Plan Contable (CSV simulando software contable Contasol / A3 / Sage)
    print("\n3. Probando importación masiva de plan contable vía CSV...")
    csv_content = (
        "codigo;descripcion;cif\n"
        "600000002;Compras de material de oficina;\n"
        "628000001;Suministros eléctricos;\n"
        "400000001;Iberdrola Clientes S.A.U.;A95748356\n"
        "410000001;Vodafone España S.A.U.;A82269950\n"
        "430000001;Cliente Principal S.L.;B12345674\n"
        "700000001;Ventas de prestaciones y servicios;\n"
    )
    files = {"file": ("sumas_y_saldos_contasol.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res_import = requests.post(f"{BASE_URL}/companies/{company_id}/chart-of-accounts/import", files=files)
    assert res_import.status_code == 200, f"Error en importación: {res_import.text}"
    import_summary = res_import.json()
    assert (import_summary['created'] + import_summary.get('updated', 0)) >= 5, "Deberían haberse procesado (creadas/actualizadas) las cuentas del CSV"

    # 4. Exportación del Plan Contable a CSV normalizado
    print("\n4. Probando exportación del catálogo completo normalizado...")
    res_export = requests.get(f"{BASE_URL}/companies/{company_id}/chart-of-accounts/export")
    assert res_export.status_code == 200, f"Error exportando cuentas: {res_export.text}"
    assert "Content-Disposition" in res_export.headers
    print(f" -> Exportación correcta (Bytes: {len(res_export.content)})")

    # 5. Listado y paginación de cuentas con filtros
    print("\n5. Probando consulta paginada y filtrado...")
    res_list = requests.get(f"{BASE_URL}/companies/{company_id}/accounts?tipo=PROVEEDOR_400")
    assert res_list.status_code == 200
    list_data = res_list.json()
    print(f" -> Cuentas de proveedores encontradas: {len(list_data['items'])}")
    assert any("400" in a["codigo"] for a in list_data['items'])

    # 6. Edición de empresa (Ruta de almacenamiento y longitud)
    print("\n6. Actualizando datos de la empresa (storage_base_path)...")
    res_update_comp = requests.put(f"{BASE_URL}/companies/{company_id}", json={
        "razon_social": "Empresa Automatizada Test Renovada S.L.",
        "storage_base_path": "storage/red_corporativa/asesoria"
    })
    assert res_update_comp.status_code == 200
    comp_updated = res_update_comp.json()
    print(f" -> Empresa actualizada: storage_base_path={comp_updated['storage_base_path']}")

    # 7. Borrado de facturas en lote
    print("\n7. Probando endpoint de borrado de facturas en lote con lista vacía / ficticia...")
    res_bulk = requests.post(f"{BASE_URL}/invoices/bulk-delete", json={"invoice_ids": ["non-existent-id-1", "non-existent-id-2"]})
    assert res_bulk.status_code == 200
    print(f" -> Respuesta borrado en lote: {res_bulk.json()}")

    # 8. Eliminación estricta de empresa con confirmación de CIF
    print("\n8. Probando eliminación con confirmación estricta de CIF...")
    # CIF erróneo
    res_del_bad = requests.delete(f"{BASE_URL}/companies/{company_id}", json={"cif_confirmation": "CIF_INCORRECTO"})
    print(f" -> Intento con CIF erróneo: HTTP {res_del_bad.status_code} ({res_del_bad.text})")
    assert res_del_bad.status_code == 400

    # CIF correcto
    res_del_good = requests.delete(f"{BASE_URL}/companies/{company_id}", json={"cif_confirmation": test_cif})
    assert res_del_good.status_code == 200
    print(f" -> Empresa eliminada con éxito en cascada: {res_del_good.json()}")

    # Verificar que ya no existe
    res_check = requests.get(f"{BASE_URL}/companies/{company_id}")
    assert res_check.status_code == 404
    print(" -> Verificado: la empresa y sus datos han sido eliminados por completo.")

    print("\n=== TODAS LAS PRUEBAS PASARON EXITOSAMENTE (100% OK) ===")

if __name__ == "__main__":
    run_tests()

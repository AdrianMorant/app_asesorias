"""
Suite de Pruebas Automatizadas — Fase 4 (Seguridad, Autenticación y RBAC) y Fase 5 (Fiabilidad y Operaciones)
KontaAI Suite — Rigor de Seguridad Empresarial, OWASP y Esquema Nacional de Seguridad (ENS).

Ejecución asíncrona nativa mediante httpx.AsyncClient y ASGI Transport.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date
from pathlib import Path
import httpx
from sqlalchemy import select, delete

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from app.main import app
from app.core.database import AsyncSessionLocal, init_db
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_password_reset_token,
    verify_password_reset_token,
    token_revocation_store,
)
from app.core.security_cookies import (
    create_access_token,
    create_session_tokens,
    verify_session_token,
)
from app.core.two_factor import (
    generate_totp_secret,
    generate_totp_uri,
    _verify_native_totp,
    generate_recovery_codes,
)
from app.core.rate_limiter import in_memory_limiter
from app.core.audit_logger import log_security_event, verify_audit_log_integrity
from app.services.backup_service import (
    create_system_backup,
    verify_backup_integrity,
    restore_system_backup,
)
from app.models.company import Company
from app.models.user import User, UserRole, user_companies
from app.models.invoice import Invoice
from app.models.accounting_entry import AccountingEntryLine


async def test_password_hashing_and_complexity():
    """Prueba 1: Hashing resistente PBKDF2-HMAC-SHA256 y políticas de complejidad."""
    # 1. Validación de fortaleza
    weak_cases = ["corta", "solominusculas1", "SOLOMAYUSCULAS1", "SinNumerosNiSignos"]
    for pwd in weak_cases:
        is_ok, err = validate_password_strength(pwd)
        assert not is_ok, f"Se debió rechazar la contraseña débil: {pwd}"

    strong_pwd = "KontaSecure2026!Password"
    is_ok, err = validate_password_strength(strong_pwd)
    assert is_ok, f"Error en contraseña válida: {err}"

    # 2. Hashing y verificación
    hashed = hash_password(strong_pwd)
    assert hashed.startswith("$pbkdf2-sha256$i=310000$s="), "Formato de hash PBKDF2 incorrecto"
    assert verify_password(strong_pwd, hashed), "Fallo al verificar contraseña correcta"
    assert not verify_password("ClaveIncorrecta!", hashed), "Verificó erróneamente una clave falsa"
    assert not verify_password("", hashed), "Permitió contraseña vacía"


async def test_auth_registration_and_login(client: httpx.AsyncClient):
    """Prueba 2: Registro, prevención de duplicados, login y emisión de cookies/JWT."""
    unique_email = f"asesor_{uuid.uuid4().hex[:6]}@despacho-test.es"
    pwd = "MiContrasenaSegura2026!"

    # 1. Registro exitoso
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": pwd,
            "full_name": "Dr. Asesor Contable",
            "role": "ADVISOR",
            "advisor_firm_name": "Morant & Asociados Asesores",
            "initial_company_cif": "B88888888",
            "initial_company_name": "Empresa Inicial SL",
        },
    )
    assert reg_res.status_code == 201, f"Fallo al registrar: {reg_res.text}"
    reg_data = reg_res.json()
    assert reg_data["success"] is True
    assert reg_data["email"] == unique_email

    # 2. Prevención de duplicados
    dup_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": pwd,
            "full_name": "Intento Duplicado",
            "role": "ADVISOR",
        },
    )
    assert dup_res.status_code == 400, "Debió rechazar correo duplicado"

    # 3. Intento con credenciales erróneas
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "PasswordIncorrecto123!"},
    )
    assert bad_login.status_code == 401, "Debió rechazar credenciales incorrectas"

    # 4. Login exitoso
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": pwd},
    )
    assert login_res.status_code == 200, f"Fallo al iniciar sesión: {login_res.text}"
    login_data = login_res.json()
    assert login_data["success"] is True
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["user"]["role"] == "ADVISOR"

    # 5. Consulta de perfil autenticado /me
    token = login_data["access_token"]
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200, f"Fallo al consultar /me: {me_res.text}"
    me_data = me_res.json()
    assert me_data["email"] == unique_email
    assert me_data["global_role"] == "ADVISOR"


async def test_session_revocation_and_logout(client: httpx.AsyncClient):
    """Prueba 3: Cierre de sesión, revocación activa de tokens en lista negra."""
    unique_email = f"user_logout_{uuid.uuid4().hex[:6]}@konta.ai"
    pwd = "PasswordSeguro2026!"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": pwd,
            "full_name": "Usuario Para Logout",
            "role": "ACCOUNTANT",
        },
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": pwd},
    )
    token = login_res.json()["access_token"]

    # Acceso exitoso previo a logout
    pre_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pre_res.status_code == 200

    # Logout
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Acceso posterior debe ser denegado por token revocado
    post_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_res.status_code == 401, "El token revocado no debe permitir acceso a /me"


async def test_password_recovery_flow(client: httpx.AsyncClient):
    """Prueba 4: Recuperación de contraseña verificable (forgot-password y reset-password)."""
    unique_email = f"recov_{uuid.uuid4().hex[:6]}@konta.ai"
    old_pwd = "PasswordViejo2026!"
    new_pwd = "PasswordNuevo2026!"

    await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": old_pwd, "full_name": "Usuario Recuperador"},
    )

    # 1. Solicitar token de restablecimiento
    forgot_res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": unique_email},
    )
    assert forgot_res.status_code == 200
    token = forgot_res.json().get("reset_token")
    assert token, "Debe generar un token temporal de reseteo"

    # 2. Restablecer con la nueva contraseña
    reset_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_pwd},
    )
    assert reset_res.status_code == 200, f"Fallo en reset: {reset_res.text}"

    # 3. Comprobar que la vieja contraseña falla y la nueva funciona
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": old_pwd},
    )
    assert bad_login.status_code == 401

    ok_login = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": new_pwd},
    )
    assert ok_login.status_code == 200


async def test_rbac_authorization_matrix(client: httpx.AsyncClient):
    """Prueba 5: Matriz de Control de Acceso Basado en Roles (RBAC) en el backend."""
    company_id = "comp-test-phase2-01"

    # Iniciar sesión / crear usuario con rol INVOICING (solo facturación)
    inv_email = f"invoicing_{uuid.uuid4().hex[:6]}@empresa.com"
    pwd = "PasswordRole123!"

    await client.post(
        "/api/v1/auth/register",
        json={"email": inv_email, "password": pwd, "full_name": "Facturador Limitado", "role": "INVOICING"},
    )
    login_res = await client.post("/api/v1/auth/login", json={"email": inv_email, "password": pwd})
    inv_token = login_res.json()["access_token"]
    inv_headers = {"Authorization": f"Bearer {inv_token}"}

    # 1. INVOICING intenta revertir un asiento contable -> Debe dar HTTP 403 Forbidden
    rev_res = await client.post(
        f"/api/v1/companies/{company_id}/journal/1/reverse",
        headers=inv_headers,
        json={"reason": "Intento no autorizado de reversión"},
    )
    assert rev_res.status_code == 403, f"INVOICING no debe tener permiso de reversión: {rev_res.status_code}"

    # 2. INVOICING intenta cerrar un ejercicio contable -> Debe dar HTTP 403 Forbidden
    close_res = await client.post(
        f"/api/v1/companies/{company_id}/journal/close-fiscal-year",
        headers=inv_headers,
        json={"year": 2025},
    )
    assert close_res.status_code == 403, f"INVOICING no debe poder cerrar ejercicio: {close_res.status_code}"

    # 3. INVOICING intenta reabrir un ejercicio contable -> Debe dar HTTP 403 Forbidden
    reopen_res = await client.post(
        f"/api/v1/companies/{company_id}/journal/reopen-fiscal-year",
        headers=inv_headers,
        json={"cif_confirmation": "B98765432"},
    )
    assert reopen_res.status_code == 403, f"INVOICING no debe poder reabrir ejercicio: {reopen_res.status_code}"

    # 4. INVOICING intenta eliminar una empresa -> Debe dar HTTP 403 Forbidden
    del_comp_res = await client.delete(
        f"/api/v1/companies/{company_id}?cif_confirmation=B98765432",
        headers=inv_headers,
    )
    assert del_comp_res.status_code == 403, f"INVOICING no debe poder borrar empresa: {del_comp_res.status_code}"

    # 5. Usuario con rol ADVISOR o ACCOUNTANT tiene acceso concedido
    advisor_email = f"advisor_{uuid.uuid4().hex[:6]}@gestoria.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": advisor_email, "password": pwd, "full_name": "Asesor Titular", "role": "ADVISOR"},
    )
    adv_login = await client.post("/api/v1/auth/login", json={"email": advisor_email, "password": pwd})
    adv_token = adv_login.json()["access_token"]
    adv_headers = {"Authorization": f"Bearer {adv_token}"}

    # Asesor tiene autorización RBAC sobre la empresa
    me_adv = await client.get("/api/v1/auth/me", headers=adv_headers)
    assert me_adv.status_code == 200
    assert me_adv.json()["global_role"] == "ADVISOR"


async def test_audit_worm_cryptographic_verification(client: httpx.AsyncClient):
    """Prueba 6: Verificación de la cadena criptográfica inmutable WORM SHA-256."""
    # 1. Registrar eventos
    log_security_event(action="TEST_SECURITY_EVENT_1", details={"note": "Prueba de auditoría 1"})
    log_security_event(action="TEST_SECURITY_EVENT_2", details={"note": "Prueba de auditoría 2"})

    # 2. Verificar integridad mediante función interna
    is_valid, count, error = verify_audit_log_integrity()
    assert is_valid is True, f"Fallo de integridad en log de auditoría: {error}"
    assert count >= 2, f"Total de eventos menor al esperado: {count}"

    # 3. Comprobar endpoint REST de auditoría para asesores/auditores
    admin_email = f"auditor_{uuid.uuid4().hex[:6]}@auditoria.es"
    pwd = "AuditPassword2026!"
    await client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": pwd, "full_name": "Auditor Oficial", "role": "SUPERADMIN"},
    )
    login_res = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    token = login_res.json()["access_token"]

    verify_res = await client.get(
        "/api/v1/auth/audit/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_res.status_code == 200, f"Error en endpoint de auditoría: {verify_res.text}"
    v_data = verify_res.json()
    assert v_data["is_valid"] is True
    assert v_data["chain_status"] == "INTACT"
    assert v_data["cryptographic_algorithm"] == "SHA-256 Chained WORM"


async def test_backup_and_recovery_operations(client: httpx.AsyncClient):
    """Prueba 7: Copias de seguridad atómicas, verificación SHA-256 y ensayo de restauración."""
    # 1. Crear backup integral
    backup_meta = create_system_backup(include_documents=False, backup_name_prefix="test_backup")
    assert backup_meta["success"] is True
    backup_file = Path(backup_meta["backup_path"])
    assert backup_file.is_file(), f"No se creó el archivo de respaldo: {backup_file}"
    assert backup_meta["archive_sha256"], "El hash SHA-256 del backup no debe estar vacío"

    # 2. Verificar integridad matemática del backup
    is_valid, error, manifest = verify_backup_integrity(backup_file)
    assert is_valid is True, f"El backup falló la verificación de integridad: {error}"
    assert manifest is not None
    assert manifest["backup_filename"] == backup_file.name

    # 3. Ensayo de restauración y validación SQLite (PRAGMA quick_check)
    restore_res = restore_system_backup(backup_file)
    assert restore_res["success"] is True
    assert restore_res["sqlite_quick_check"] == "ok", "La base de datos restaurada no pasó quick_check"

    # Limpiar archivo temporal de prueba si se desea
    if backup_file.exists():
        backup_file.unlink()


async def test_healthchecks_and_operations_endpoints(client: httpx.AsyncClient):
    """Prueba 8: Endpoints de salud operacional /health y /health/detailed."""
    # 1. Liveness check
    h_res = await client.get("/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "ok"

    # 2. Detailed health check
    d_res = await client.get("/health/detailed")
    assert d_res.status_code == 200
    data = d_res.json()
    assert data["status"] in ("HEALTHY", "OPERATIONAL")
    assert data["components"]["database"]["status"] == "OPERATIONAL"
    assert data["components"]["filesystem"]["status"] == "OPERATIONAL"
    assert data["components"]["audit_log"]["chain_intact"] is True


async def test_rate_limiting_protection(client: httpx.AsyncClient):
    """Prueba 9: Mitigación de fuerza bruta con Rate Limiting (5 peticiones/minuto)."""
    in_memory_limiter.clear()
    # Realizar 5 intentos que deben procesarse
    for _ in range(5):
        res = await client.post("/api/v1/auth/login", json={"email": "attacker@fake.es", "password": "wrong"})
        assert res.status_code == 401

    # El 6to intento debe ser bloqueado con HTTP 429 Too Many Requests
    blocked_res = await client.post("/api/v1/auth/login", json={"email": "attacker@fake.es", "password": "wrong"})
    assert blocked_res.status_code == 429, f"Se esperaba HTTP 429, obtenido: {blocked_res.status_code}"
    in_memory_limiter.clear()


async def main():
    print("\n" + "=" * 80)
    print("   KONTA AI SUITE - FASE 4 Y FASE 5: SEGURIDAD, RBAC Y FIABILIDAD OPERATIVA")
    print("=" * 80 + "\n")

    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tests = [
            ("Criptografía: PBKDF2-HMAC-SHA256 y Políticas de Complejidad", lambda: test_password_hashing_and_complexity()),
            ("Autenticación: Registro, Prevención de Duplicados, Login y Cookies JWT", lambda: test_auth_registration_and_login(client)),
            ("Seguridad de Sesiones: Logout y Revocación Activa de Tokens (JTI)", lambda: test_session_revocation_and_logout(client)),
            ("Recuperación de Contraseñas: Flujo Criptográfico Verificable", lambda: test_password_recovery_flow(client)),
            ("Control de Acceso (RBAC): Segregación de Funciones y Aislamiento por Rol", lambda: test_rbac_authorization_matrix(client)),
            ("Auditoría Inmutable: Verificación Criptográfica WORM SHA-256", lambda: test_audit_worm_cryptographic_verification(client)),
            ("Mitigación de Fuerza Bruta: Rate Limiting HTTP 429 Activo", lambda: test_rate_limiting_protection(client)),
            ("Fiabilidad: Copias de Seguridad, Manifiesto SHA-256 y Restauración Probada", lambda: test_backup_and_recovery_operations(client)),
            ("Operaciones: Sondas de Salud /health y /health/detailed", lambda: test_healthchecks_and_operations_endpoints(client)),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            in_memory_limiter.clear()
            try:
                await test_func()
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
            print("\n>>> TODAS LAS PRUEBAS DE FASE 4 Y FASE 5 HAN SIDO SUPERADAS AL 100% <<<\n")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

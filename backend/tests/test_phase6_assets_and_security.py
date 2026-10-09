"""
Suite Integral de Pruebas de Calidad y Validación para la Fase 6:
Inmovilizado, Seguridad Real, Persistencia de Revocación y Preparación para Producción.

Cubre:
1. Seguridad Real y RBAC:
   - Persistencia de revocación en base de datos relacional (tabla revoked_tokens).
   - Bloqueo de tokens revocados frente a reutilización.
   - Comprobación de seguridad en modo producción (assert_production_security_readiness).
   - Pruebas negativas de aislamiento multi-empresa (Multi-Tenant).
   - Integridad criptográfica de la cadena WORM ante manipulaciones.
2. Inmovilizado y Amortizaciones (PGC):
   - Registro de activos con cuentas PGC adaptadas a la empresa.
   - Cuadro plurianual con prorrateo por días exactos y cuadre decimal.
   - Contabilización de dotación (asiento 681 / 281 en partida doble).
   - Idempotencia: bloqueo de doble contabilización del mismo ejercicio.
   - Bloqueo contable estricto ante ejercicios cerrados.
   - Baja/Venta con asiento de desinversión (cuentas 281, 21x, 572, 671/771).
3. Respaldo y Restauración Aislada:
   - Generación y verificación del manifiesto de backup.
   - Prueba de restauración en un entorno aislado sin sobreescritura de producción.
"""

import asyncio
import os
import shutil
import tempfile
import uuid
import zipfile
import json
from datetime import date, datetime, timedelta, timezone

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app as fastapi_app
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import (
    token_revocation_store,
    assert_production_security_readiness,
)
from app.core.security_cookies import (
    create_session_tokens,
    verify_session_token,
)
from app.core.audit_logger import (
    log_security_event,
    verify_audit_log_integrity,
    get_audit_log_path,
)
from app.models.company import Company
from app.models.user import User, UserRole, RevokedToken, user_companies
from app.models.asset import Asset, AssetDepreciationSchedule, AssetStatus, AssetCategory, DepreciationMethod
from app.models.accounting_entry import AccountingEntryLine
from app.services.asset_service import AssetService
from app.schemas.asset_dto import AssetCreateDTO, PostDepreciationRequestDTO, DisposeAssetRequestDTO
from app.services.backup_service import create_system_backup, restore_system_backup, verify_backup_integrity


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


async def run_phase6_tests():
    print("=" * 75)
    print("KONTA AI SUITE - EJECUCIÓN DE PRUEBAS DE FASE 6")
    print("Seguridad Real, Inmovilizado PGC, Auditoría WORM y Recuperación")
    print("=" * 75)

    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    import app.models as _all_models
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    results = []

    async def record_test(name: str, coro):
        try:
            print(f"\n[TEST] {name} ...", end=" ", flush=True)
            await coro()
            print("OK")
            results.append((name, True, None))
        except Exception as e:
            print(f"FAILED: {e}")
            results.append((name, False, str(e)))

    # -------------------------------------------------------------
    # 1. SEGURIDAD: Persistencia de Revocación de Tokens
    # -------------------------------------------------------------
    async def test_token_revocation_persistence():
        async with TestSessionLocal() as db:
            jti = str(uuid.uuid4())
            exp = datetime.now(timezone.utc) + timedelta(hours=1)

            # Revocar con persistencia
            await token_revocation_store.revoke_persistent(
                jti=jti,
                token_type="access",
                user_id="user-123",
                expires_at=exp,
                db=db,
            )

            # Comprobar en BD
            res = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
            revoked_row = res.scalar_one_or_none()
            assert revoked_row is not None, "El token no se persistió en la tabla revoked_tokens"
            assert revoked_row.jti == jti

            # Comprobar función de chequeo
            is_rev = await token_revocation_store.is_revoked_persistent(jti, db=db)
            assert is_rev is True, "is_revoked_persistent debió retornar True para un token revocado"

            # Token no revocado debe ser False
            is_rev_other = await token_revocation_store.is_revoked_persistent("other-jti", db=db)
            assert is_rev_other is False

    await record_test("1. Persistencia de revocación de tokens en BD (RevokedToken)", test_token_revocation_persistence)

    # -------------------------------------------------------------
    # 2. SEGURIDAD: Readiness en Modo Producción
    # -------------------------------------------------------------
    async def test_production_readiness_checks():
        # En producción con secret inseguro debe fallar
        try:
            assert_production_security_readiness(
                secret_key="insecure-development-secret-key-change-in-production",
                environment="production",
                cookie_secure=True,
            )
            assert False, "Debió lanzar ValueError por SECRET_KEY insegura en producción"
        except ValueError as err:
            assert "clave predeterminada" in str(err)

        # En producción sin HTTPS (cookie_secure=False) debe fallar
        try:
            assert_production_security_readiness(
                secret_key="una-clave-extremadamente-segura-y-fuerte-para-produccion-123456",
                environment="production",
                cookie_secure=False,
            )
            assert False, "Debió lanzar ValueError por ausencia de HTTPS/COOKIE_SECURE"
        except ValueError as err:
            assert "COOKIE_SECURE" in str(err)

        # En desarrollo es tolerante
        assert_production_security_readiness(
            secret_key="insecure-key",
            environment="development",
            cookie_secure=False,
        )

    await record_test("2. Rechazo estricto de configuraciones inseguras en producción", test_production_readiness_checks)

    # -------------------------------------------------------------
    # 3. SEGURIDAD: Aislamiento Multi-Tenant (Prueba Negativa)
    # -------------------------------------------------------------
    async def test_multi_tenant_isolation_negative():
        async with TestSessionLocal() as db:
            # Crear dos empresas
            comp_a = Company(id="comp-a", cif="B11111111", razon_social="Empresa A S.L.")
            comp_b = Company(id="comp-b", cif="B22222222", razon_social="Empresa B S.L.")
            db.add_all([comp_a, comp_b])

            # Crear usuario perteneciente solo a Empresa A
            user_a = User(
                id="user-a",
                email="contable_a@empresa.com",
                hashed_password="hash",
                full_name="Contable A",
                global_role=UserRole.ACCOUNTANT.value,
                is_active=True,
            )
            db.add(user_a)
            await db.flush()

            # Asignar a user_companies para comp_a
            await db.execute(
                user_companies.insert().values(
                    user_id=user_a.id,
                    company_id=comp_a.id,
                    role=UserRole.ACCOUNTANT.value,
                )
            )
            await db.commit()

        # Generar token para user_a
        tokens_a = create_session_tokens(user_id=user_a.id, role=UserRole.ACCOUNTANT.value, company_id="comp-a")
        token_a = tokens_a["access_token"]

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Acceso a comp-a debe ser exitoso
            res_a = await ac.get(
                f"/api/v1/companies/comp-a/assets",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res_a.status_code == 200

            # 2. Acceso a comp-b debe ser 403 FORBIDDEN si el endpoint verifica pertenencia
            from app.core.auth_deps import verify_company_access
            async with TestSessionLocal() as db:
                has_access_b = await verify_company_access("comp-b", user_a, db)
                assert has_access_b is False, "El usuario de Empresa A no debe tener acceso a Empresa B"

    await record_test("3. Aislamiento Multi-Tenant con pruebas de acceso cruzado", test_multi_tenant_isolation_negative)

    # -------------------------------------------------------------
    # 4. INMOVILIZADO: Creación de Activo y Asignación PGC
    # -------------------------------------------------------------
    async def test_asset_creation_and_pgc_mapping():
        async with TestSessionLocal() as db:
            comp = Company(id="comp-assets-1", cif="B33333333", razon_social="Tech Corp S.L.", plan_cuentas_longitud=9)
            db.add(comp)
            await db.commit()

        dto = AssetCreateDTO(
            code="ACT-2026-001",
            name="Servidor Central Rack Dell",
            category=AssetCategory.EQUIPOS_INFORMATICOS,
            acquisition_date=date(2026, 1, 1),
            acquisition_cost=4000.0,
            residual_value=400.0,
            useful_life_years=4.0,
            depreciation_method=DepreciationMethod.LINEAL,
        )

        async with TestSessionLocal() as db:
            asset = await AssetService.create_asset(db, "comp-assets-1", dto, "admin_test")
            assert asset.id is not None
            assert asset.account_asset == "217000000"
            assert asset.account_accumulated_depreciation == "281700000"
            assert asset.account_depreciation_expense == "681000000"
            assert len(asset.schedules) == 4
            # Base amortizable = 4000 - 400 = 3600 -> 900 al año
            assert asset.schedules[0].depreciation_amount == 900.0
            assert asset.schedules[3].net_book_value == 400.0  # Llega al valor residual
            assert asset.status == AssetStatus.ACTIVO.value

    await record_test("4. Alta de activo y autogeneración de cuentas PGC y cuadro", test_asset_creation_and_pgc_mapping)

    # -------------------------------------------------------------
    # 5. INMOVILIZADO: Prorrateo Temporal por Días Exactos
    # -------------------------------------------------------------
    async def test_depreciation_daily_proration():
        # Compra a mitad de año: 1 de julio de 2026
        schedules = AssetService.generate_depreciation_schedule(
            acquisition_cost=1000.0,
            residual_value=0.0,
            start_date=date(2026, 7, 1),
            useful_life_years=2.0,
            method="LINEAL",
        )
        assert len(schedules) >= 2
        # Año 1 (184 días del 1 julio al 31 diciembre de un año no bisiesto de 365 días)
        # Cuota anual = 500. Días: 184 / 365 = ~0.5041 -> ~252.05
        first_year = schedules[0]
        assert first_year["fiscal_year"] == 2026
        assert 250.0 <= first_year["depreciation_amount"] <= 255.0
        # La suma total de todas las cuotas debe ser exactamente 1000.00
        total_deprec = round(sum(s["depreciation_amount"] for s in schedules), 2)
        assert total_deprec == 1000.0, f"La suma de amortizaciones debe cuadrar a 1000.0, dio {total_deprec}"
        assert schedules[-1]["net_book_value"] == 0.0

    await record_test("5. Prorrateo temporal exacto por días y cuadre decimal", test_depreciation_daily_proration)

    # -------------------------------------------------------------
    # 6. INMOVILIZADO: Contabilización de Dotación (Partida Doble)
    # -------------------------------------------------------------
    async def test_post_depreciation_accounting_entry():
        async with TestSessionLocal() as db:
            asset_res = await db.execute(select(Asset).where(Asset.code == "ACT-2026-001"))
            asset = asset_res.scalar_one()

            # Contabilizar primer ejercicio (2026)
            updated_asset, sched, entry_num = await AssetService.post_depreciation_quota(
                session=db,
                company_id=asset.company_id,
                asset_id=asset.id,
                payload=PostDepreciationRequestDTO(fiscal_year=2026),
                current_user_name="contable_test",
            )

            assert sched.is_posted is True
            assert sched.accounting_entry_number == entry_num
            assert updated_asset.accumulated_depreciation == 900.0
            assert updated_asset.net_book_value == 3100.0

            # Verificar las líneas de diario creadas
            lines_res = await db.execute(
                select(AccountingEntryLine).where(
                    AccountingEntryLine.company_id == asset.company_id,
                    AccountingEntryLine.entry_number == entry_num,
                )
            )
            lines = lines_res.scalars().all()
            assert len(lines) == 2

            line_gasto = next(l for l in lines if l.debe > 0)
            line_amort = next(l for l in lines if l.haber > 0)
            assert line_gasto.subcuenta == "681000000"
            assert line_gasto.debe == 900.0
            assert line_amort.subcuenta == "281700000"
            assert line_amort.haber == 900.0
            assert line_gasto.debe == line_amort.haber  # Partida doble perfecta

    await record_test("6. Contabilización de dotación periódica en partida doble (681/281)", test_post_depreciation_accounting_entry)

    # -------------------------------------------------------------
    # 7. INMOVILIZADO: Idempotencia y Bloqueo de Ejercicios Cerrados
    # -------------------------------------------------------------
    async def test_idempotence_and_closed_fiscal_year_lock():
        async with TestSessionLocal() as db:
            asset_res = await db.execute(select(Asset).where(Asset.code == "ACT-2026-001"))
            asset = asset_res.scalar_one()

            # 1. Intentar contabilizar el mismo ejercicio 2026 de nuevo debe fallar
            try:
                await AssetService.post_depreciation_quota(
                    session=db,
                    company_id=asset.company_id,
                    asset_id=asset.id,
                    payload=PostDepreciationRequestDTO(fiscal_year=2026),
                )
                assert False, "Debió fallar por duplicidad de dotación en el mismo ejercicio"
            except Exception as err:
                assert "ya fue contabilizado" in str(err).lower()

            # 2. Bloqueo por cierre contable: cerrar el año 2027 a fecha 31/12/2027
            comp_res = await db.execute(select(Company).where(Company.id == asset.company_id))
            comp = comp_res.scalar_one()
            comp.fecha_cierre_contable = date(2027, 12, 31)
            await db.commit()

            # Intentar contabilizar ejercicio 2027 cerrado debe fallar
            try:
                await AssetService.post_depreciation_quota(
                    session=db,
                    company_id=asset.company_id,
                    asset_id=asset.id,
                    payload=PostDepreciationRequestDTO(fiscal_year=2027, posting_date=date(2027, 12, 31)),
                )
                assert False, "Debió fallar por bloqueo de ejercicio cerrado"
            except Exception as err:
                assert "cerrado" in str(err).lower()

            # Reabrir para siguientes pruebas
            comp.fecha_cierre_contable = None
            await db.commit()

    await record_test("7. Idempotencia y bloqueo estricto ante ejercicios contables cerrados", test_idempotence_and_closed_fiscal_year_lock)

    # -------------------------------------------------------------
    # 8. INMOVILIZADO: Venta y Baja Contable con Pérdida / Beneficio
    # -------------------------------------------------------------
    async def test_asset_disposal_accounting():
        async with TestSessionLocal() as db:
            # Creamos una furgoneta comprada por 10.000€
            van_dto = AssetCreateDTO(
                code="ACT-VAN-01",
                name="Furgoneta Reparto Citroën",
                category=AssetCategory.ELEMENTOS_TRANSPORTE,
                acquisition_date=date(2025, 1, 1),
                acquisition_cost=10000.0,
                residual_value=0.0,
                useful_life_years=5.0,
                depreciation_method=DepreciationMethod.LINEAL,
            )
            van = await AssetService.create_asset(db, "comp-assets-1", van_dto)

            # Contabilizamos 1 año de amortización (2000€)
            await AssetService.post_depreciation_quota(
                db, "comp-assets-1", van.id, PostDepreciationRequestDTO(fiscal_year=2025)
            )

            # Ahora VNC = 8.000€. La vendemos por 8.500€ (Beneficio de 500€ en cuenta 771)
            dispose_dto = DisposeAssetRequestDTO(
                disposal_date=date(2026, 6, 15),
                disposal_amount=8500.0,
                disposal_reason="Venta por renovación de flota",
            )
            disp_asset, entry_num = await AssetService.dispose_asset(
                db, "comp-assets-1", van.id, dispose_dto, "director_financiero"
            )

            assert disp_asset.status == AssetStatus.VENDIDO.value
            assert disp_asset.net_book_value == 0.0

            # Comprobar el asiento de venta
            lines_res = await db.execute(
                select(AccountingEntryLine).where(
                    AccountingEntryLine.company_id == "comp-assets-1",
                    AccountingEntryLine.entry_number == entry_num,
                )
            )
            lines = lines_res.scalars().all()
            total_debe = round(sum(l.debe for l in lines), 2)
            total_haber = round(sum(l.haber for l in lines), 2)
            assert total_debe == total_haber, f"Asiento descuadrado: Debe={total_debe}, Haber={total_haber}"
            # Debe: 2000 (amort 2818) + 8500 (banco 572) = 10500
            # Haber: 10000 (activo 218) + 500 (beneficio 771) = 10500
            assert total_debe == 10500.0
            profit_line = next(l for l in lines if l.subcuenta.startswith("771"))
            assert profit_line.haber == 500.0

    await record_test("8. Flujo contable de venta de activo con beneficio (771) y cuadre", test_asset_disposal_accounting)

    # -------------------------------------------------------------
    # 9. SEGURIDAD WORM: Detección de Alteraciones Criptográficas
    # -------------------------------------------------------------
    async def test_worm_audit_tampering_detection():
        # Generar evento legítimo
        log_security_event(action="TEST_INTEGRITY_EVENT", user_id="auditor", details={"status": "initial"})
        is_intact, count, _ = verify_audit_log_integrity()
        assert is_intact is True, "La cadena WORM inicial debe ser válida"

        # Simular alteración externa en el archivo
        log_path = get_audit_log_path()
        original_content = log_path.read_text(encoding="utf-8")

        # Modificar una coma o texto para corromper el hash
        tampered_content = original_content.replace('"initial"', '"tampered_payload"')
        log_path.write_text(tampered_content, encoding="utf-8")

        # La verificación debe detectar la alteración
        is_intact_tampered, _, corrupt_idx = verify_audit_log_integrity()
        assert is_intact_tampered is False, "La auditoría debió detectar la alteración criptográfica"

        # Restaurar contenido para no afectar otras pruebas
        log_path.write_text(original_content, encoding="utf-8")
        is_intact_restored, _, _ = verify_audit_log_integrity()
        assert is_intact_restored is True

    await record_test("9. Detección criptográfica de alteraciones en auditoría WORM", test_worm_audit_tampering_detection)

    # -------------------------------------------------------------
    # 10. BACKUP Y RESTAURACIÓN AISLADA
    # -------------------------------------------------------------
    async def test_isolated_backup_and_restore():
        from pathlib import Path
        # 1. Crear backup integral
        manifest = create_system_backup()
        assert manifest.get("backup_filename") is not None
        zip_path = Path(manifest["backup_path"])
        assert zip_path.is_file(), f"El archivo de backup no existe: {zip_path}"

        # 2. Verificar integridad del archivo mediante SHA-256
        is_valid, err, meta = verify_backup_integrity(zip_path)
        assert is_valid is True, f"Fallo al verificar el backup: {err}"

        # 3. Restaurar en un directorio temporal aislado (sin sobreescribir prod)
        with tempfile.TemporaryDirectory() as temp_target_dir:
            res = restore_system_backup(
                zip_path=zip_path,
                target_extract_dir=Path(temp_target_dir),
            )
            assert res["success"] is True
            assert os.path.exists(res["extracted_path"])
            assert "manifest" in res

        # Limpiar archivo de backup generado durante el test
        if zip_path.is_file():
            os.remove(zip_path)

    await record_test("10. Generación de copia y restauración en entorno aislado", test_isolated_backup_and_restore)

    # -------------------------------------------------------------
    # RESUMEN FINAL
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print("RESUMEN DE RESULTADOS FASE 6:")
    passed_count = sum(1 for _, ok, _ in results if ok)
    failed_count = sum(1 for _, ok, _ in results if not ok)
    print(f"Total pruebas: {len(results)} | Superadas: {passed_count} | Fallidas: {failed_count}")
    print("=" * 75)

    assert failed_count == 0, f"Se produjeron {failed_count} fallos en las pruebas de Fase 6."


if __name__ == "__main__":
    asyncio.run(run_phase6_tests())

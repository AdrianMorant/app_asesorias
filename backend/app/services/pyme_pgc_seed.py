"""
Catálogo Maestro y Sembrador del Plan General Contable (PGC) para PYMEs en España.
Adapta automáticamente todas las subcuentas a la longitud configurada por la empresa (8, 9 o 10 dígitos).
"""

from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.account import Account

# Definición del catálogo base oficial del PGC PYMES
# Cada entrada tiene:
# - base_code: Código base (puede ser raíz de 3 o 4 dígitos, o con subcódigo con '.')
# - descripcion: Denominación oficial contable
# - tipo: Categoría (GASTO, INGRESO, PROVEEDOR, ACREEDOR, CLIENTE, FINANCIERO, TRIBUTARIO, INMOVILIZADO, PATRIMONIO)
PGC_PYME_MASTER: List[Dict[str, str]] = [
    # ---------------------------------------------------------
    # GRUPO 6: COMPRAS Y GASTOS
    # ---------------------------------------------------------
    {"base": "600", "desc": "Compras de mercaderías", "tipo": "GASTO"},
    {"base": "601", "desc": "Compras de materias primas", "tipo": "GASTO"},
    {"base": "602", "desc": "Compras de otros aprovisionamientos", "tipo": "GASTO"},
    {"base": "607", "desc": "Trabajos realizados por otras empresas (subcontratación)", "tipo": "GASTO"},
    {"base": "608", "desc": "Devoluciones de compras y operaciones similares", "tipo": "GASTO"},
    {"base": "609", "desc": "Rappels por compras", "tipo": "GASTO"},
    {"base": "621", "desc": "Arrendamientos y cánones (alquiler oficinas y naves)", "tipo": "GASTO"},
    {"base": "622", "desc": "Reparaciones y conservación", "tipo": "GASTO"},
    {"base": "623", "desc": "Servicios de profesionales independientes (abogados, asesores, notaría)", "tipo": "GASTO"},
    {"base": "624", "desc": "Transportes y envíos", "tipo": "GASTO"},
    {"base": "625", "desc": "Primas de seguros", "tipo": "GASTO"},
    {"base": "626", "desc": "Servicios bancarios y comisiones similares", "tipo": "GASTO"},
    {"base": "627", "desc": "Publicidad, propaganda y relaciones públicas", "tipo": "GASTO"},
    {"base": "628", "desc": "Suministros (electricidad, agua, gas, internet y telefonía)", "tipo": "GASTO"},
    {"base": "629", "desc": "Otros servicios (material de oficina, software, peajes, viajes)", "tipo": "GASTO"},
    {"base": "631", "desc": "Otros tributos (tasas municipales, IBI, vados)", "tipo": "GASTO"},
    {"base": "640", "desc": "Sueldos y salarios del personal", "tipo": "GASTO"},
    {"base": "642", "desc": "Seguridad Social a cargo de la empresa", "tipo": "GASTO"},
    {"base": "649", "desc": "Otros gastos sociales", "tipo": "GASTO"},
    {"base": "662", "desc": "Intereses de deudas con entidades de crédito", "tipo": "GASTO"},
    {"base": "669", "desc": "Otros gastos financieros", "tipo": "GASTO"},
    {"base": "681", "desc": "Amortización del inmovilizado material", "tipo": "GASTO"},
    {"base": "680", "desc": "Amortización del inmovilizado intangible", "tipo": "GASTO"},

    # ---------------------------------------------------------
    # GRUPO 7: VENTAS E INGRESOS
    # ---------------------------------------------------------
    {"base": "700", "desc": "Ventas de mercaderías", "tipo": "INGRESO"},
    {"base": "705", "desc": "Prestaciones de servicios", "tipo": "INGRESO"},
    {"base": "708", "desc": "Devoluciones de ventas y operaciones similares", "tipo": "INGRESO"},
    {"base": "709", "desc": "Rappels sobre ventas", "tipo": "INGRESO"},
    {"base": "752", "desc": "Ingresos por arrendamientos", "tipo": "INGRESO"},
    {"base": "754", "desc": "Ingresos por comisiones", "tipo": "INGRESO"},
    {"base": "759", "desc": "Ingresos por servicios diversos", "tipo": "INGRESO"},
    {"base": "769", "desc": "Otros ingresos financieros", "tipo": "INGRESO"},

    # ---------------------------------------------------------
    # GRUPO 4: ACREEDORES Y DEUDORES POR OPERACIONES COMERCIALES Y FISCALES
    # ---------------------------------------------------------
    {"base": "400", "desc": "Proveedores generales", "tipo": "PROVEEDOR"},
    {"base": "400.1", "desc": "Proveedores habituales (operaciones corrientes)", "tipo": "PROVEEDOR"},
    {"base": "401", "desc": "Proveedores, efectos comerciales a pagar", "tipo": "PROVEEDOR"},
    {"base": "410", "desc": "Acreedores por prestaciones de servicios", "tipo": "ACREEDOR"},
    {"base": "411", "desc": "Acreedores, efectos comerciales a pagar", "tipo": "ACREEDOR"},
    {"base": "430", "desc": "Clientes generales", "tipo": "CLIENTE"},
    {"base": "431", "desc": "Clientes, efectos comerciales a cobrar", "tipo": "CLIENTE"},
    {"base": "440", "desc": "Deudores varios", "tipo": "CLIENTE"},
    {"base": "465", "desc": "Remuneraciones pendientes de pago (nóminas)", "tipo": "ACREEDOR"},
    
    # Hacienda Pública y Seguridad Social
    {"base": "4700", "desc": "Hacienda Pública, deudora por IVA", "tipo": "TRIBUTARIO"},
    {"base": "472.21", "desc": "H.P. IVA soportado al 21%", "tipo": "TRIBUTARIO"},
    {"base": "472.10", "desc": "H.P. IVA soportado al 10%", "tipo": "TRIBUTARIO"},
    {"base": "472.4", "desc": "H.P. IVA soportado al 4%", "tipo": "TRIBUTARIO"},
    {"base": "472.0", "desc": "H.P. IVA soportado al 0% (exento)", "tipo": "TRIBUTARIO"},
    {"base": "473", "desc": "Hacienda Pública, retenciones y pagos a cuenta", "tipo": "TRIBUTARIO"},
    {"base": "4750", "desc": "Hacienda Pública, acreedora por IVA", "tipo": "TRIBUTARIO"},
    {"base": "4751", "desc": "H.P. acreedora por retenciones practicadas (IRPF)", "tipo": "TRIBUTARIO"},
    {"base": "476", "desc": "Organismos de la Seguridad Social, acreedores", "tipo": "TRIBUTARIO"},
    {"base": "477.21", "desc": "H.P. IVA repercutido al 21%", "tipo": "TRIBUTARIO"},
    {"base": "477.10", "desc": "H.P. IVA repercutido al 10%", "tipo": "TRIBUTARIO"},
    {"base": "477.4", "desc": "H.P. IVA repercutido al 4%", "tipo": "TRIBUTARIO"},

    # ---------------------------------------------------------
    # GRUPO 5: TESORERÍA Y FINANCIERO
    # ---------------------------------------------------------
    {"base": "570", "desc": "Caja, euros", "tipo": "FINANCIERO"},
    {"base": "572", "desc": "Bancos e instituciones de crédito c/c vista", "tipo": "FINANCIERO"},
    {"base": "520", "desc": "Deudas a corto plazo con entidades de crédito", "tipo": "FINANCIERO"},
    {"base": "521", "desc": "Deudas a corto plazo", "tipo": "FINANCIERO"},
    {"base": "555", "desc": "Partidas pendientes de aplicación", "tipo": "FINANCIERO"},

    # ---------------------------------------------------------
    # GRUPO 2: INMOVILIZADO ESENCIAL
    # ---------------------------------------------------------
    {"base": "213", "desc": "Maquinaria", "tipo": "INMOVILIZADO"},
    {"base": "216", "desc": "Mobiliario y enseres de oficina", "tipo": "INMOVILIZADO"},
    {"base": "217", "desc": "Equipos para procesos de información (ordenadores)", "tipo": "INMOVILIZADO"},
    {"base": "218", "desc": "Elementos de transporte (vehículos comerciales)", "tipo": "INMOVILIZADO"},

    # ---------------------------------------------------------
    # GRUPO 1: FINANCIACIÓN BÁSICA
    # ---------------------------------------------------------
    {"base": "100", "desc": "Capital social", "tipo": "PATRIMONIO"},
    {"base": "129", "desc": "Resultado del ejercicio", "tipo": "PATRIMONIO"}
]

def expand_account_code(base_code: str, target_length: int) -> str:
    """
    Normaliza y expande un código base a la longitud exacta de la empresa (8, 9 o 10 dígitos).
    
    Reglas de normalización del software contable español (Contasol, A3, Sage):
    - Códigos con sufijo decimal (ej: '472.21', '472.10', '472.4', '400.1'):
      Se coloca el prefijo, se rellena con ceros intermedios y se ubica el sufijo al final.
      Ej: '472.21' a 9 dígitos -> '472' + '0000' + '21' = '472000021'
      Ej: '472.4' a 9 dígitos  -> '472' + '00000' + '4'  = '472000004'
    - Códigos numéricos simples (ej: '628', '600', '4751'):
      Se coloca el prefijo y se rellena con ceros a la derecha hasta completar target_length.
      Ej: '628' a 9 dígitos  -> '628000000'
      Ej: '4751' a 9 dígitos -> '475100000'
    """
    clean = base_code.strip()
    
    if "." in clean:
        prefix, suffix = clean.split(".", 1)
        needed_zeros = target_length - len(prefix) - len(suffix)
        if needed_zeros >= 0:
            return f"{prefix}{'0' * needed_zeros}{suffix}"
        else:
            # Si se excede, truncar
            return (prefix + suffix)[:target_length]
    else:
        needed_zeros = target_length - len(clean)
        if needed_zeros >= 0:
            return f"{clean}{'0' * needed_zeros}"
        else:
            return clean[:target_length]

async def seed_company_chart_of_accounts(
    db: AsyncSession,
    company_id: str,
    target_length: int
) -> int:
    """
    Siembra el catálogo completo del PGC PYMES adaptado a la longitud de la empresa.
    Inserta únicamente las cuentas que no existan previamente.
    Retorna el número de cuentas creadas.
    """
    # 1. Obtener códigos existentes para evitar duplicados
    stmt = select(Account.codigo).where(Account.company_id == company_id)
    res = await db.execute(stmt)
    existing_codes = set(res.scalars().all())

    created_count = 0
    for item in PGC_PYME_MASTER:
        code = expand_account_code(item["base"], target_length)
        if code not in existing_codes:
            acc = Account(
                company_id=company_id,
                codigo=code,
                descripcion=item["desc"],
                tipo=item["tipo"]
            )
            db.add(acc)
            existing_codes.add(code)
            created_count += 1

    if created_count > 0:
        await db.commit()

    return created_count

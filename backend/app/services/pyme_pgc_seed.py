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
    # GRUPO 1: FINANCIACIÓN BÁSICA (Patrimonio Neto y Pasivo No Corriente)
    # ---------------------------------------------------------
    {"base": "100", "desc": "Capital social", "tipo": "PATRIMONIO"},
    {"base": "102", "desc": "Capital (empresario individual / autónomo)", "tipo": "PATRIMONIO"},
    {"base": "112", "desc": "Reserva legal", "tipo": "PATRIMONIO"},
    {"base": "113", "desc": "Reservas voluntarias", "tipo": "PATRIMONIO"},
    {"base": "120", "desc": "Remanente", "tipo": "PATRIMONIO"},
    {"base": "121", "desc": "Resultados negativos de ejercicios anteriores", "tipo": "PATRIMONIO"},
    {"base": "129", "desc": "Resultado del ejercicio (Pérdidas y Ganancias)", "tipo": "PATRIMONIO"},
    {"base": "170", "desc": "Deudas a largo plazo con entidades de crédito (préstamos bancarios LP)", "tipo": "FINANCIERO"},
    {"base": "171", "desc": "Deudas a largo plazo", "tipo": "FINANCIERO"},
    {"base": "173", "desc": "Proveedores de inmovilizado a largo plazo", "tipo": "FINANCIERO"},

    # ---------------------------------------------------------
    # GRUPO 2: ACTIVO NO CORRIENTE (Inmovilizado Intangible, Material y Amortizaciones)
    # ---------------------------------------------------------
    {"base": "203", "desc": "Propiedad industrial (marcas y patentes)", "tipo": "INMOVILIZADO"},
    {"base": "206", "desc": "Aplicaciones informáticas (software con licencia LP)", "tipo": "INMOVILIZADO"},
    {"base": "210", "desc": "Terrenos y bienes naturales", "tipo": "INMOVILIZADO"},
    {"base": "211", "desc": "Construcciones (naves, oficinas y locales en propiedad)", "tipo": "INMOVILIZADO"},
    {"base": "212", "desc": "Instalaciones técnicas", "tipo": "INMOVILIZADO"},
    {"base": "213", "desc": "Maquinaria", "tipo": "INMOVILIZADO"},
    {"base": "214", "desc": "Utillaje y herramientas", "tipo": "INMOVILIZADO"},
    {"base": "215", "desc": "Otras instalaciones", "tipo": "INMOVILIZADO"},
    {"base": "216", "desc": "Mobiliario y enseres de oficina", "tipo": "INMOVILIZADO"},
    {"base": "217", "desc": "Equipos para procesos de información (ordenadores y servidores)", "tipo": "INMOVILIZADO"},
    {"base": "218", "desc": "Elementos de transporte (furgonetas y vehículos comerciales)", "tipo": "INMOVILIZADO"},
    {"base": "219", "desc": "Otro inmovilizado material", "tipo": "INMOVILIZADO"},
    {"base": "280", "desc": "Amortización acumulada del inmovilizado intangible", "tipo": "INMOVILIZADO"},
    {"base": "281", "desc": "Amortización acumulada del inmovilizado material", "tipo": "INMOVILIZADO"},
    {"base": "291", "desc": "Deterioro de valor del inmovilizado material", "tipo": "INMOVILIZADO"},

    # ---------------------------------------------------------
    # GRUPO 3: EXISTENCIAS (Almacén y Regularización de Stock)
    # ---------------------------------------------------------
    {"base": "300", "desc": "Mercaderías (bienes adquiridos para reventa sin transformación)", "tipo": "INVENTARIO"},
    {"base": "310", "desc": "Materias primas (materiales para transformación y fabricación)", "tipo": "INVENTARIO"},
    {"base": "320", "desc": "Elementos y conjuntos incorporables", "tipo": "INVENTARIO"},
    {"base": "321", "desc": "Combustibles", "tipo": "INVENTARIO"},
    {"base": "322", "desc": "Repuestos", "tipo": "INVENTARIO"},
    {"base": "325", "desc": "Materiales diversos", "tipo": "INVENTARIO"},
    {"base": "326", "desc": "Embalajes", "tipo": "INVENTARIO"},
    {"base": "327", "desc": "Envases", "tipo": "INVENTARIO"},
    {"base": "328", "desc": "Material de oficina en almacén", "tipo": "INVENTARIO"},
    {"base": "330", "desc": "Productos en curso", "tipo": "INVENTARIO"},
    {"base": "350", "desc": "Productos terminados fabricados por la empresa", "tipo": "INVENTARIO"},
    {"base": "390", "desc": "Deterioro de valor de las mercaderías", "tipo": "INVENTARIO"},

    # ---------------------------------------------------------
    # GRUPO 4: ACREEDORES Y DEUDORES POR OPERACIONES COMERCIALES Y FISCALES
    # ---------------------------------------------------------
    {"base": "400", "desc": "Proveedores generales", "tipo": "PROVEEDOR"},
    {"base": "400.1", "desc": "Proveedores habituales (operaciones corrientes)", "tipo": "PROVEEDOR"},
    {"base": "401", "desc": "Proveedores, efectos comerciales a pagar (pagarés)", "tipo": "PROVEEDOR"},
    {"base": "407", "desc": "Anticipos a proveedores", "tipo": "PROVEEDOR"},
    {"base": "410", "desc": "Acreedores por prestaciones de servicios", "tipo": "ACREEDOR"},
    {"base": "411", "desc": "Acreedores, efectos comerciales a pagar", "tipo": "ACREEDOR"},
    {"base": "430", "desc": "Clientes generales", "tipo": "CLIENTE"},
    {"base": "430.1", "desc": "Clientes habituales (operaciones corrientes)", "tipo": "CLIENTE"},
    {"base": "431", "desc": "Clientes, efectos comerciales a cobrar", "tipo": "CLIENTE"},
    {"base": "436", "desc": "Clientes de dudoso cobro", "tipo": "CLIENTE"},
    {"base": "438", "desc": "Anticipos de clientes", "tipo": "CLIENTE"},
    {"base": "440", "desc": "Deudores varios", "tipo": "CLIENTE"},
    {"base": "460", "desc": "Anticipos de remuneraciones (anticipo de nómina)", "tipo": "ACREEDOR"},
    {"base": "465", "desc": "Remuneraciones pendientes de pago (nóminas de empleados)", "tipo": "ACREEDOR"},
    
    # Administraciones Públicas (Hacienda y Seguridad Social)
    {"base": "4700", "desc": "Hacienda Pública, deudora por IVA (a compensar o devolver)", "tipo": "TRIBUTARIO"},
    {"base": "4708", "desc": "Hacienda Pública, deudora por subvenciones concedidas", "tipo": "TRIBUTARIO"},
    {"base": "4709", "desc": "Hacienda Pública, deudora por devolución de impuestos", "tipo": "TRIBUTARIO"},
    {"base": "471", "desc": "Organismos de la Seguridad Social, deudores", "tipo": "TRIBUTARIO"},
    {"base": "472.21", "desc": "H.P. IVA soportado al 21% (régimen general)", "tipo": "TRIBUTARIO"},
    {"base": "472.10", "desc": "H.P. IVA soportado al 10% (tipo reducido)", "tipo": "TRIBUTARIO"},
    {"base": "472.4", "desc": "H.P. IVA soportado al 4% (tipo superreducido)", "tipo": "TRIBUTARIO"},
    {"base": "472.0", "desc": "H.P. IVA soportado al 0% (operaciones exentas)", "tipo": "TRIBUTARIO"},
    {"base": "473", "desc": "Hacienda Pública, retenciones y pagos a cuenta soportados", "tipo": "TRIBUTARIO"},
    {"base": "4750", "desc": "Hacienda Pública, acreedora por IVA (a ingresar Modelo 303)", "tipo": "TRIBUTARIO"},
    {"base": "4751", "desc": "H.P. acreedora por retenciones practicadas IRPF (Modelos 111 / 115)", "tipo": "TRIBUTARIO"},
    {"base": "4752", "desc": "H.P. acreedora por Impuesto sobre Sociedades (Modelo 200/202)", "tipo": "TRIBUTARIO"},
    {"base": "476", "desc": "Organismos de la Seguridad Social, acreedores (cuotas TC1/TC2)", "tipo": "TRIBUTARIO"},
    {"base": "477.21", "desc": "H.P. IVA repercutido al 21% (ventas régimen general)", "tipo": "TRIBUTARIO"},
    {"base": "477.10", "desc": "H.P. IVA repercutido al 10% (ventas tipo reducido)", "tipo": "TRIBUTARIO"},
    {"base": "477.4", "desc": "H.P. IVA repercutido al 4% (ventas tipo superreducido)", "tipo": "TRIBUTARIO"},
    {"base": "477.0", "desc": "H.P. IVA repercutido al 0% (ventas exentas / exportaciones)", "tipo": "TRIBUTARIO"},
    {"base": "477.52", "desc": "H.P. Recargo de equivalencia repercutido al 5.2%", "tipo": "TRIBUTARIO"},
    {"base": "477.14", "desc": "H.P. Recargo de equivalencia repercutido al 1.4%", "tipo": "TRIBUTARIO"},
    {"base": "477.05", "desc": "H.P. Recargo de equivalencia repercutido al 0.5%", "tipo": "TRIBUTARIO"},
    {"base": "490", "desc": "Deterioro de valor de créditos por operaciones comerciales", "tipo": "TRIBUTARIO"},

    # ---------------------------------------------------------
    # GRUPO 5: CUENTAS FINANCIERAS Y TESORERÍA
    # ---------------------------------------------------------
    {"base": "520", "desc": "Deudas a corto plazo con entidades de crédito (pólizas y préstamos CP)", "tipo": "FINANCIERO"},
    {"base": "521", "desc": "Deudas a corto plazo", "tipo": "FINANCIERO"},
    {"base": "523", "desc": "Proveedores de inmovilizado a corto plazo", "tipo": "FINANCIERO"},
    {"base": "525", "desc": "Efectos a pagar a corto plazo", "tipo": "FINANCIERO"},
    {"base": "554", "desc": "Cuenta corriente con UTEs y suplidos profesionales (fondos ajenos)", "tipo": "FINANCIERO"},
    {"base": "555", "desc": "Partidas pendientes de aplicación (descuadres bancarios temporales)", "tipo": "FINANCIERO"},
    {"base": "565", "desc": "Fianzas constituidas a corto plazo (alquileres / depósitos)", "tipo": "FINANCIERO"},
    {"base": "570", "desc": "Caja, euros (efectivo en caja de oficina)", "tipo": "FINANCIERO"},
    {"base": "572", "desc": "Bancos e instituciones de crédito c/c vista (cuenta corriente operativa)", "tipo": "FINANCIERO"},
    {"base": "574", "desc": "Bancos e instituciones de crédito, cuentas de ahorro", "tipo": "FINANCIERO"},

    # ---------------------------------------------------------
    # GRUPO 6: COMPRAS Y GASTOS (Pérdidas y Ganancias)
    # ---------------------------------------------------------
    {"base": "600", "desc": "Compras de mercaderías", "tipo": "GASTO"},
    {"base": "601", "desc": "Compras de materias primas", "tipo": "GASTO"},
    {"base": "602", "desc": "Compras de otros aprovisionamientos", "tipo": "GASTO"},
    {"base": "606", "desc": "Descuentos sobre compras por pronto pago", "tipo": "GASTO"},
    {"base": "607", "desc": "Trabajos realizados por otras empresas (subcontratación productiva)", "tipo": "GASTO"},
    {"base": "608", "desc": "Devoluciones de compras y operaciones similares", "tipo": "GASTO"},
    {"base": "609", "desc": "Rappels por compras (descuentos por volumen)", "tipo": "GASTO"},
    {"base": "610", "desc": "Variación de existencias de mercaderías", "tipo": "GASTO"},
    {"base": "611", "desc": "Variación de existencias de materias primas", "tipo": "GASTO"},
    
    # Servicios exteriores (Subgrupo 62)
    {"base": "621", "desc": "Arrendamientos y cánones (alquiler de oficinas, naves y equipos)", "tipo": "GASTO"},
    {"base": "622", "desc": "Reparaciones y conservación", "tipo": "GASTO"},
    {"base": "623", "desc": "Servicios de profesionales independientes (abogados, asesores, notaría, auditores)", "tipo": "GASTO"},
    {"base": "624", "desc": "Transportes y envíos (paquetería, mensajería y portes)", "tipo": "GASTO"},
    {"base": "625", "desc": "Primas de seguros", "tipo": "GASTO"},
    {"base": "626", "desc": "Servicios bancarios y comisiones similares (mantenimiento y TPV)", "tipo": "GASTO"},
    {"base": "627", "desc": "Publicidad, propaganda y relaciones públicas (marketing, anuncios, Google Ads)", "tipo": "GASTO"},
    {"base": "628", "desc": "Suministros (electricidad, agua, gas, telefonía, fibra e internet)", "tipo": "GASTO"},
    {"base": "629", "desc": "Otros servicios (material de oficina, suscripciones SaaS, peajes, dietas, viajes)", "tipo": "GASTO"},
    
    # Tributos y personal (Subgrupos 63 y 64)
    {"base": "630", "desc": "Impuesto sobre beneficios (Impuesto de Sociedades)", "tipo": "GASTO"},
    {"base": "631", "desc": "Otros tributos (tasas municipales, IBI, vados, basuras)", "tipo": "GASTO"},
    {"base": "640", "desc": "Sueldos y salarios (retribución bruta del personal)", "tipo": "GASTO"},
    {"base": "641", "desc": "Indemnizaciones al personal", "tipo": "GASTO"},
    {"base": "642", "desc": "Seguridad Social a cargo de la empresa (cuota patronal)", "tipo": "GASTO"},
    {"base": "649", "desc": "Otros gastos sociales (formación, seguros colectivos)", "tipo": "GASTO"},
    
    # Gastos financieros y amortizaciones (Subgrupos 66 y 68)
    {"base": "662", "desc": "Intereses de deudas (intereses préstamos bancarios)", "tipo": "GASTO"},
    {"base": "665", "desc": "Intereses por descuento de efectos y factoring", "tipo": "GASTO"},
    {"base": "668", "desc": "Diferencias negativas de cambio (divisas)", "tipo": "GASTO"},
    {"base": "669", "desc": "Otros gastos financieros", "tipo": "GASTO"},
    {"base": "678", "desc": "Gastos excepcionales", "tipo": "GASTO"},
    {"base": "680", "desc": "Amortización del inmovilizado intangible", "tipo": "GASTO"},
    {"base": "681", "desc": "Amortización del inmovilizado material", "tipo": "GASTO"},
    {"base": "694", "desc": "Pérdidas por deterioro de créditos comerciales", "tipo": "GASTO"},

    # ---------------------------------------------------------
    # GRUPO 7: VENTAS E INGRESOS (Pérdidas y Ganancias)
    # ---------------------------------------------------------
    {"base": "700", "desc": "Ventas de mercaderías", "tipo": "INGRESO"},
    {"base": "701", "desc": "Ventas de productos terminados", "tipo": "INGRESO"},
    {"base": "705", "desc": "Prestaciones de servicios (facturación principal de servicios)", "tipo": "INGRESO"},
    {"base": "706", "desc": "Descuentos sobre ventas por pronto pago", "tipo": "INGRESO"},
    {"base": "708", "desc": "Devoluciones de ventas y operaciones similares", "tipo": "INGRESO"},
    {"base": "709", "desc": "Rappels sobre ventas (abonos por volumen a clientes)", "tipo": "INGRESO"},
    {"base": "710", "desc": "Variación de existencias de productos en curso", "tipo": "INGRESO"},
    {"base": "712", "desc": "Variación de existencias de productos terminados", "tipo": "INGRESO"},
    {"base": "740", "desc": "Subvenciones, donaciones y legados a la explotación", "tipo": "INGRESO"},
    {"base": "752", "desc": "Ingresos por arrendamientos (alquileres cobrados a terceros)", "tipo": "INGRESO"},
    {"base": "754", "desc": "Ingresos por comisiones", "tipo": "INGRESO"},
    {"base": "759", "desc": "Ingresos por servicios diversos", "tipo": "INGRESO"},
    {"base": "762", "desc": "Ingresos de créditos", "tipo": "INGRESO"},
    {"base": "768", "desc": "Diferencias positivas de cambio (divisas)", "tipo": "INGRESO"},
    {"base": "769", "desc": "Otros ingresos financieros (intereses de cuentas a favor)", "tipo": "INGRESO"},
    {"base": "778", "desc": "Ingresos excepcionales", "tipo": "INGRESO"},
    {"base": "794", "desc": "Reversión del deterioro de créditos por operaciones comerciales", "tipo": "INGRESO"}
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

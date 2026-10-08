from typing import List, Optional
from pydantic import BaseModel, Field

class TaxBreakdownItem(BaseModel):
    tax_rate: float = Field(
        description="Porcentaje del tipo de IVA aplicado (ej. 21.0, 10.0, 4.0, 0.0)."
    )
    base_amount: float = Field(
        description="Base imponible en euros sujeta a este tipo impositivo concreto."
    )
    tax_amount: float = Field(
        description="Cuota tributaria de IVA correspondiente a esta base en euros."
    )
    surcharge_rate: Optional[float] = Field(
        default=0.0,
        description="Porcentaje de recargo de equivalencia si aplica (ej. 5.2, 1.4, 0.5)."
    )
    surcharge_amount: Optional[float] = Field(
        default=0.0,
        description="Cuota del recargo de equivalencia en euros."
    )

class InvoiceLineItem(BaseModel):
    description: str = Field(description="Descripción del concepto o línea facturada.")
    quantity: Optional[float] = Field(default=1.0, description="Cantidad facturada.")
    unit_price: Optional[float] = Field(default=0.0, description="Precio unitario antes de impuestos.")
    total_line: Optional[float] = Field(default=0.0, description="Importe total de la línea.")

class InvoiceExtractionResult(BaseModel):
    """
    Esquema estructurado estricto para extracción fiscal de facturas españolas con LLM.
    """
    issuer_name: str = Field(
        description="Razón social o nombre y apellidos del emisor (proveedor o acreedor)."
    )
    issuer_tax_id: str = Field(
        description="NIF o CIF del emisor (ej. B12345678, A28015865, 12345678Z). Sin guiones ni puntos."
    )
    issuer_address: Optional[str] = Field(
        default=None,
        description="Dirección fiscal o domicilio del emisor si aparece en la factura."
    )
    
    recipient_name: Optional[str] = Field(
        default=None,
        description="Razón social o nombre del receptor (cliente)."
    )
    recipient_tax_id: Optional[str] = Field(
        default=None,
        description="NIF o CIF del receptor/cliente si aparece."
    )
    
    invoice_number: str = Field(
        description="Número o serie de la factura (ej. FRA-2024-0091, 24/001). Si no existe, indicar 'S/N'."
    )
    issue_date: str = Field(
        description="Fecha de emisión de la factura en formato ISO YYYY-MM-DD (ej. 2024-03-15)."
    )
    due_date: Optional[str] = Field(
        default=None,
        description="Fecha de vencimiento en formato ISO YYYY-MM-DD si figura."
    )
    
    currency: str = Field(
        default="EUR",
        description="Código de moneda ISO 4217 (habitualmente EUR)."
    )
    
    concept_summary: Optional[str] = Field(
        default=None,
        description="Resumen breve del tipo de gasto o servicio facturado (ej. 'Suministro de energía', 'Asesoría fiscal', 'Compra de material de oficina')."
    )
    
    taxes: List[TaxBreakdownItem] = Field(
        default_factory=list,
        description="Desglose detallado por cada tipo impositivo de IVA presente en la factura."
    )
    
    total_base: float = Field(
        description="Suma total de bases imponibles en euros."
    )
    total_tax: float = Field(
        description="Suma total de cuotas de IVA en euros."
    )
    
    retention_rate: Optional[float] = Field(
        default=0.0,
        description="Porcentaje de retención de IRPF si se trata de profesional o alquiler (ej. 15.0, 7.0, 19.0). 0.0 si no aplica."
    )
    retention_amount: Optional[float] = Field(
        default=0.0,
        description="Importe total retenido por IRPF en euros a restar del total."
    )
    
    total_amount: float = Field(
        description="Total factura a pagar por el cliente en euros (Base + IVA - Retención + Recargo)."
    )
    
    items: Optional[List[InvoiceLineItem]] = Field(
        default_factory=list,
        description="Líneas de detalle o partidas individuales contenidas en la factura."
    )

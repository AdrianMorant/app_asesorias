import re
from typing import Tuple, Optional
from pydantic import BaseModel

class NIFValidationResult(BaseModel):
    is_valid: bool
    document_type: str  # 'DNI', 'NIE', 'CIF', o 'INVALID'
    normalized: str
    error_message: Optional[str] = None


def normalize_nif(doc: str) -> str:
    """Limpia caracteres especiales, espacios y convierte a mayúsculas."""
    if not doc:
        return ""
    return re.sub(r"[^A-Z0-9]", "", doc.upper().strip())


def validate_spanish_id(tax_id: str) -> NIFValidationResult:
    """
    Valida un documento fiscal español (DNI, NIE o CIF) de acuerdo con los
    algoritmos oficiales de la Agencia Estatal de Administración Tributaria (AEAT).
    
    Regulaciones de referencia:
    - Real Decreto 1065/2007
    - Orden EHA/451/2008
    - Orden de 28 de mayo de 1984
    """
    normalized = normalize_nif(tax_id)
    
    if not normalized:
        return NIFValidationResult(
            is_valid=False,
            document_type="INVALID",
            normalized="",
            error_message="El documento está vacío."
        )

    # El formato general estándar en España es de 9 caracteres
    if len(normalized) != 9:
        return NIFValidationResult(
            is_valid=False,
            document_type="INVALID",
            normalized=normalized,
            error_message=f"Longitud inválida ({len(normalized)} caracteres). Debe tener 9 caracteres."
        )

    # 1. Comprobación de DNI (8 dígitos + 1 letra)
    if re.match(r"^\d{8}[A-Z]$", normalized):
        return _validate_dni(normalized)

    # 2. Comprobación de NIE (X, Y o Z + 7 dígitos + 1 letra)
    if re.match(r"^[XYZ]\d{7}[A-Z]$", normalized):
        return _validate_nie(normalized)

    # 3. Comprobación de CIF de personas jurídicas y entidades
    if re.match(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$", normalized):
        return _validate_cif(normalized)

    return NIFValidationResult(
        is_valid=False,
        document_type="INVALID",
        normalized=normalized,
        error_message="El formato no coincide con un DNI, NIE o CIF español reglamentario."
    )


def _validate_dni(dni: str) -> NIFValidationResult:
    """Valida un DNI español mediante el algoritmo de módulo 23."""
    table = "TRWAGMYFPDXBNJZSQVHLCKE"
    numbers = int(dni[:8])
    letter = dni[8]
    expected_letter = table[numbers % 23]
    
    if letter == expected_letter:
        return NIFValidationResult(
            is_valid=True,
            document_type="DNI",
            normalized=dni,
            error_message=None
        )
    return NIFValidationResult(
        is_valid=False,
        document_type="DNI",
        normalized=dni,
        error_message=f"Letra de control de DNI incorrecta. Se esperaba '{expected_letter}', se encontró '{letter}'."
    )


def _validate_nie(nie: str) -> NIFValidationResult:
    """Valida un NIE sustituyendo la letra inicial (X=0, Y=1, Z=2) y aplicando módulo 23."""
    table = "TRWAGMYFPDXBNJZSQVHLCKE"
    prefix_map = {"X": "0", "Y": "1", "Z": "2"}
    
    first_char = nie[0]
    numeric_equivalent = prefix_map[first_char] + nie[1:8]
    letter = nie[8]
    
    expected_letter = table[int(numeric_equivalent) % 23]
    
    if letter == expected_letter:
        return NIFValidationResult(
            is_valid=True,
            document_type="NIE",
            normalized=nie,
            error_message=None
        )
    return NIFValidationResult(
        is_valid=False,
        document_type="NIE",
        normalized=nie,
        error_message=f"Letra de control de NIE incorrecta. Se esperaba '{expected_letter}', se encontró '{letter}'."
    )


def _validate_cif(cif: str) -> NIFValidationResult:
    """
    Valida un CIF según la Orden EHA/451/2008 de la AEAT.
    Letra tipo + 7 dígitos + carácter de control (dígito o letra).
    """
    first_char = cif[0]
    central_digits = cif[1:8]
    control_char = cif[8]

    # Suma de posiciones pares (índices 1, 3, 5 dentro de central_digits -> posiciones 2, 4, 6)
    even_sum = sum(int(central_digits[i]) for i in [1, 3, 5])

    # Suma de posiciones impares (índices 0, 2, 4, 6 dentro de central_digits -> posiciones 1, 3, 5, 7)
    odd_sum = 0
    for i in [0, 2, 4, 6]:
        d = int(central_digits[i]) * 2
        odd_sum += (d // 10) + (d % 10)

    total_sum = even_sum + odd_sum
    units = total_sum % 10
    control_digit = (10 - units) % 10

    # Conversión a letra (0=J, 1=A, 2=B, ..., 9=I)
    cif_letters = "JABCDEFGHI"
    expected_letter = cif_letters[control_digit]
    expected_digit = str(control_digit)

    # Reglas de tipo de control según letra inicial
    # 1. Sólo admiten letra de control
    only_letter = {"P", "Q", "R", "S", "W"}
    # 2. Sólo admiten número de control
    only_number = {"A", "B", "E", "H"}
    # 3. Admiten indistintamente letra o número: C, D, F, G, J, N, U, V

    is_valid = False
    expected_desc = ""

    if first_char in only_letter:
        is_valid = (control_char == expected_letter)
        expected_desc = f"letra '{expected_letter}'"
    elif first_char in only_number:
        is_valid = (control_char == expected_digit)
        expected_desc = f"número '{expected_digit}'"
    else:
        # Acepta cualquiera de las dos
        is_valid = (control_char == expected_digit or control_char == expected_letter)
        expected_desc = f"'{expected_digit}' o letra '{expected_letter}'"

    if is_valid:
        return NIFValidationResult(
            is_valid=True,
            document_type="CIF",
            normalized=cif,
            error_message=None
        )
    
    return NIFValidationResult(
        is_valid=False,
        document_type="CIF",
        normalized=cif,
        error_message=f"Carácter de control de CIF incorrecto. Se esperaba {expected_desc}, se encontró '{control_char}'."
    )

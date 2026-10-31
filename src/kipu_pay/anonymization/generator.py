"""Deterministic, category-preserving pseudonym generator."""

from __future__ import annotations

import hashlib
import random
import uuid
from typing import Any

# Colombian name pools
_FEMALE_NAMES = [
    "Sofía", "Valentina", "Isabella", "Camila", "Luciana", "Mariana", "Daniela",
    "Gabriela", "Natalia", "Andrea", "Carolina", "Juliana", "Laura", "Paula",
    "Diana", "Lorena", "Alejandra", "Catalina", "Fernanda", "Melissa", "Jessica",
    "Tatiana", "Paola", "Luz", "Marcela", "Adriana", "Claudia", "Patricia",
    "Elena", "Silvia", "Rosa", "Carmen", "Gloria", "Alicia", "Teresa",
]
_FEMALE_SURNAMES = [
    "Gómez", "Rodríguez", "Martínez", "García", "López", "Hernández",
    "Sánchez", "Ramírez", "Torres", "Flórez", "Díaz", "Morales",
    "Ortiz", "Ruiz", "Vargas", "Castro", "Mendoza", "Jiménez",
    "Ríos", "Agudelo", "Vásquez", "Restrepo", "Bernal", "Cárdenas",
    "Zambrano", "Cortés", "Navarro", "Quintero", "Salazar", "Henao",
]
_MALE_NAMES = [
    "Santiago", "Matías", "Sebastián", "Alejandro", "Nicolás", "Daniel",
    "Juan", "Samuel", "Tomás", "Lucas", "Gabriel", "Martín", "David",
    "Emiliano", "Andrés", "Joaquín", "Carlos", "Diego", "José", "Luis",
    "Miguel", "Antonio", "Fernando", "Ricardo", "Alberto", "Eduardo",
    "Jorge", "Hernán", "César", "Julio", "Raúl", "Sergio", "Mario",
    "Oscar", "Víctor", "Pedro", "Francisco", "Manuel", "Rafael", "Iván",
]
_MALE_SURNAMES = [
    "Gómez", "Rodríguez", "Martínez", "García", "López", "Hernández",
    "Sánchez", "Ramírez", "Torres", "Flórez", "Díaz", "Morales",
    "Ortiz", "Ruiz", "Vargas", "Castro", "Mendoza", "Jiménez",
    "Ríos", "Agudelo", "Vásquez", "Restrepo", "Bernal", "Cárdenas",
    "Zambrano", "Cortés", "Navarro", "Quintero", "Salazar", "Henao",
]

_OCCUPATIONS_GENERAL = {
    "abogada": "profesional de derecho",
    "abogado": "profesional de derecho",
    "médica": "profesional de salud",
    "médico": "profesional de salud",
    "enfermera": "profesional de salud",
    "enfermero": "profesional de salud",
    "contadora": "profesional financiera",
    "contador": "profesional financiera",
    "ingeniera": "profesional técnica",
    "ingeniero": "profesional técnica",
    "periodista": "profesional de medios",
    "diseñadora": "profesional creativa",
    "diseñador": "profesional creativa",
    "profesora": "docente",
    "profesor": "docente",
    "estudiante": "estudiante",
    "empresaria": "empresaria",
    "empresario": "empresario",
    "vendedora": "comerciante",
    "vendedor": "comerciante",
    "cajera": "empleada de servicios",
    "cajero": "empleado de servicios",
    "repartidora": "mensajera",
    "repartidor": "mensajero",
    "chef": "profesional gastronómica",
    "cocinera": "profesional gastronómica",
    "cocinero": "profesional gastronómica",
    "psicóloga": "profesional de salud",
    "psicólogo": "profesional de salud",
    "arquitecta": "profesional técnica",
    "arquitecto": "profesional técnica",
    "administradora": "administradora",
    "administrador": "administrador",
    "electricista": "técnica en mantenimiento",
    "plomera": "técnica en mantenimiento",
    "plomero": "técnico en mantenimiento",
    "policía": "fuerza pública",
    "bombera": "fuerza pública",
    "bombero": "fuerza pública",
    "fotógrafa": "profesional creativa",
    "fotógrafo": "profesional creativa",
    "peluquera": "estilista",
    "peluquero": "estilista",
    "secretaria": "asistente administrativa",
    "mensajera": "mensajera",
    "mensajero": "mensajero",
    "taxista": "conductor",
    "conductor": "conductor",
    "mecánica": "técnica en mantenimiento",
    "mecánico": "técnico en mantenimiento",
    "carpintera": "técnica en construcción",
    "carpintero": "técnico en construcción",
    "pintora": "profesional creativa",
    "pintor": "profesional creativa",
    "música": "artista",
    "músico": "artista",
    "deportista": "deportista",
    "ama de casa": "hogar",
    "jubilada": "jubilada",
    "jubilado": "jubilado",
    "desempleada": "buscando empleo",
    "desempleado": "buscando empleo",
}

_EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com"]


def _seeded_random(entity_id: uuid.UUID, category: str, secret: str) -> random.Random:
    """Create a deterministic random seeded from entity + category + secret."""
    key = f"{entity_id}:{category}:{secret}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    r = random.Random(h)
    return r


def _gender_from_name(name: str) -> str:
    """Infer gender heuristically from first name for pseudonym selection."""
    first = name.split()[0] if name else ""
    first_lower = first.lower()
    # Simple heuristic based on common endings
    if first_lower.endswith(("a", "i")) and first_lower not in ("santiago", "tomás", "matías"):
        return "female"
    return "male"


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def generate_person_name(original_name: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a deterministic Colombian person name preserving inferred gender."""
    gender = _gender_from_name(original_name)
    rng = _seeded_random(entity_id, f"person_name:{gender}", secret)
    if gender == "female":
        first = rng.choice(_FEMALE_NAMES)
        mid = rng.choice(_FEMALE_NAMES)
        sur1 = rng.choice(_FEMALE_SURNAMES)
        sur2 = rng.choice(_FEMALE_SURNAMES)
    else:
        first = rng.choice(_MALE_NAMES)
        mid = rng.choice(_MALE_NAMES)
        sur1 = rng.choice(_MALE_SURNAMES)
        sur2 = rng.choice(_MALE_SURNAMES)
    # 50% chance of two surnames, 50% single surname
    if rng.random() < 0.5:
        return f"{first} {mid} {sur1}"
    return f"{first} {mid} {sur1} {sur2}"


def generate_email(original_email: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a deterministic pseudonym email."""
    rng = _seeded_random(entity_id, "email", secret)
    # Keep kipupay.co domain for employees
    if "@kipupay.co" in original_email.lower():
        local = f"usuario.{rng.randint(100,999)}"
        return f"{local}@kipupay.co"
    local = f"u{rng.randint(10000,99999)}"
    domain = rng.choice(_EMAIL_DOMAINS)
    return f"{local}@{domain}"


def generate_phone(original_phone: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a deterministic Colombian mobile."""
    rng = _seeded_random(entity_id, "phone", secret)
    prefix = rng.choice(["300", "301", "302", "304", "305", "310", "311", "312", "313", "314",
                         "315", "316", "317", "318", "319", "320", "321", "322", "323", "324"])
    rest = rng.randint(1000000, 9999999)
    return f"{prefix} {rest:07d}"


def generate_cedula(original_cedula: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a deterministic Colombian cédula-like number preserving format."""
    rng = _seeded_random(entity_id, "cedula", secret)
    # Colombian cédula: 6-10 digits, commonly 8-10
    val = rng.randint(10000000, 109999999)
    # Preserve dotted format if original had dots
    if "." in original_cedula:
        s = str(val)
        if len(s) == 8:
            return f"{s[:1]}.{s[1:4]}.{s[4:7]}.{s[7:]}"
        elif len(s) == 9:
            return f"{s[:2]}.{s[2:5]}.{s[5:8]}.{s[8:]}"
        elif len(s) == 10:
            return f"{s[:3]}.{s[3:6]}.{s[6:9]}.{s[9:]}"
    return str(val)


def generate_address(original_address: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a plausible address preserving street/Apt pattern."""
    rng = _seeded_random(entity_id, "address", secret)
    types = ["Calle", "Carrera", "Avenida", "Diagonal", "Transversal"]
    t = rng.choice(types)
    n1 = rng.randint(1, 180)
    n2 = rng.randint(1, 80)
    n3 = rng.randint(1, 40)
    apt = rng.randint(101, 1200)
    return f"{t} {n1} # {n2}-{n3}, Apto {apt}"


def generalize_occupation(original: str) -> str:
    """Map occupation to general category."""
    key = original.lower().strip()
    return _OCCUPATIONS_GENERAL.get(key, "profesional independiente")


def generalize_neighborhood(neighborhood: str, city: str) -> str:
    """Generalize neighborhood to city when it could be identifying."""
    # Conservative: if neighborhood is a distinctive proper name, return city
    # Otherwise keep the neighborhood
    return city if city else "ciudad"


def generate_birth_year(original_year: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generalize birth year to decade."""
    rng = _seeded_random(entity_id, "birth_year", secret)
    try:
        y = int(original_year)
        decade = (y // 10) * 10
        return f"fines de los {decade}s"
    except ValueError:
        return "hace unos años"


def generate_handle(original: str, entity_id: uuid.UUID, secret: str) -> str:
    """Generate a generic handle/username."""
    rng = _seeded_random(entity_id, "handle", secret)
    return f"agente.{rng.randint(100,999)}"


def generalize_dob(original_dob: str) -> str:
    """Generalize a date of birth to a vague period."""
    import re
    m = re.search(r"(\d{4})", original_dob)
    if m:
        year = int(m.group(1))
        decade = (year // 10) * 10
        return f"fines de los {decade}s"
    return "hace unos años"

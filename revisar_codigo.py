# revisar_codigo.py
import subprocess
import sys

TRADUCCIONES = {
    # Errores (E)
    "E0001": "Error de sintaxis",
    "E0100": "Error en __init__ del generador",
    "E0101": "Retorno en __init__",
    "E0102": "Función/clase/método redefinido",
    "E0103": "break/continue fuera de un bucle",
    "E0104": "return fuera de una función",
    "E0105": "yield fuera de una función",
    "E0107": "Uso de operador de incremento no existente (++ o --)",
    "E0110": "Uso abstracto de clase no implementada",
    "E0111": "Argumentos invertidos en isinstance()",
    "E0401": "No se puede importar el módulo",
    "E0611": "No se puede importar el nombre desde el módulo",
    "E1101": "El módulo no tiene ese miembro",
    "E1120": "Falta argumento requerido en la llamada",
    "E1121": "Demasiados argumentos en la llamada",
    # Advertencias (W)
    "W0401": "Importación con comodín (wildcard import)",
    "W0404": "Reimportación de módulo ya importado",
    "W0611": "Importación no utilizada",  # duplicado eliminado
    "W0612": "Variable asignada pero no utilizada",
    "W0613": "Argumento no utilizado",
    "W0621": "Variable redefinida desde el ámbito externo",
    "W0622": "Redefinición de nombre incorporado (built-in)",
    "W0702": "Excepción capturada sin especificar tipo (except: desnudo)",
    "W0703": "Excepción demasiado general (Exception)",
    "W1309": "Uso de f-string sin placeholders",
    # Convenciones (C)
    "C0103": "Nombre de variable/función no sigue la convención (snake_case)",
    "C0114": "Falta docstring en el módulo",
    "C0115": "Falta docstring en la clase",
    "C0116": "Falta docstring en la función/método",
    "C0301": "Línea demasiado larga",
    "C0303": "Espacios en blanco al final de la línea",
    "C0304": "Falta salto de línea al final del archivo",
    "C0305": "Líneas en blanco de más al final del archivo",
    "C0321": "Más de una instrucción en la misma línea",
    "C0411": "Orden incorrecto de importaciones",
    "C0412": "Importaciones no agrupadas correctamente",
    "C0413": "Importación no al inicio del archivo",
    # Refactoring (R)
    "R0201": "Método podría ser una función estática",
    "R0401": "Importación circular detectada",
    "R0801": "Código duplicado detectado",
    "R0901": "Demasiados ancestros en la herencia",
    "R0902": "Demasiados atributos en la clase",
    "R0903": "Muy pocos métodos públicos en la clase",
    "R0904": "Demasiados métodos públicos",
    "R0911": "Demasiados return en la función",
    "R0912": "Demasiadas ramas (if/elif) en la función",
    "R0913": "Demasiados argumentos en la función",
    "R0914": "Demasiadas variables locales",
    "R0915": "Demasiadas instrucciones en la función",
    "R1705": "else innecesario después de return",
    "R1710": "La función no siempre retorna un valor explícito",
    "R1720": "else innecesario después de raise",
    "R1721": "Comprensión de lista innecesaria",
    "R1722": "Usar sys.exit() en lugar de raise SystemExit()",
}

CATEGORIAS = {
    "E": "🔴 ERRORES (deben corregirse)",
    "W": "🟡 ADVERTENCIAS (revisar)",
    "C": "🔵 CONVENCIONES (estilo de código)",
    "R": "🟠 REFACTORING (mejoras sugeridas)",
}


def ejecutar_pylint(ruta):
    resultado = subprocess.run(
        [
            "pylint",
            "--load-plugins=pylint_django",
            "--msg-template={path}|{line}|{msg_id}|{msg}",
            "--output-format=text",
            "--reports=no",
            "--score=yes",
            ruta,
        ],
        capture_output=True,
        text=True,
    )
    # FIX: combinar stdout y stderr para no perder mensajes
    salida_completa = resultado.stdout + resultado.stderr
    return salida_completa, resultado.returncode


def _construir_entrada(archivo, numero_linea, codigo, mensaje):
    """Formatea una línea de problema en texto legible."""
    traduccion = TRADUCCIONES.get(codigo, mensaje)
    return (
        f"  Archivo : {archivo}  |  Línea: {numero_linea}\n"
        f"  Código  : {codigo}\n"
        f"  Problema: {traduccion}\n"
        f"  Detalle : {mensaje}\n"
    )


def _parsear_lineas(salida):
    """Recorre la salida de Pylint y devuelve (problemas, puntaje)."""
    problemas = {"E": [], "W": [], "C": [], "R": []}
    puntaje = None

    for linea in salida.splitlines():
        if linea.startswith("Your code has been rated"):
            puntaje = linea
            continue

        partes = linea.split("|")
        if len(partes) < 4:
            continue

        archivo = partes[0].strip()
        numero_linea = partes[1].strip()
        codigo = partes[2].strip()
        mensaje = partes[3].strip()
        categoria = codigo[0] if codigo else "?"

        if categoria not in problemas:
            continue

        problemas[categoria].append(
            _construir_entrada(archivo, numero_linea, codigo, mensaje)
        )

    return problemas, puntaje


def _imprimir_reporte(problemas, puntaje):
    """Imprime el reporte final organizado por categoría."""
    print("\n" + "=" * 60)
    print("     REVISIÓN DE CÓDIGO — REPORTE EN ESPAÑOL")
    print("=" * 60)

    total = sum(len(v) for v in problemas.values())

    if total == 0:
        print("\n✅ ¡Sin problemas encontrados!")
    else:
        for cat, lista in problemas.items():
            if not lista:
                continue
            print(f"\n{CATEGORIAS[cat]} — {len(lista)} encontrado(s)")
            print("-" * 50)
            for item in lista:
                print(item)

    print("=" * 60)
    print(f"TOTAL DE PROBLEMAS: {total}")
    if puntaje:
        print(f"PUNTUACIÓN: {puntaje}")
    print("=" * 60 + "\n")


def parsear_y_mostrar(salida):
    """Orquesta el parseo y la impresión del reporte."""
    problemas, puntaje = _parsear_lineas(salida)
    _imprimir_reporte(problemas, puntaje)


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"\n🔍 Analizando: {ruta} ...")
    salida, _ = ejecutar_pylint(ruta)
    parsear_y_mostrar(salida)

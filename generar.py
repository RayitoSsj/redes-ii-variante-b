#!/usr/bin/env python3
"""
Genera la configuración de los 6 equipos de la Práctica integradora
Redes II (Variante B) a partir de datos.yaml y plantillas Jinja2.

Uso:
    python generar.py                  # usa datos.yaml, escribe en salida/
    python generar.py -d otro.yaml -o carpeta/
"""
import argparse
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

BASE = Path(__file__).resolve().parent


def cargar_datos(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validar(d):
    """Revisa reglas de la ficha antes de generar. Regresa lista de errores."""
    errores = []
    rangos = [r["dhcp_rango"] for r in d["routers"]]
    (a1, b1), (a2, b2) = rangos
    if not (b1 < a2 or b2 < a1):
        errores.append(f"Los rangos DHCP se traslapan: {rangos}")
    bloques = [r["dhcpv6_bloque"] for r in d["routers"]]
    if len(set(bloques)) != len(bloques):
        errores.append("Los dos routers usan el mismo bloque DHCPv6")
    hostnames = {r["hostname"] for r in d["routers"]}
    for v in d["vlans"]:
        if "activo" in v and v["activo"] not in hostnames:
            errores.append(f"VLAN {v['id']}: router activo '{v['activo']}' no existe")
    return errores


def contexto_comun(d):
    vlans_usuario = [v for v in d["vlans"] if "v6" in v]          # 15,25,35,45
    vlans_ruteadas = [v for v in d["vlans"] if "v4" in v]         # + gestión
    gestion = next(v for v in d["vlans"] if v.get("gestion"))
    permitidas = sorted([v["id"] for v in vlans_ruteadas] + [d["vlan_nativa"]])
    return {
        "d": d,
        "g": d["general"],
        "vlans_usuario": vlans_usuario,
        "vlans_ruteadas": vlans_ruteadas,
        "gestion": gestion,
        "ids_usuario": ",".join(str(v["id"]) for v in vlans_usuario),
        "permitidas": ",".join(str(x) for x in permitidas),
    }


def excluidos(rango, ultimo=254):
    """Todo lo que NO es el rango del router queda excluido."""
    a, b = rango
    out = []
    if a > 1:
        out.append((1, a - 1))
    if b < ultimo:
        out.append((b + 1, ultimo))
    return out


def stp(d, router):
    con_hsrp = [v for v in d["vlans"] if "activo" in v]
    prim = [str(v["id"]) for v in con_hsrp if v["activo"] == router]
    sec = [str(v["id"]) for v in con_hsrp if v["activo"] != router]
    return ",".join(prim), ",".join(sec)


def generar(datos, salida):
    d = cargar_datos(datos)
    errores = validar(d)
    if errores:
        for e in errores:
            print("ERROR:", e)
        sys.exit(1)

    env = Environment(
        loader=FileSystemLoader(BASE / "plantillas"),
        undefined=StrictUndefined,      # falla si falta un dato en el YAML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    comun = contexto_comun(d)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)

    trabajos = []
    for r in d["routers"]:
        ctx = dict(comun, equipo=r, vty="0 4", excluidos=excluidos(r["dhcp_rango"]))
        trabajos.append(("router.j2", r["hostname"], ctx))
    for s in d["switches"]:
        ctx = dict(comun, equipo=s, vty="0 15")
        if s["rol"] == "distribucion":
            ctx["stp_primario"], ctx["stp_secundario"] = stp(d, s["router"])
            trabajos.append(("distribucion.j2", s["hostname"], ctx))
        else:
            trabajos.append(("acceso.j2", s["hostname"], ctx))

    for plantilla, nombre, ctx in trabajos:
        texto = env.get_template(plantilla).render(**ctx)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        archivo = salida / f"{nombre}.txt"
        archivo.write_text(texto, encoding="utf-8")
        pendientes = sorted(set(re.findall(r"<[A-Z0-9_]+>", texto)))
        aviso = f"  (faltan: {', '.join(pendientes)})" if pendientes else ""
        print(f"OK  {archivo}{aviso}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-d", "--datos", default=BASE / "datos.yaml")
    p.add_argument("-o", "--salida", default=BASE / "salida")
    a = p.parse_args()
    generar(a.datos, a.salida)

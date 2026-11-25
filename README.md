# Práctica integradora Redes II · Variante B · Clínica San Rafael

Bono de automatización: un script en Python lee los datos de la ficha desde un
archivo YAML y genera, con plantillas Jinja2, la configuración completa de los
6 equipos (R5, R6, DS5, DS6, AS7, AS8).

## Estructura

```
.
├── datos.yaml             # Datos de la ficha (VLANs, IPs, HSRP, DHCP, VTP, puertos)
├── generar.py             # Lee el YAML, valida y renderiza las plantillas
├── plantillas/
│   ├── base.j2            # Paso 1 (básica) y Paso 9 (SSH): comunes a los 6 equipos
│   ├── router.j2          # Pasos 6 y 7: subinterfaces, HSRPv2, serial, DHCPv4/v6
│   ├── _switch.j2         # Pasos 2, 3, 4, 8 y 9 comunes a los 4 switches
│   ├── distribucion.j2    # VLANs (servidor VTP) y raíz STP primaria/secundaria
│   └── acceso.j2          # Puertos de acceso, VLAN 666 y Paso 10 (seguridad)
├── salida/                # Configuraciones generadas (una por equipo)
└── requirements.txt
```

## Uso

```bash
pip install -r requirements.txt
python generar.py
```

Salida esperada:

```
OK  salida/R5.txt
OK  salida/R6.txt
OK  salida/DS5.txt
OK  salida/DS6.txt
OK  salida/AS7.txt
OK  salida/AS8.txt
```

Si en el YAML queda algún marcador sin llenar (por ejemplo `<SERIAL_R5>`), el
script lo avisa junto al archivo.

Opciones:

```bash
python generar.py -d otro_archivo.yaml -o otra_carpeta/
```

## Qué se calcula automáticamente desde el YAML

| Dato | Cómo lo obtiene el script |
|---|---|
| VLANs permitidas en troncales | VLANs con red IPv4 + VLAN nativa → `15,25,35,45,85,777` |
| Prioridad y preempt de HSRP | `150` + `preempt` solo en el router marcado como `activo` de cada VLAN |
| Grupo HSRP IPv6 | ID de VLAN + 1000 |
| Exclusiones DHCPv4 | Todo lo que queda fuera del `dhcp_rango` de cada router (incluye routers, gateway y switches) |
| Bloque DHCPv6 | R5 reparte de `xx:1::/80` y R6 de `xx:2::/80`, así que ningún host recibe la misma dirección de los dos |
| Raíz STP | El switch de distribución conectado al router activo es `root primary` de esa VLAN; el otro, `secondary` |
| Confianza DHCP Snooping / DAI | Troncales y port-channel de cada switch de acceso |

Antes de generar, el script **valida**:
- que los rangos DHCPv4 de los dos routers no se traslapen,
- que cada router use un bloque DHCPv6 distinto,
- que el router activo de cada VLAN exista.

Además usa `StrictUndefined`: si falta un dato en el YAML, falla en lugar de
generar una configuración incompleta.

## Cambiar de red (por ejemplo, para Packet Tracer)

Solo se edita el YAML; las plantillas no se tocan:

- `hostname`, interfaces (`lan`, `troncales`, `etherchannel.puertos`, `serial.interfaz`) y puertos de acceso.
- `general.scrypt: false` para Packet Tracer (no soporta `algorithm-type scrypt`).

Se puede tener un YAML por escenario y elegirlo con `-d`.

## Cómo demostrar que funciona

1. Ejecutar `python generar.py`.
2. Abrir cada archivo de `salida/` y pegarlo en la CLI del equipo correspondiente.
3. Verificar con los `show` de cada punto de revisión del documento
   (`show etherchannel summary`, `show interfaces trunk`, `show vlan brief`,
   `show standby brief`, `show ip dhcp binding`, `show spanning-tree vlan X`,
   `show ip ssh`, `show port-security interface ...`).

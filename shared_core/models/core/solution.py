from threading import Thread

import numpy as np
import pyttsx3
from colorama import Fore, Style, init
from pyttsx3.engine import Engine
from pyttsx3.voice import Voice

from shared_core.middlewares.slogger import SafeLogger

init()

LOGGER = SafeLogger("solution")


class Solution:
    """Formatted IIT/MIP solution with optional speech notification."""

    def __init__(
        self,
        estrategia: str,
        perdida: float,
        distribucion_subsistema: np.ndarray,
        distribucion_particion: np.ndarray,
        particion: str,
        tiempo_total: float = 0.0,
        quiere_hablar: bool | None = None,
        hablar: bool | None = None,
        voz: str | None = None,
    ) -> None:
        self.estrategia = estrategia
        self.perdida = perdida
        self.distribucion_subsistema = distribucion_subsistema
        self.distribucion_particion = distribucion_particion
        self.particion = particion
        self.tiempo_ejecucion = tiempo_total
        self.id_voz = voz
        self.hablar = hablar if hablar is not None else (
            True if quiere_hablar is None else quiere_hablar
        )

    def __obtener_voz_espanol(self, motor: Engine) -> str | None:
        voces: list[Voice] = motor.getProperty("voices")
        prioridades = [
            ("sabina", "méxico"),
            ("helena", "españa"),
            ("spanish", None),
            ("español", None),
            ("es-", None),
        ]

        for nombre_buscado, region in prioridades:
            for voz in voces:
                nombre_voz = voz.name.lower()
                id_voz = voz.id.lower()

                if nombre_buscado in nombre_voz or nombre_buscado in id_voz:
                    if region is None or region in nombre_voz:
                        return voz.id

        return voces[0].id if voces else None

    def __anunciar_solucion(self) -> None:
        """Announce the solution through the local TTS engine when enabled."""
        try:
            motor = pyttsx3.init()
            id_voz = self.id_voz or self.__obtener_voz_espanol(motor)
            if id_voz:
                motor.setProperty("voice", id_voz)

            motor.setProperty("rate", 150)
            motor.setProperty("volume", 0.9)
            mensaje = f"Solución encontrada con {self.estrategia}." + (
                f"El valor de fi es de {self.perdida:.2f}"
                if self.perdida > 0
                else "No hubo pérdida."
            )
            motor.say(mensaje)
            motor.runAndWait()
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            LOGGER.error(f"Error al inicializar el motor de voz: {error}")

    def __str__(self) -> str:
        espaciado = 64
        bilinea = "═" * espaciado
        trilinea = "≡" * espaciado

        def formatear_distribucion(
            distribucion: np.ndarray,
            evitar_desbordamiento: bool = True,
        ) -> str:
            rango = distribucion.size
            mensaje_desborde = ""
            if evitar_desbordamiento:
                excedente = rango - espaciado
                if excedente > 0:
                    mensaje_desborde = f" {excedente} valores más.."
                    rango = espaciado

            datos = " ".join(
                f"{Fore.WHITE}{distribucion[idx]:.4f}"
                if distribucion[idx] > 0
                else f"{Fore.LIGHTBLACK_EX}0.    "
                for idx in range(rango)
            )
            return f"[ {datos}{mensaje_desborde} {Fore.WHITE}]"

        if self.hablar:
            voz = Thread(target=self.__anunciar_solucion)
            voz.start()

        distancia_metrica, notacion = _application_labels()
        es_pyphi = self.estrategia == "Pyphi"
        tipo_distribucion = "tensorial" if es_pyphi else "marginal"
        tiempo_hrs, tiempo_min, tiempo_seg = (
            f"{self.tiempo_ejecucion / 3600:.2f}",
            f"{self.tiempo_ejecucion / 60:.1f}",
            f"{self.tiempo_ejecucion:.4f}",
        )
        return f"""{Fore.CYAN}{bilinea}

{Fore.RED}{self.estrategia} fue la estrategia de solucion.

{Fore.BLUE}Distancia métrica utilizada:
{Fore.WHITE}{distancia_metrica}
{Fore.BLUE}Notación utilizada en indexación:
{Fore.WHITE}{notacion}

{Fore.YELLOW}Distribucion {tipo_distribucion} del Subsistema:
{Style.RESET_ALL}{formatear_distribucion(self.distribucion_subsistema)}
{Fore.YELLOW}Distribucion {tipo_distribucion} de la Partición:
{Style.RESET_ALL}{formatear_distribucion(self.distribucion_particion)}

{Fore.YELLOW}Mejor Bi-Partición:
{Fore.MAGENTA}{self.particion}
{Fore.GREEN}Perdida mínima ( φ ) = {self.perdida:.4f}

{Fore.BLUE}Tiempos de ejecución:
{Fore.WHITE}Horas: {tiempo_hrs} = Minutos: {tiempo_min} = Segundos: {tiempo_seg}

{Fore.CYAN}{trilinea}{Style.RESET_ALL}"""

    def __repr__(self) -> str:
        return self.__str__()


def _application_labels() -> tuple[object, object]:
    try:
        from src.models.base.application import aplicacion
    except (ImportError, ModuleNotFoundError):
        return "", ""
    return (
        getattr(aplicacion, "distancia_metrica", ""),
        getattr(aplicacion, "notacion_indexado", getattr(aplicacion, "notacion", "")),
    )

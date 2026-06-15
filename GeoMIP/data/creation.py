import os
import sys
import time

import numpy as np

from shared_core.middlewares.slogger import SafeLogger

LOGGER = SafeLogger("geomip_data_creation")


class SystemCreator:
    def __init__(self, N: int):
        self.N = N
        self.num_states = 2**N

        total_size_gb = (self.num_states * N) / (1024**3)
        LOGGER.info(f"\nTamaño estimado: {total_size_gb:.6f} GB")
        if total_size_gb > 1:
            confirm = input("El sistema ocupará más de 1GB. ¿Desea continuar? (s/n): ")
            if confirm.lower() != "s":
                sys.exit("Operación cancelada por el usuario")

        estimated_time = total_size_gb * 2
        LOGGER.info(f"Tiempo estimado: {estimated_time:.1f} segundos ({estimated_time/60:.1f} minutos)")

        LOGGER.info("Generando estados...")
        start_time = time.time()
        self.states = np.random.randint(2, size=(self.num_states, N), dtype=np.int8)
        elapsed = time.time() - start_time
        LOGGER.info(f"Generación completada en {elapsed:.2f} segundos")

    def marginalize(self, dimension: int) -> np.ndarray:
        if dimension < 1 or dimension >= self.N:
            raise ValueError(f"La dimensión debe estar en [1, {self.N - 1})")
        return self.states[:, dimension]

    def save_to_csv(self, filename: str = None):
        filename = f"Sys{self.N}.csv" if filename is None else filename

        os.makedirs(".assets", exist_ok=True)
        filepath = os.path.join(".assets", filename)
        LOGGER.info(f"\nGuardando estados en {filepath}...")

        start_time = time.time()

        # Guardar solo la data, sin header
        np.savetxt(filepath, self.states, delimiter=",", fmt="%d")

        elapsed = time.time() - start_time
        file_size_gb = os.path.getsize(filepath) / (1024**3)
        LOGGER.info(f"Archivo guardado: {file_size_gb:.6f} GB")
        LOGGER.info(f"Tiempo de guardado: {elapsed:.2f} segundos")


def generate_and_save(N: int):
    LOGGER.info(f"\nGenerando sistema con N={N}...")
    start_total = time.time()

    system = SystemCreator(N)
    system.save_to_csv()

    total_time = time.time() - start_total
    LOGGER.info(f"\nTiempo total del proceso: {total_time:.2f} segundos ({total_time / 60:.2f} minutos)")
    return system


if __name__ == "__main__":
    try:
        system = generate_and_save(8)
    except KeyboardInterrupt:
        LOGGER.error("\nOperación cancelada por el usuario")
    except (OSError, ValueError) as error:
        LOGGER.error(f"\nError: {error}")

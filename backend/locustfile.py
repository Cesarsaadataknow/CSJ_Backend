"""
===============================================================================
DESCRIPCIÓN: Archivo de configuración para pruebas de carga con Locust.
             Define un usuario de prueba que realiza solicitudes HTTP a la aplicación.
===============================================================================
"""

# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
from locust import HttpUser, task, between
# endregion

# -----------------------------------------------------------------------------
# region               CLASE DE USUARIO PARA PRUEBAS DE CARGA
# -----------------------------------------------------------------------------
class load_testing(HttpUser):
    """
    Clase que define el comportamiento de un usuario durante las pruebas de carga.
    """
    
    wait_time = between(1, 3)  # Tiempo de espera entre tareas (1 a 3 segundos)
    host = "https://alqueria-poc-agente-sql-frontend-duh8dzanccarhbg3.eastus2-01.azurewebsites.net/c/2623fd4b-0310-4524-a233-3b05a06c72c3"
    
    @task
    def load_testing(self):
        """
        Tarea que ejecuta el usuario: realiza una solicitud GET a la raíz del host.
        """
        self.client.get("/")
# endregion
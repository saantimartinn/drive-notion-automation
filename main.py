import json
import logging
import os
from datetime import datetime

from flask import Flask
from google.auth import default
from google.cloud import secretmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from notion_client import Client

from gcs_helpers import guardar_en_gcs

app = Flask(__name__)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# -----------------------------
# Config (env-driven where it matters)
# -----------------------------
SCOPES = ["https://www.googleapis.com/auth/drive"]

import os

SECRET_NAME = os.environ.get("GCP_SECRET_NAME")
if not SECRET_NAME:
    raise RuntimeError("Missing environment variable: GCP_SECRET_NAME")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "mi-bucket-automatizaciones")
LOG_OBJECT_NAME = os.environ.get("LOG_OBJECT_NAME", "log_drive_notion.txt")

# -----------------------------
# Load config from Secret Manager (Default Credentials)
# -----------------------------
credentials, _ = default()
sm_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
response = sm_client.access_secret_version(request={"name": SECRET_NAME})
claves_json = response.payload.data.decode("UTF-8")
config = json.loads(claves_json)

# -----------------------------
# Google Drive client (service account stored in secret)
# -----------------------------
drive_creds = service_account.Credentials.from_service_account_info(
    config["google_drive"]["service_account"],
    scopes=SCOPES,
)
drive_service = build("drive", "v3", credentials=drive_creds, cache_discovery=False)

# -----------------------------
# Notion client
# -----------------------------
ID_CARPETA_RESERVA = config["google_drive"]["plantillas_id"]
ID_CARPETA_PPAL = config["google_drive"]["folder_id"]
NOTION_TOKEN = config["notion"]["token"]
DATABASE_ID = config["notion"]["database_id"]

notion = Client(auth=NOTION_TOKEN)

# -----------------------------
# Logging to GCS
# -----------------------------
def registrar_log(clientes_procesados, errores, carpetas_creadas) -> None:
    log = f"Ejecucion: {datetime.now().isoformat()}\n"
    log += f"Clientes procesados: {len(clientes_procesados)}\n"
    log += f"Nombres de clientes: {clientes_procesados}\n"
    log += f"Carpetas creadas: {carpetas_creadas}\n"
    log += f"Errores: {errores}\n"
    guardar_en_gcs(LOG_OBJECT_NAME, log, bucket_name=GCS_BUCKET_NAME)


# -----------------------------
# Google Drive helpers
# -----------------------------
def crear_carpeta(nombre: str, id_padre: str) -> str:
    if DRY_RUN:
        logger.info("[DRY_RUN] Crear carpeta '%s' en padre=%s", nombre, id_padre)
        return f"dryrun_{nombre}"

    metadata = {
        "name": nombre,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [id_padre],
    }
    carpeta = drive_service.files().create(body=metadata, fields="id").execute()
    return carpeta["id"]


def obtener_reserva_disponible(tipo: str):
    query = f"name contains '{tipo}' and '{ID_CARPETA_RESERVA}' in parents"
    resultados = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
    ).execute()

    archivos = resultados.get("files", [])
    archivos.sort(key=lambda x: x["name"])
    return archivos[0] if archivos else None


def mover_archivo_a_cliente(file_id: str, id_destino: str) -> None:
    if DRY_RUN:
        logger.info("[DRY_RUN] Mover archivo %s -> %s (removeParents=%s)", file_id, id_destino, ID_CARPETA_RESERVA)
        return

    drive_service.files().update(
        fileId=file_id,
        addParents=id_destino,
        removeParents=ID_CARPETA_RESERVA,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    logger.info("Archivo movido: %s -> %s", file_id, id_destino)


def renombrar_archivo(file_id: str, nuevo_nombre: str) -> None:
    if DRY_RUN:
        logger.info("[DRY_RUN] Renombrar archivo %s -> %s", file_id, nuevo_nombre)
        return

    drive_service.files().update(
        fileId=file_id,
        body={"name": nuevo_nombre},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    logger.info("Archivo renombrado a: %s", nuevo_nombre)


def crear_estructura_recursiva(id_padre: str, estructura: dict, id_usuario: str = "") -> None:
    for nombre, contenido in estructura.items():
        id_carpeta = crear_carpeta(nombre, id_padre)
        logger.info("Carpeta creada: %s (%s)", nombre, id_carpeta)

        if isinstance(contenido, dict):
            crear_estructura_recursiva(id_carpeta, contenido, id_usuario)
            continue

        if isinstance(contenido, list):
            for archivo in contenido:
                archivo_reserva = obtener_reserva_disponible(archivo)
                if not archivo_reserva:
                    logger.warning("No hay archivos disponibles para: %s", archivo)
                    continue

                mover_archivo_a_cliente(archivo_reserva["id"], id_carpeta)

                # Renombrar el archivo con el ID del cliente si está disponible
                nuevo_nombre = f"{id_usuario}_{archivo}.docx" if id_usuario else f"{archivo}.docx"
                renombrar_archivo(archivo_reserva["id"], nuevo_nombre)


# -----------------------------
# Default client folder structure
# -----------------------------
estructura_cliente = {
    "0. Info Received": {
        "0. DNI/Pasaporte": {"0. Cliente": [], "1. Padres": []},
        "1. Notas": [],
        "2. Extra Docs": [],
    },
    "1. Profile": {
        "0. FrameWork": ["Framework"],
        "1. Extra": [],
    },
    "2. Working Papers": {
        "0. Essays": [],
        "1. Grades": [],
        "2. Extra": [],
    },
    "3. Formal Docs": {
        "0. Contract": ["Contrato"],
        "1. Invoices": ["Factura"],
    },
}

# -----------------------------
# Notion helpers
# -----------------------------
def obtener_clientes_para_crear():
    response = notion.databases.query(
        database_id=DATABASE_ID,
        filter={
            "and": [
                {"property": "IN?", "status": {"equals": "INSIDE"}},
                {"property": "Carpeta Creada", "checkbox": {"equals": False}},
            ]
        },
    )
    logger.info("Se encontraron %d clientes para procesar.", len(response["results"]))
    return response["results"]


def marcar_como_creado(page_id: str) -> None:
    if DRY_RUN:
        logger.info("[DRY_RUN] Marcar como creado en Notion page_id=%s", page_id)
        return

    notion.pages.update(
        page_id=page_id,
        properties={"Carpeta Creada": {"checkbox": True}},
    )


# -----------------------------
# Main flow
# -----------------------------
def crear_estructura_para_cliente(nombre_cliente: str, id_usuario: str = "") -> None:
    nombre_carpeta_principal = f"{id_usuario}_{nombre_cliente}" if id_usuario else nombre_cliente
    logger.info("Creando carpeta principal: %s", nombre_carpeta_principal)

    id_cliente = crear_carpeta(nombre_carpeta_principal, ID_CARPETA_PPAL)
    logger.info("Carpeta cliente creada: %s", id_cliente)

    crear_estructura_recursiva(id_cliente, estructura_cliente, id_usuario)


def procesar_clientes() -> None:
    clientes = obtener_clientes_para_crear()
    clientes_procesados = []
    carpetas_creadas = []
    errores = []

    for cliente in clientes:
        propiedades = cliente["properties"]
        nombre = propiedades["Nombre"]["title"][0]["text"]["content"]

        prop = propiedades.get("ID", {})
        id_usuario = ""
        if prop.get("type") == "unique_id" and "unique_id" in prop:
            uid = prop["unique_id"]
            prefix = uid.get("prefix", "")
            number = uid.get("number", "")
            id_usuario = f"{prefix}{number}"

        try:
            logger.info("ID extraído: '%s' (cliente=%s)", id_usuario, nombre)
            crear_estructura_para_cliente(nombre, id_usuario)
            marcar_como_creado(cliente["id"])
            clientes_procesados.append(nombre)
            carpetas_creadas.append(f"{id_usuario}_{nombre}" if id_usuario else nombre)
        except Exception as exc:
            logger.exception("Error procesando cliente '%s'", nombre)
            errores.append(f"{nombre}: {exc}")

    registrar_log(clientes_procesados, errores, carpetas_creadas)


# -----------------------------
# Flask trigger endpoint
# -----------------------------
@app.route("/", methods=["POST"])
def trigger():
    procesar_clientes()
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

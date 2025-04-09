import re
from fuzzywuzzy import fuzz
import sys  # Importar el módulo sys para finalizar la ejecución
from typing import Optional, Dict, Any, Union
import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from bs4 import BeautifulSoup
import logging
import re
import time
import imaplib
import email
from email.header import decode_header

import pandas as pd
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
import imaplib
import msal
from datetime import datetime, timedelta
from dotenv import load_dotenv

import re

import logging
import imaplib
import re
import msal
from dotenv import load_dotenv
import jwt

from email import message_from_bytes
from email.header import decode_header
from PIL import Image
import os
import time
import logging
import imaplib
import msal
import re
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from dotenv import load_dotenv
from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text as extract_pdf_text
from PIL import Image, ImageEnhance, ImageFilter
from openai import OpenAI

# Cargar variables de entorno
load_dotenv()
 
# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
 
CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
 
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://outlook.office365.com/.default"]
 
# Configuración del correo
EMAIL = os.getenv("EMAIL")
IMAP_SERVER = "outlook.office365.com"
IMAP_PORT = 993
 
# Definir palabras clave y holder indicators
KEYWORDS = ['CERTIFICATE MASTER', 'CERTIFICATE', 'Certificate Master', 'Certificate', 'certificate', "COI","certificados"]
HOLDER_INDICATORS = ['LLC', 'INC', 'CORP', 'CO', 'LP', 'LTD', 'TRANSPORT', 'TRUCKING', "AMERICAN"]
 
# Configuración de manejo de adjuntos
MAX_EMAILS = 40
ATTACHMENT_DIR = "attachments"
if not os.path.exists(ATTACHMENT_DIR):
    os.makedirs(ATTACHMENT_DIR)

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#LEER CORREO, CON TODOS LOS ADJUNTOS Y EL CUERPO DEL CORREO#
class Authenticator:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.imap = None  
        self.get_azure_token()
 
    def get_azure_token(self):
        """Obtiene un token de acceso de Azure AD usando MSAL."""
        app = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
        token_response = app.acquire_token_for_client(scopes=SCOPES)
 
        if "access_token" not in token_response:
            logger.error("Error al obtener el token de Azure AD: %s", token_response.get("error_description"))
            raise Exception("No se pudo obtener el token de autenticación.")
 
        self.access_token = token_response["access_token"]
        self.token_expiry = datetime.now() + timedelta(seconds=token_response.get("expires_in", 3600))
        logger.info("✅ Token de Azure AD obtenido correctamente.")
 
    def connect_to_email(self):
        """Conecta a Outlook 365 vía IMAP usando OAuth2."""
        auth_string = f"user={EMAIL}\x01auth=Bearer {self.access_token}\x01\x01"
       
        try:
            self.imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            self.imap.authenticate("XOAUTH2", lambda x: auth_string.encode("utf-8"))
            logger.info("✅ Conexión IMAP exitosa.")
        except Exception as e:
            logger.error("❌ Error de conexión IMAP: %s", str(e))
            self.imap = None
            raise Exception("No se pudo conectar a IMAP.")
 
    def clean_html(self, html_content):
        """Elimina las etiquetas HTML del cuerpo del correo y retorna solo el texto limpio."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            clean_text = soup.get_text(separator=" ", strip=True)  # Limpiar el texto
            return clean_text
        except Exception as e:
            logger.error(f"Error al limpiar el HTML: {e}")
            return html_content  #
       
    def process_emails(self, mailboxes=None, max_retries=3, retry_delay=5, keywords=None):
        """Procesa correos no leídos de los buzones especificados sin marcarlos como leídos y filtra por keywords."""
        if mailboxes is None:
            print("mail boxes is none")
            mailboxes = ["INBOX"]
       
        if keywords is None:
            keywords = []  # Si no se pasan keywords, no filtra por ninguna palabra clave
        
        all_results = []
 
        for attempt in range(max_retries):
            try:
                self.connect_to_email()
 
                for mailbox in mailboxes:
                    status, _ = self.imap.select(mailbox)
                    if status != "OK":
                        logger.error(f"❌ No se pudo seleccionar el buzón {mailbox}.")
                        continue
                    # Buscar solo correos no leídos
                    status, email_ids = self.imap.search(None, "UNSEEN")
                    if status != "OK" or not email_ids[0]:
                        logger.info(f"📭 No hay correos nuevos en {mailbox}.")
                        continue
                   
                    for email_id in email_ids[0].split():
                        status, msg_data = self.imap.fetch(email_id, "(BODY.PEEK[])")
                        if status != "OK" or not msg_data or not msg_data[0]:
                            logger.error(f"Error al recuperar el correo {email_id.decode()}")
                            continue
                        
                        msg = message_from_bytes(msg_data[0][1])
                        body, attachments = self.get_email_content(msg)
                        
                        # Limpiar el cuerpo del correo (eliminar etiquetas HTML)
                        cleaned_body = self.clean_html(body)
 
                        # Obtener el asunto del correo
                        subject = msg.get("Subject", "").lower()
                        sender_email = msg.get("From")
 
                        # Filtrar si el asunto o el cuerpo contienen alguna de las palabras clave
                        if any(keyword.lower() in cleaned_body for keyword in keywords) or any(keyword.lower() in subject for keyword in keywords):
                            logger.info(f"📧 Correo de: {sender_email}")
                            logger.info(f"💬 Contenido del correo:\n{cleaned_body}")
 
                            email_info = {
                                "mailbox": mailbox,
                                "email_id": email_id.decode(),
                                "emails": self.extract_emails(body),
                                "attachments": attachments,
                                "sender": sender_email,
                                "body": cleaned_body
                            }
                            all_results.append(email_info)
 
                logger.info(f"🔄 Intento {attempt + 1} finalizado sin errores.")
                break  # Salimos del retry loop si todo va bien
 
            except Exception as e:
                logger.error(f"❌ Error en intento {attempt + 1}: {str(e)}")
                time.sleep(retry_delay)

 
        print("resultados de all results")
        print(all_results)
       
        return all_results
    
    def get_email_content(self, msg):
        """Extrae cuerpo, adjuntos, texto de imágenes y PDFs."""
        body = ""
        attachments = []
 
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "").lower()
 
            # ---- Cuerpo del correo ----
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception as e:
                    logger.error(f"Error al decodificar texto plano: {e}")
            elif content_type == "text/html" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    body = body.replace("<br>", "\n").replace("<p>", "\n")
                except Exception as e:
                    logger.error(f"Error al decodificar HTML: {e}")
 
            # ---- Adjuntos o imágenes inline ----
            if ("attachment" in content_disposition or self.is_image(part)) and part.get_filename():
                filename = decode_header(part.get_filename())[0][0]
                if isinstance(filename, bytes):
                    filename = filename.decode()
 
                filepath = os.path.join(ATTACHMENT_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
                attachments.append(filepath)
 
                # Si es imagen, hacer OCR
                if self.is_image(part):
                    ocr_text = self.extract_text_from_image(filepath)
                    body += f"\n\n[Texto OCR de imagen {filename}]:\n{ocr_text}"
 
                # Si es PDF, extraer texto
                elif filename.lower().endswith(".pdf"):
                    pdf_text = self.extract_text_from_pdf(filepath)
                    body += f"\n\n[Texto extraído de PDF {filename}]:\n{pdf_text}"
 
        if not body:
            logger.warning("⚠️ No se pudo extraer contenido del correo.")
 
        return body, attachments
 

   
 
    def extract_emails(self, text):
        """Extrae direcciones de correo electrónico del texto."""
        return list(set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)))
 
    def is_image(self, part):
        """Verifica si una parte del mensaje es una imagen (PNG, JPG, etc.)."""
        content_type = part.get_content_type()
        return content_type.startswith("image/")
 
    def extract_text_from_image(self, image_path):
        """Extrae texto de una imagen usando OCR con preprocesamiento."""
        try:
            logger.info(f"🖼️ Procesando imagen para OCR: {image_path}")
            image = Image.open(image_path)
            image = image.convert("L")  # Escala de grises
            image = ImageEnhance.Contrast(image).enhance(2)
            image = image.filter(ImageFilter.SHARPEN)
            image = image.point(lambda p: p > 150 and 255)  # Binarización
 
            text = pytesseract.image_to_string(image)
            logger.info(f"📝 Texto OCR extraído:\n{text}")
            return text.strip()
        except Exception as e:
            logger.error(f"Error OCR en imagen {image_path}: {e}")
            return ""
       
    def extract_text_from_pdf(self, pdf_path):
        """Extrae texto de un archivo PDF."""
        try:
            text = extract_pdf_text(pdf_path)
            return text.strip()
        except Exception as e:
            logger.error(f"Error al procesar el PDF {pdf_path}: {e}")
            return ""
        
    def move_email_to_folder(self, email_id, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS"):
        if not self.imap:
            raise Exception("No hay conexión IMAP activa.")
        
        try:
            # Selecciona la carpeta origen
            status, _ = self.imap.select(source_mailbox)
            if status != "OK":
                logger.error(f"❌ No se pudo seleccionar la carpeta origen: {source_mailbox}")
                return False

            # Intenta crear la carpeta destino si no existe
            try:
                self.imap.create(f'"{target_folder}"')  # Asegura comillas si hay espacios
            except Exception as e:
                logger.info(f"📁 La carpeta {target_folder} ya podría existir o no se pudo crear: {e}")
            
            #lee el correo
            self.imap.store(email_id, "+FLAGS", "\\Seen")  # Marca el correo como leído
            # Copia el correo
            result = self.imap.copy(email_id, f'"{target_folder}"')
            if result[0] != "OK":
                logger.error(f"❌ No se pudo copiar el correo {email_id} a la carpeta {target_folder}")
                return False

            # Borra el original
            self.imap.store(email_id, "+FLAGS", r"(\Deleted)")
            self.imap.expunge()

            logger.info(f"📂 Correo {email_id} movido exitosamente a {target_folder}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al mover el correo {email_id} a {target_folder}: {e}")
            return False

    def move_email_to_folder_logrados(self, email_id, source_mailbox="INBOX", target_folder="CERTIFICADOS BOT"):
        if not self.imap:
            raise Exception("No hay conexión IMAP activa.")
        
        try:
            # Selecciona la carpeta origen
            status, _ = self.imap.select(source_mailbox)
            if status != "OK":
                logger.error(f"❌ No se pudo seleccionar la carpeta origen: {source_mailbox}")
                return False

            # Intenta crear la carpeta destino si no existe
            try:
                self.imap.create(f'"{target_folder}"')  # Asegura comillas si hay espacios
            except Exception as e:
                logger.info(f"📁 La carpeta {target_folder} ya podría existir o no se pudo crear: {e}")
            
            #lee el correo
            self.imap.store(email_id, "+FLAGS", "\\Seen")  # Marca el correo como leído
            # Copia el correo
            result = self.imap.copy(email_id, f'"{target_folder}"')
            if result[0] != "OK":
                logger.error(f"❌ No se pudo copiar el correo {email_id} a la carpeta {target_folder}")
                return False

            # Borra el original
            self.imap.store(email_id, "+FLAGS", r"(\Deleted)")
            self.imap.expunge()

            logger.info(f"📂 Correo {email_id} movido exitosamente a {target_folder}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al mover el correo {email_id} a {target_folder}: {e}")
            return False

class NowCertsAPI:

    def __init__(self):
        self.base_url = "https://api.nowcerts.com/api"
        self.token = None
        self.token_expiry = None
        self.headers = {}  # Inicializar headers vacío
        self.refresh_token()


    def refresh_token(self):
        """Obtiene un nuevo token de acceso para NowCerts."""
        try:
            auth_url = f"{self.base_url}/token"
            auth_data = {
                "username": os.getenv('NOWCERTS_USERNAME'),
                "password": os.getenv('NOWCERTS_PASSWORD'),
                "grant_type": "password"
            }
            response = requests.post(auth_url, data=auth_data)
            response.raise_for_status()
            auth_response = response.json()
            self.token = auth_response.get('access_token')
            expires_in = auth_response.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            print("✅ Token de NowCerts obtenido correctamente.")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error obteniendo token de NowCerts: {str(e)}")
            exit()

    def make_request(self, method, endpoint, data=None):
        """Realiza solicitudes a la API de NowCerts manejando tokens."""
        if datetime.now() >= self.token_expiry - timedelta(minutes=5):
            self.refresh_token()

        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request(method, url, headers=headers, json=data)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            print(f"❌ Error en la solicitud: {str(e)}")
            return {"error": str(e)}


    def get_insured_list(self, top: int = 15000, skip: int = 0, order_by: str = "createDate desc", keyword: str = None) -> list:
        """Obtiene la lista de asegurados con paginación y filtro opcional por nombre comercial."""
        filter_part = f"&$filter=contains(CommercialName,'{keyword}')" if keyword else ""
        endpoint = f"/InsuredDetailList()?$count=true&$skip={skip}&$orderby={order_by}&$top={top}{filter_part}"
        response = self.make_request("GET", endpoint)
        return response.get('value', [])
    
    ##Para obtener la lista de HOLDERS##
    def get_certificate_holder_list(self, name: str = None, top: int = 5, skip: int = 0, order_by: str = "changeDate desc") -> Optional[Dict[str, Any]]:
        """Gets the list of Certificate Holders, optionally filtering by name."""
        
        endpoint = f"/CertificateHolderList?$top={top}&$skip={skip}&$orderby={order_by}"
        
        if name:
            # Encode the name to avoid issues with special characters in the URL
            name_encoded = requests.utils.quote(name)
            endpoint += f"&$filter=contains(name,'{name_encoded}')"  # Filter by name
        
        response = self.make_request("GET", endpoint)
        
        if 'value' in response and len(response['value']) > 0:
            return response['value']  # Return the filtered list
        return None
    

    def buscar_cliente(self, nombre_cliente: str) -> Optional[Dict[str, Any]]:
        """Busca un cliente o asegurado utilizando el primer nombre como filtro."""

        # Función para normalizar el texto eliminando caracteres especiales
        def normalizar_texto(texto: str) -> str:
            texto = re.sub(r"[^\w\s]", "", texto)  # Elimina caracteres especiales excepto letras y espacios
            return texto.lower().strip()

        # Normalizar el nombre del cliente de entrada
        nombre_cliente_normalizado = normalizar_texto(nombre_cliente)

        if not nombre_cliente_normalizado:
            print("⚠️ Error: Nombre del cliente vacío después de la normalización.")
            return None

        # Obtener la primera palabra del nombre para búsqueda
        primer_nombre = nombre_cliente_normalizado.split()[0]

        # Obtener la lista de asegurados que contienen el primer nombre
        insured = self.get_insured_list(keyword=primer_nombre)

        cliente_encontrado = None
        mejor_similitud = 0

        # Buscar el cliente con mayor similitud
        for insured_person in insured:
            insured_name = normalizar_texto(insured_person.get("commercialName", ""))

            # Comparar usando token_set_ratio (más robusto con cambios de orden)
            similarity = fuzz.token_set_ratio(nombre_cliente_normalizado, insured_name)

            if similarity > mejor_similitud and similarity >= 90:  # Umbral ajustable
                mejor_similitud = similarity
                cliente_encontrado = insured_person

        # Verificar si se encontró el cliente
        if cliente_encontrado:
            print(f"✅ Cliente encontrado: {cliente_encontrado} (Similitud: {mejor_similitud}%)")
        else:
            print("❌ El cliente no se encuentra en la base de datos.")

        return cliente_encontrado
    
    def buscar_holder(self, nombre_holder): 
        """Busca un holder utilizando el primer nombre como filtro.""" 
        # Dividir el nombre del holder por espacios y usar la primera palabra
        primer_nombre = nombre_holder.split()[0]

        # Obtener la lista de holders que contienen el primer nombre 
        holder_list = self.get_certificate_holder_list(name=primer_nombre)
        
        print("Holder list:")
        print(holder_list)

        # Si holder_list es None, evitar que el ciclo inicie
        if not holder_list:  
            print("El holder no se encuentra en ninguna de las bases de datos.")
            
            return None

        # Inicializar holder_encontrado como None 
        holder_encontrado = None

        # Buscar el holder con mayor similitud
        for holder_person in holder_list: 
            holder_name = holder_person.get("name", "")  # Usamos 'name' para buscar el nombre del holder
            similarity = fuzz.token_sort_ratio(nombre_holder.lower(), holder_name.lower())  # Usamos token_sort_ratio
            if similarity >= 90:
                holder_encontrado = holder_person
                break  # Salir del bucle al encontrar el primer holder

        # Verificar si se encontró el holder
        if holder_encontrado:
            print(f"Holder encontrado: {holder_encontrado}")
        else:
            print("El holder no se encuentra en ninguna de las bases de datos.")

        return holder_encontrado

    def get_vehicle_list(self, insured_database_id: str = None) -> List[Dict[str, Any]]:
        """
        Gets the list of visible vehicles for a specific insured_database_id.
        
        Args:
            insured_database_id: Database ID of the insured to filter vehicles
                
        Returns:
            List of visible vehicles or empty list if none found
        """
        if not insured_database_id:
            logger.warning("insured_database_id is required to get the vehicle list")
            return []
            
        # Build the endpoint with the specific filter
        endpoint = f"/VehicleList()?$filter=insuredDatabaseId eq {insured_database_id}"
                
        logger.info(f"Getting vehicle list with endpoint: {endpoint}")
        
        response = self.make_request("GET", endpoint)
        
        if 'value' in response:
            # Filter only visible vehicles
            visible_vehicles = [vehicle for vehicle in response['value'] if vehicle.get('visible', False) is True]
            logger.info(f"Found {len(visible_vehicles)} visible vehicles out of a total of {len(response['value'])}")
            return visible_vehicles
        
        logger.warning("No vehicles found or unexpected response format")
        return []

    def get_active_drivers(self, insured_database_id: str = None) -> List[Dict[str, str]]:
        """Gets the list of active drivers for a specific insured_database_id."""
        if not insured_database_id:
            logger.warning("❌ insured_database_id is required to get the driver list.")
            return []
        
        endpoint = f"/DriverList()?$filter=insuredDatabaseId eq {insured_database_id}"
        logger.info(f"📡 Getting driver list with endpoint: {endpoint}")
        
        response = self.make_request("GET", endpoint)
        print(f"📜 API response: {json.dumps(response, indent=4)}")  # View entire response

        if 'value' in response:
            active_drivers = [{"id": driver["id"]} for driver in response["value"]]
            logger.info(f"✅ Found {len(active_drivers)} active drivers")
            return active_drivers
        
        logger.warning("⚠️ No drivers found or unexpected response format.")
        return []


    def search_customer(self, email_recibir: str) -> Union[Dict[str, Any], str]:
        """Busca el certificado más reciente del cliente usando su correo."""
        endpoint = ("/CertificatesList()?$count=true&$orderby=changeDate desc"
                    f"&$filter=insuredEmail eq '{email_recibir}' and acordFormNumber eq 25101"
                    "&$skip=0&$top=1")

        try:
            url = self.base_url + endpoint
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(url, headers=headers)
            data = response.json()

            print("Respuesta completa:", data)

            # Verifica si hay resultados en la clave "value"
            if "value" in data and isinstance(data["value"], list) and len(data["value"]) > 0:
                certificado = data["value"][0]
                resultado = {
                    "database_id_almacenado": certificado.get("databaseId"),
                    "insured_database_id_almacenado": certificado.get("insuredDatabaseId"),
                    "nombre_certificado": certificado.get("name"),
                    "email": certificado.get("insuredEmail"),
                    "fecha_creacion": certificado.get("createDate")
                }
                return resultado
            else:
                return "No se encontró con ese correo"

        except Exception as e:
            print(f"Error en la solicitud: {e}")
            return "Error al consultar el API"

    def send_certificate(self,
                        emails: str,
                        certificate_id: str,
                        insured_database_id: str,
                        insured_first_name: str,
                        insured_last_name: str,
                        certificate_holder: List[Dict[str, str]],
                        email_subject: str,
                        description: str,
                        insured_commercial_name: str = "",
                        send_copy_to_insured_email: bool = True,
                        send_copy_to_insured_fax: bool = False,
                        send_cc_to_me: bool = True,
                        fax: str = "",
                        vehicle_ids: List[str] = None,
                        driver_ids: List[str] = None,
                        equipment_ids: List[str] = None,
                        property_ids: List[str] = None,
                        show_description_in_acord101: int = 1) -> Dict[str, Any]:
        """
        Sends a certificate using the NowCerts API.
        """
        endpoint = "/SendCertificate/SendCertificate"
    
        data = {    
            "Emails": emails,
            "Fax": fax,
            "SendCopyToInsuredEmail": send_copy_to_insured_email,
            "SendCopyToInsuredFax": send_copy_to_insured_fax,
            "SendCCToMe": send_cc_to_me,
            "CertificateId": certificate_id,
            "InsuredDatabaseId": insured_database_id,
            "InsuredFirstName": insured_first_name,
            "InsuredLastName": insured_last_name,
            "insuredCommercialName": insured_commercial_name,
            "certificateHolder": certificate_holder,
            "VehicleIds": vehicle_ids or [],
            "DriverIds": driver_ids or [],
            "EquipmentIds": equipment_ids or [],
            "PropertyIds": property_ids or [],
            "EmailSubject": email_subject,
            "Description": description,
            "ShowDescriptionInAcord101": show_description_in_acord101
        }

        try:
            response = self.make_request("POST", endpoint, data)
            print("API response:", response)
            return response

        except Exception as e:
            logger.error(f"Error sending certificate: {str(e)}")
            return {"error": str(e)}



#LLAMADO A DEEP SEEK API# 


#ENCONTRAR EL CLIENTE EN LA BASE DE DATOS DE NOWCERTS#

def obtener_nombre_cliente(email_body):
 
    client=OpenAI(api_key=os.getenv("api_key_open"),
                base_url="https://openrouter.ai/api/v1")


    chat_cliente = client.chat.completions.create(
        model="deepseek/deepseek-r1-distill-llama-70b:free",
        messages=[
            {
                "role": "user",
                "content": f"""EXTRACT ONLY THE INSURED'S NAME FROM THIS EMAIL. 
                RULES:
                1. Return only the name if found
                2. If multiple names: 'SEVERAL CLIENTS REQUEST'
                3. If none: 'CLIENT NOT FOUND IN EMAIL'
                
                EMAIL CONTENT: {email_body}"""
            }
        ]
    )

    response = chat_cliente  # Renombrado para claridad
    print("Respuesta completa de la API:", response)
    return chat_cliente.choices[0].message.content

def obtener_nombre_holder(email_body):
 
    client=OpenAI(api_key=os.getenv("api_key_open"),
                base_url="https://openrouter.ai/api/v1")


    chat_holder = client.chat.completions.create(
        model="deepseek/deepseek-r1-distill-llama-70b:free",
        messages=[
            {
                "role": "user",
               "content": f"""
                The email provided contains a request for a Certificate of Insurance (COI) related to truck insurance. Your task is to extract only the HOLDER'S NAME, which is similar to "whom it is directed to."

                Instructions:
                - If multiple holder names are mentioned, respond only with the names, separated by "--".
                - If the holder name is not found, respond with: "HOLDER NOT FOUND IN EMAIL".
                - If the email is a **verification request** (i.e., the certificate is requested only for verification purposes and only the client is named), respond with: "VERIFICATION REQUEST".

                Provide only the required output. Do not include explanations, additional context, or extra responses.

                TEXT: {email_body}
                """
            }
        ]
    )

    response = chat_holder  # Renombrado para claridad
    print("Respuesta completa de la API PARA EL HOLDER:", response)
    # Extraer el contenido de la respuesta correctamente
    response = chat_holder.choices[0].message.content

    # Verificar si se encontraron holders
    if 'HOLDER NOT FOUND IN EMAIL' in response:
        return response
    
    # Asegurar que los nombres están correctamente separados por '--'
    return response


def limpiar_attachments():
    for filename in os.listdir(ATTACHMENT_DIR):
        file_path = os.path.join(ATTACHMENT_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ Archivo eliminado: {file_path}")
        except Exception as e:
            logger.error(f"❌ Error al eliminar archivo {file_path}: {e}")

def main():

    # Limpiar carpeta de attachments al iniciar
    limpiar_attachments()
    # ================================
    #  Buscar INFORMACIÓN DEL CORREO NO LEIDO
    # ================================
    # Crear instancia de Authenticator
    auth = Authenticator()
    
    # Procesar correos no leídos
    result = auth.process_emails(mailboxes=["INBOX"], keywords=KEYWORDS)

    # Si hay un correo, imprimirlo
    if result:
        email_body_dic = {
            "Sender": result[0]['sender'],
            "Body": result[0]['body'],
            "Attachments": result[0]['attachments'],
            "Emails": ", ".join(result[0]['emails'])  # Convertir lista de emails en una cadena separada por comas
        }

        # Convertir el diccionario completo a un string legible
        email_body_str = f"""
Sender: {email_body_dic['Sender']}
Body:
{email_body_dic['Body']}
Attachments: {email_body_dic['Attachments']}
Emails: {email_body_dic['Emails']}
"""

        print("Email Body:")
        print(email_body_str)
    else:
        print("No se encontraron correos que coincidan con las palabras clave.")
        sys.exit()

   #todos los correos a los que se deben enviar los certificados
    ALL_Email = {email_body_dic['Emails']}
    ALL_email_string = list(ALL_Email)[0] 
    print("ALL Emails string:")        
    print(ALL_email_string)
    # id del correo

    id_Email_leido= result[0]['email_id']

    # ================================
    #  Buscar INFORMACIÓN USANDO DEEP SEEK API
    # ================================


    email_body = email_body_str
    email_body = email_body[:2000]  # Ajusta según el límite de tokens del modelo

    nombre_cliente = obtener_nombre_cliente(email_body)

    if "<tool_response>" in nombre_cliente and nombre_cliente.count("<tool_response>") > 3:
        print("⚠️ Respuesta inválida (tool_response detectado).")
    elif nombre_cliente == "CLIENT NO FOUND IN EMAIL":
        print("❌ El cliente no fue encontrado en el correo.")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")
        sys.exit()
    elif nombre_cliente == "SEVERAL CLIENTS REQUEST":
        print("⚠️ Se detectaron múltiples clientes en la solicitud. Saliendo...")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")
        sys.exit()
    else:
        print(f"✅ Cliente identificado: {nombre_cliente}")

        
    nombre_holder = obtener_nombre_holder(email_body)

    if nombre_holder is None or nombre_holder == "HOLDER NOT FOUND IN EMAIL":
        print("❌ El holder no fue encontrado en el correo o la respuesta fue None.")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")
        print("El correo se ha movido a la carpeta CERTIFICADOS FALLIDOS.")
        sys.exit()
    elif nombre_holder == "VERIFICATION REQUEST":
        print("⚠️ Solicitud de VERIFICACIÓN detectada ")
        nombre_holder="Certificate of Verification"
    elif "<tool_response>" in nombre_holder and nombre_holder.count("<tool_response>") > 3:
        print("⚠️ Respuesta inválida (tool_response detectado).")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")
        sys.exit()
    else:
        print(f"✅ Holder identificado: {nombre_holder}")

    api = NowCertsAPI()

    # ================================
    #  Buscar el CLIENTE utilizando 
    #  la función buscar_cliente
    # ================================
    cliente_encontrado =  api.buscar_cliente(nombre_cliente)
    print("buscando cliente:")
    print(nombre_cliente)
    

    if cliente_encontrado == "CLIENT NO FOUND IN EMAIL" or cliente_encontrado is None:
        # Si no se encuentra el cliente, mostrar un mensaje
        print("EL CLIENTE NO FUE ENCONTRADO")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")
        print("El correo se ha movido a la carpeta CERTIFICADOS FALLIDOS.")
        sys.exit()  # Finalizar la ejecución del script
    else:
        # Si se encuentra un cliente, mostrar los datos completos
        print("\nCliente encontrado. Datos completos del cliente:")
        print(cliente_encontrado)  # Los datos completos del cliente se mostrarán aquí

        # Extraer el ID y el correo electrónico del insured
        id_insured = cliente_encontrado.get("id", None)  # Si no existe la clave "id", devuelve None
        email_insured = cliente_encontrado.get("eMail", None)  # Extraer el email si existe
        first_name_insured = cliente_encontrado.get("firstName", None)  # Extraer el email si existe
        last_name_insured = cliente_encontrado.get("lastName", None)  # Extraer el email si existe
        commercial_name_insured = cliente_encontrado.get("commercialName", None)  # Extraer el email si existe
        print(f"ID del insured: {id_insured}")
        print(f"Correo electrónico del insured: {email_insured}")

        
    # ================================
    #  Buscar INFORMACIÓN ZAPIER GET CERTIFICATES
    # ================================
    # Search customer by email
    customer = api.search_customer(email_insured)
    if not customer:
        logger.info("Customer not found. Exiting...")
        print("No se encontró el cliente.")
        auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")        
        print("El correo se ha movido a la carpeta CERTIFICADOS FALLIDOS.")
        sys.exit()

    logger.info(f"Customer found: {customer}")
    print("El customer es:")
    print(customer)

    # ===== Extraer variables del diccionario si existen ====

    if isinstance(customer, dict):
        database_id_almacenado = customer.get("database_id_almacenado")
        insured_database_id_almacenado = customer.get("insured_database_id_almacenado")
        
        print(f"database_id_almacenado: {database_id_almacenado}")
        print(f"insured_database_id_almacenado: {insured_database_id_almacenado}")
    else:
        print("No se pudo extraer información porque el cliente no fue encontrado.")
    



    # ================================
    #  Buscar VECHICULOS
    # ================================

    # Inicializar `vehicle_ids_list` antes de su uso
    vehicle_ids_list = []
    # Obtener la lista de vehículos
    vehicles = api.get_vehicle_list(insured_database_id_almacenado)

    if vehicles:
        print(f"\n🚚 Found {len(vehicles)} visible vehicles:")
        vehicle_ids_list = [vehicle.get("id") for vehicle in vehicles if vehicle.get("id")]

        for i, vehicle in enumerate(vehicles, 1):
            print(f"\nVehicle {i}:")
            print(f"  ID: {vehicle.get('id')}")
            print(f"  Make: {vehicle.get('make')}")
            print(f"  Model: {vehicle.get('model')}")
            print(f"  VIN: {vehicle.get('vin')}")
            print(f"  Year: {vehicle.get('year')}")
            print(f"  Value: ${vehicle.get('value')}")
        print("\n📋 List of vehicle IDs:")
        print(vehicle_ids_list)
    else:
        print("❌ No vehicles found for this insured.")

    # Verificar que `vehicle_ids_list` no sea None antes de su uso
    if vehicle_ids_list is None:
        vehicle_ids_list = []


    # ================================
    #  Buscar ACTIVE DRIVERS
    # ================================
        # Get active drivers
    driver_ids_list = api.get_active_drivers(insured_database_id_almacenado)


    # ================================
    #  Buscar el HOLDER utilizando 
    #  la función buscar_holder
    # ================================
    # Separar los holders en una lista
    
    partes_del_holder = nombre_holder.split("--")

    # Recorrer cada parte del nombre del holder
    for parte in partes_del_holder:
        # Limpiar espacios extra
        parte = parte.strip()

        # Buscar al holder utilizando la función buscar_holder
        holder_encontrado = api.buscar_holder(parte)

        if holder_encontrado is None or holder_encontrado == "HOLDER NO FOUND IN EMAIL":
            # Si no se encuentra el holder, mostrar un mensaje
            print(f"EL HOLDER {parte} NO FUE ENCONTRADO")
            auth.move_email_to_folder(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS FALLIDOS")        
            print("El correo se ha movido a la carpeta CERTIFICADOS FALLIDOS.")
            sys.exit()
          
        
        else:
            # Si se encuentra el holder, mostrar los datos completos
            print(f"\nHolder encontrado: {parte}. Datos completos del holder:")
            print(holder_encontrado)  # Los datos completos del holder se mostrarán aquí

            # Extraer el ID del holder
            holder_id = holder_encontrado.get("databaseId", None)  # Si no existe la clave "databaseId", devuelve None
            print(f"ID del holder: {holder_id}")

            try:
                response = api.send_certificate(
                    emails=ALL_email_string, #email_body_dic.get("Emails", ""),  # Extraer los emails formateados
                    certificate_id=database_id_almacenado,
                    insured_database_id=insured_database_id_almacenado,
                    insured_first_name=first_name_insured,
                    insured_last_name=last_name_insured,
                    insured_commercial_name=commercial_name_insured,
                    certificate_holder=[{"id": holder_id}],
                    email_subject="Response to Certificate Request - COI",
                    description = (
                        "Warm greetings,\n\n"
                        "Please find attached the requested user certificate.\n"
                        "Let us know if you need any further assistance.\n\n"
                        "Best regards,\n"
                        "Customer Service\n"
                        "INTRUCKS"
                    ),
                    vehicle_ids=[{"id": vid} for vid in vehicle_ids_list],
                    driver_ids=driver_ids_list
                )

                logger.info("✅ Server response when sending certificate:")
                logger.info(json.dumps(response, indent=2))
                auth.move_email_to_folder_logrados(id_Email_leido, source_mailbox="INBOX", target_folder="CERTIFICADOS BOT")
            except Exception as e:
                logger.error(f"❌ Error sending certificate: {str(e)}")



def pruebas():
    
    api = NowCertsAPI()


    # Inicializar `vehicle_ids_list` antes de su uso
    vehicle_ids_list = []
    insured_database_id_almacenado= "4a6992e5-22a8-454b-acf2-ff80624bdddc"
    # Obtener la lista de vehículos
    vehicles = api.get_vehicle_list(insured_database_id_almacenado)

    if vehicles:
        print(f"\n🚚 Found {len(vehicles)} visible vehicles:")
        vehicle_ids_list = [vehicle.get("id") for vehicle in vehicles if vehicle.get("id")]

        for i, vehicle in enumerate(vehicles, 1):
            print(f"\nVehicle {i}:")
            print(f"  ID: {vehicle.get('id')}")
            print(f"  Make: {vehicle.get('make')}")
            print(f"  Model: {vehicle.get('model')}")
            print(f"  VIN: {vehicle.get('vin')}")
            print(f"  Year: {vehicle.get('year')}")
            print(f"  Value: ${vehicle.get('value')}")
        print("\n📋 List of vehicle IDs:")
        print(vehicle_ids_list)
    else:
        print("❌ No vehicles found for this insured.")

    # Verificar que `vehicle_ids_list` no sea None antes de su uso
    if vehicle_ids_list is None:
        vehicle_ids_list = []



 




        




        
if __name__ == "__main__":
    main()

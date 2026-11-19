from extras.scripts import Script
from utilities.exceptions import AbortScript
from tenancy.models import Tenant
from ipam.models import IPAddress

# Google Libs
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError



class GoogleSheetUpdate(Script):
    class Meta(Script.Meta):
            name = "GoogleSheetUpdate"
            description = "Update Google Sheet: Cyber Base"
            scheduling_enabled = False


    def append_row(self, gs_service, spreadsheet_id, page_name, rows):
        body = { "values": [rows] }

        try:
            result = gs_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{page_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            self.log_success(f"{result.get('updates').get('updatedRows')} rows added")

        except HttpError as error:
            raise AbortScript(f"An error occurred: {error}")


    def create_header(self, gs_service, spreadsheet_id, page_name):
        try:
            gs_service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=f"{page_name}!1:1", valueInputOption="RAW", body={"values": [['edrpou', 'org', 'ip', 'region', 'moniker', 'kontrol', 'comment']]}).execute()
            self.log_success(f"Page header successfully added to page: {page_name}")
        
        except HttpError as error:
            raise AbortScript(f"Error during added header row to page {page_name}: {error}")


    def create_gs_page(self, gs_service, spreadsheet_id, page_name):
        body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": page_name
                    }
                }
            }
        ]
        }

        try:
            gs_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            self.log_success(f"Page {page_name} successfully created")

        except HttpError as error:
            raise AbortScript(f"Error during page creation: {error}")

    def run(self, data, commit):
        # 1. Google AUTH data        
        # 1. Google API Token
        GOOGLE_TOKEN = data.get("google_api_token")

        if not GOOGLE_TOKEN:
            raise AbortScript('Missing required attribute: {"google_api_token": "token"}')

        try:
            token_info = json.loads(GOOGLE_TOKEN) if isinstance(GOOGLE_TOKEN, str) else GOOGLE_TOKEN
        except json.JSONDecodeError:
            raise AbortScript("Invalid Google API token JSON format")

        GS_CREAD = Credentials.from_authorized_user_info(
            token_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        GS_SERVICE = build("sheets", "v4", credentials=GS_CREAD)

        # 2. Spreadsheet information
        SPREADSHEET_ID = data.get("gs_table_id")


        # 3. Data about Asset
        ip_id = data.get('id')
        IP_ADDRESS_OBJECT = IPAddress.objects.get(pk=ip_id)
        self.log_debug(f"IP Address object extracted: {IP_ADDRESS_OBJECT}")


        # 4. Organization data
        if not data.get('tenant'):
            raise AbortScript('IP Address do not belong to any Tenant')

        tenant_id = data.get('tenant').get('id')

        TENANT_OBJECT = Tenant.objects.get(pk=tenant_id)
        self.log_debug(f"Tenant object extracted: {TENANT_OBJECT}")

        REGION_ID = TENANT_OBJECT.cf.get("region", {}).slug
        self.log_debug(f"Region ID extracted: {REGION_ID}")

        REGION_NAME = TENANT_OBJECT.cf.get("region", {}).name
        self.log_debug(f"Region name extracted: {REGION_NAME}")
        
        if not REGION_ID:
            raise AbortScript('Tenant do not belong to any Region')
        

        # 5. Перевірка сторінки регіону
        REGION_PAGE_NAME = str(REGION_ID).upper() + ": " + REGION_NAME
        self.log_info(f"Google Sheet page name: {REGION_PAGE_NAME}")

        GS_INFO = GS_SERVICE.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        self.log_debug(f"Google Sheet Info: {GS_INFO}")

        GS_PAGE = { page["properties"]["title"] for page in GS_INFO.get("sheets", [])}
        self.log_debug(GS_PAGE)

        if REGION_PAGE_NAME not in GS_PAGE:
            self.create_gs_page(GS_SERVICE, SPREADSHEET_ID, REGION_PAGE_NAME)

        # 5.1 Перевірка хедера
        GS_PAGE_HEADER = GS_SERVICE.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{REGION_PAGE_NAME}!1:1").execute()
        GS_PAGE_HEADER_VALUES = GS_PAGE_HEADER.get("values")
        self.log_debug(GS_PAGE_HEADER_VALUES)

        if not GS_PAGE_HEADER_VALUES:
           self.log_warning(f"Page {REGION_PAGE_NAME} missing header row")
           self.create_header(GS_SERVICE, SPREADSHEET_ID, REGION_PAGE_NAME)
        
        # 6. Format new row that should be append
        row = [ TENANT_OBJECT.cf.get("edrpou", None),
                TENANT_OBJECT.description,
                str(IP_ADDRESS_OBJECT.address).split("/")[0],
                REGION_NAME,
                'moniker',
                'kontrol', 
                'comment'
                ]
        self.log_info(f"Row that should be append: {row}")
        self.append_row(GS_SERVICE, SPREADSHEET_ID, REGION_PAGE_NAME, row)

        
        
        
        


import requests

from bs4 import BeautifulSoup

from extras.scripts import Script
from utilities.exceptions import AbortScript
from tenancy.models import Tenant
from dcim.models import Region
from extras.models import Tag  

class YouControlEnrichment(Script):
    class Meta(Script.Meta):
        name = "YouControl"
        description = "Enrich organization data with YouControl"
        scheduling_enabled = False

    def youcontrol_search_by_edrpou(self, edrpou: str = None):
        if not edrpou:
            raise Exception("Missing edrpou argument")

        url = "https://youcontrol.com.ua/catalog/company_details/"
        full_url = url + edrpou + "/"

        headers = {
            "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
            )
        }
        data = requests.get(full_url, headers=headers)

        if data.status_code == 404:
            return None

        if data.status_code != 200:
            raise Exception(
                f"YouControl return status code: {data.status_code}, "
                f"with {data.text} error"
                )

        return data.text

    def youcontrol_result_parser(self, data):
        you_control_data = {}

        soup = BeautifulSoup(data, "html.parser")
        containers = soup.find_all("div", {"class": "seo-table-contain"})

        for container in containers:
            seo_table = container.find("div", {"class": "seo-table"})
            seo_table_rows = seo_table.find_all("div", {"class": "seo-table-row"})

            for row in seo_table_rows:
                key = row.find("div", {"class": "seo-table-col-1"})
                if key:
                    key = key.get_text().strip().split("\n")[0].strip()
                
                values = row.find(
                        ["span", "p", "div"],
                        {"class": "seo-table-col-2"},)
                if values:
                
                    values = values.get_text().strip().split("\n")

                    if key == "Повне найменування юридичної особи":
                        you_control_data["name_full"] = values[0].strip() or None

                    if key == "Найменування відокремленого підрозділу":
                        you_control_data["name_full"] = values[0].strip() or None

                    if key == "Скорочена назва":
                        you_control_data["name_short"] = values[0].strip() or None

                    if key == "Назва англійською":
                        you_control_data["name_en"] = values[0].strip() or None

                    if key == "Статус юридичної особи":
                        you_control_data["status"] = values[0].strip() or  None

                    if key == "Статус з ЄДР":
                        you_control_data["status_with_edr"] = values[0].strip() or None

                    if key == "Код ЄДРПОУ":
                        you_control_data["edrpou"] = values[0].strip() or None

                    if key == "Дата реєстрації":
                        you_control_data["registration_date"] = values[0][0:10] or None

                    if key == "Організаційно-правова форма":
                        you_control_data["loyal_form"] = values[0].strip() or None

                    if key == "Види діяльності":
                        if values[0].strip() == "Основний:":
                            you_control_data["kved_main"] = values[2].strip() or None
                    
                            you_control_data["kved_secondary"] = list( i.strip() for i in values[-3:] if i!='') or None
                        else:
                            you_control_data["kved_main"] = values or None                    

                    if key == "Контактна інформація":
                        you_control_data["address"] = values[3].strip() or values[2].strip() or None

                        if you_control_data["address"]:
                            address = you_control_data["address"]
                            you_control_data["city"] = address.split(",")[-3].strip() or None
                            you_control_data["region"] = address.split(",")[2].strip() or None


                    if key == "Перелік засновників/учасників юридичної особи":
                        you_control_data["parent_org_name"] = values[0].strip() or None
                        you_control_data["parent_org_edrpou"] = values[2].strip() or None
                        you_control_data["parent_org_address"] = values[5].strip() or None

                    if key == "Дані про відокремлені підрозділи юридичної особи":
                        you_control_data["child_orgs"] = []
                        print(values)

        return you_control_data

    def run(self, data, commit):
        self.log_debug(f"{data}")
        tenant = Tenant.objects.get(pk = data.get('id'))

        tenant_edrpou = data.get('custom_fields', {}).get("edrpou")
        self.log_info(f"Tenant edrpou: {tenant_edrpou}")

        youcontrol_data = self.youcontrol_search_by_edrpou(edrpou = tenant_edrpou)

        # Missing data in youcontrol
        if not youcontrol_data:
            self.log_info("The are no data about organization with edrpou {} in YouControl") 
            tag, created = Tag.objects.get_or_create( name="youcontrol", defaults={'slug': 'youcontrol'})
            tag, created = Tag.objects.get_or_create( name="youcontrol", defaults={'slug': 'youcontrol-missing'})
            tenant.tags.add(tag)
        
        else:
    
            youcontrol_parsed_data = self.youcontrol_result_parser(data = youcontrol_data)
                        
            self.log_info(f"YouControl Data: {youcontrol_parsed_data}")
            tenant.custom_field_data["full_address"] = youcontrol_parsed_data.get("address", "")

            if youcontrol_parsed_data["region"] and youcontrol_parsed_data.get("region", "").startswith("місто"):
                search_word = youcontrol_parsed_data.get("tenant_region", "").split(" ")[1]
                self.log_debug(f"Region search word: {search_word}")

            else:
                if youcontrol_parsed_data["region"]:
                    search_word = youcontrol_parsed_data.get("region", "").split(" ")[0]
                    self.log_debug(f"Region search word: {search_word}")

                else:
                    search_word = "Відсутній в YouControl"
                    self.log_debug(f"Region search word is empty: {search_word}")

            region = Region.objects.filter(name__icontains=search_word).first()

            if region:
                tenant.custom_field_data["region"] = region_id.id

            if youcontrol_parsed_data.get("parent_org_edrpou"):
                self.log_debug(f"Find Parent Tenant {youcontrol_parsed_data.get("parent_org_edrpou")} with edrpou {youcontrol_parsed_data.get("parent_org_edrpou")} in YouControl")

            
                try:  
                    parent_tenant = Tenant.objects.get(  
                    custom_field_data__edrpou=youcontrol_parsed_data.get("parent_org_edrpou")  
                )  
                    self.log_debug(f"Parent Tenant exist in NetBox - {parent_tenant}")  
                    tenant.custom_field_data["parent_tenant"] = parent_tenant.id

                except Tenant.DoesNotExist:  
                    self.log_debug(  
                        f"Parent Tenant {youcontrol_parsed_data.get('parent_org_name')} "  
                        f"with edrpou {youcontrol_parsed_data.get('parent_org_edrpou')} not in NetBox" )

            tenant.description = youcontrol_parsed_data.get("name_full")
            self.log_debug(f"Update Tenant description (full name): {tenant.description}")


            if commit:
                self.log_success(f"Tenant suucessfully updated: {tenant}")
                tenant._changelog_message = "Automatic update from YouControl"
                tenant.save()
                
                tag, created = Tag.objects.get_or_create( name="youcontrol", defaults={'slug': 'youcontrol'})
                tenant.tags.add(tag)
            


from extras.scripts import Script
from netbox_dns.models import (Zone, Record)
from netbox_plugin_dns.choices import (RecordTypeChoices)


class DNSZoneReconciliation(Script):

    class Meta:
        name = "DNS Zone Reconciliation"
        description = (
            "Reassign existing A records to a newly created "
            "DNS Zone when their FQDN belongs to that Zone."
        )
        commit_default = False

    def run(self, data, commit):

        # 1. Event Rule - New DNS Zone created

        NEW_DNS_ZONE_ID = data.get("id")
        NEW_DNS_ZONE_OBJECT = Zone.objects.get(pk=NEW_DNS_ZONE_ID)

        NEW_DNS_ZONE = NEW_DNS_ZONE_OBJECT.name
        self.log_info( f"Target Zone: {NEW_DNS_ZONE}", NEW_DNS_ZONE_OBJECT)

        NEW_DNS_ZONE_SPLITTED = NEW_DNS_ZONE.split(".")
    
        NEW_DNS_ZONE_TIER = len(NEW_DNS_ZONE.split("."))        
        self.log_info( f"Target Zone Len: {NEW_DNS_ZONE_TIER}")

        zone_tier = NEW_DNS_ZONE_TIER

        while zone_tier != 2:
            zone_tier -= 1
            CANDIDATE = ".".join(NEW_DNS_ZONE_SPLITTED[NEW_DNS_ZONE_TIER - zone_tier:])
            self.log_info(f"Posible zone to check: {CANDIDATE}")

            CANDIDATE_DNS_ZONE_OBJECT = Zone.objects.filter(name=CANDIDATE).first()

            if CANDIDATE_DNS_ZONE_OBJECT:
                self.log_info(f"Candidate {CANDIDATE} zone exist with id: {CANDIDATE_DNS_ZONE_OBJECT.id}", CANDIDATE_DNS_ZONE_OBJECT)

                CANDIDATE_RECORDS = Record.objects.filter(zone_id=CANDIDATE_DNS_ZONE_OBJECT.id, type=RecordTypeChoices.A)

                if not CANDIDATE_RECORDS:
                    self.log_info(f"The are no DNS Records type A exist")
                
                else:
                    self.log_info(f"DNS Records: {CANDIDATE_RECORDS}")

                







            else:
                self.log_info(f"The are no DNS Zone in netbox for candidate {CANDIDATE}")

            # Для кандидата зони, отримати перелік Рекордів
            # Для кожного Рекорда перевірити чи він 
            # 1. ІДЕНТИЧНИЙ до нової зони - видалити
            # 2. Закінчується на поточну зону  - переасайн



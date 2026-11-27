
from extras.scripts import Script
from netbox_dns.models import (Zone, Record)


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
        self.log_info( f"Target Zone: {NEW_DNS_ZONE}")

        NEW_DNS_ZONE_SPLITTED = NEW_DNS_ZONE.split(".")
    
        NEW_DNS_ZONE_TIER = len(NEW_DNS_ZONE.split("."))        
        self.log_info( f"Target Zone Len: {NEW_DNS_ZONE_TIER}")

        zone_tier = NEW_DNS_ZONE_TIER

        while zone_tier != 2:
            zone_tier -= 1
            self.log_info("Posible zone to check: ",".".join(NEW_DNS_ZONE_SPLITTED[NEW_DNS_ZONE_TIER - zone_tier:]))


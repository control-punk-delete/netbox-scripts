
from extras.scripts import Script
from netbox_dns.models import Zone, Record
from django.db import transaction


# Safety switch:
# True  = report only, no database modifications
# False = move records
DRY_RUN = True

RECORD_TYPE = "A"


def normalize_domain(value):
    return str(value or "").strip().lower().rstrip(".")


def is_subdomain_or_apex(fqdn, zone_name):
    fqdn = normalize_domain(fqdn)
    zone_name = normalize_domain(zone_name)

    return fqdn == zone_name or fqdn.endswith("." + zone_name)


def get_relative_name(fqdn, zone_name):
    fqdn = normalize_domain(fqdn)
    zone_name = normalize_domain(zone_name)

    if fqdn == zone_name:
        return "@"

    if fqdn.endswith("." + zone_name):
        return fqdn[:-(len(zone_name) + 1)]

    return None


class DNSZoneReconciliation(Script):

    class Meta:
        name = "DNS Zone Reconciliation"
        description = (
            "Reassign existing A records to a newly created "
            "DNS Zone when their FQDN belongs to that Zone."
        )
        commit_default = False

    def run(self, data, commit):

        # Event Rule context
        event = getattr(self, "event", None) or {}

        zone_id = event.get("object_id")

        if not zone_id:
            self.log_failure(
                "Unable to determine the newly created DNS Zone ID "
                "from Event Rule context."
            )
            return

        try:
            target_zone = Zone.objects.select_related("view").get(
                pk=zone_id
            )
        except Zone.DoesNotExist:
            self.log_failure(
                f"DNS Zone with ID {zone_id} was not found."
            )
            return

        target_zone_name = normalize_domain(target_zone.name)
        target_view_id = target_zone.view_id

        self.log_info(
            f"Target Zone: {target_zone_name}"
        )
        self.log_info(
            f"View ID: {target_view_id}"
        )
        self.log_info(
            f"DRY_RUN: {DRY_RUN}"
        )

        # Get A records from the same DNS View,
        # excluding records already in the target Zone.
        records = (
            Record.objects
            .filter(
                type=RECORD_TYPE,
                zone__view_id=target_view_id
            )
            .exclude(zone_id=target_zone.id)
            .select_related("zone")
        )

        examined = 0
        matched = 0
        moved = 0
        duplicates = 0

        for record in records.iterator():

            examined += 1

            # Reconstruct FQDN using current Zone + Record name.
            fqdn = normalize_domain(record.fqdn)

            if not is_subdomain_or_apex(
                fqdn,
                target_zone_name
            ):
                continue

            new_name = get_relative_name(
                fqdn,
                target_zone_name
            )

            if new_name is None:
                continue

            matched += 1

            old_zone_name = normalize_domain(record.zone.name)
            old_record_name = record.name

            # Check for an exact duplicate in the destination:
            # same Zone, type, relative name and value.
            duplicate_exists = Record.objects.filter(
                zone_id=target_zone.id,
                type=record.type,
                name=new_name,
                value=record.value
            ).exclude(pk=record.pk).exists()

            if duplicate_exists:
                duplicates += 1

                self.log_warning(
                    f"DUPLICATE - skipped: {fqdn} | "
                    f"IP: {record.value} | "
                    f"Destination: {target_zone_name}/{new_name}"
                )
                continue

            self.log_info(
                f"MATCH: {fqdn} | IP: {record.value}"
            )
            self.log_info(
                f"  FROM: {old_zone_name} / {old_record_name}"
            )
            self.log_info(
                f"  TO:   {target_zone_name} / {new_name}"
            )

            if DRY_RUN:
                continue

            try:
                with transaction.atomic():
                    record.zone = target_zone
                    record.name = new_name
                    record.save()

                moved += 1

                self.log_success(
                    f"MOVED: {fqdn} -> {target_zone_name}/{new_name}"
                )

            except Exception as exc:
                self.log_failure(
                    f"ERROR moving {fqdn}: {exc}"
                )

        self.log_info("RECONCILIATION SUMMARY")
        self.log_info(f"Records examined: {examined}")
        self.log_info(f"Records matching target Zone: {matched}")
        self.log_info(f"Records moved: {moved}")
        self.log_info(f"Duplicates skipped: {duplicates}")

        if DRY_RUN:
            self.log_warning(
                "DRY RUN completed. No records were modified. "
                "Set DRY_RUN = False to enable moves."
            )

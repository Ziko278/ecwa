# insurance/management/commands/create_claim_summaries.py

from django.core.management.base import BaseCommand
from django.db.models import Q
from insurance.models import InsuranceClaimModel, InsuranceClaimSummary


class Command(BaseCommand):
    help = 'Create claim summaries for existing claims that don\'t have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Get all claims without a summary
        claims_without_summary = InsuranceClaimModel.objects.filter(
            claim_summary__isnull=True
        ).select_related(
            'patient_insurance',
            'created_by',
            'content_type'
        ).prefetch_related('content_object')

        total_claims = claims_without_summary.count()

        if total_claims == 0:
            self.stdout.write(self.style.SUCCESS('No claims need summary creation'))
            return

        self.stdout.write(f'Found {total_claims} claims without summaries')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        # Group claims by their source
        grouped_claims = {}
        orphaned_claims = []

        for claim in claims_without_summary:
            # Determine the source
            consultation = None
            admission = None
            surgery = None

            if claim.content_object:
                if hasattr(claim.content_object, 'consultation') and claim.content_object.consultation:
                    consultation = claim.content_object.consultation
                elif hasattr(claim.content_object, 'admission') and claim.content_object.admission:
                    admission = claim.content_object.admission
                elif hasattr(claim.content_object, 'surgery') and claim.content_object.surgery:
                    surgery = claim.content_object.surgery

            # Create a grouping key
            if consultation:
                key = ('consultation', consultation.id, claim.patient_insurance.id)
            elif admission:
                key = ('admission', admission.id, claim.patient_insurance.id)
            elif surgery:
                key = ('surgery', surgery.id, claim.patient_insurance.id)
            else:
                # Orphaned claim - no source
                orphaned_claims.append(claim)
                continue

            if key not in grouped_claims:
                grouped_claims[key] = {
                    'consultation': consultation,
                    'admission': admission,
                    'surgery': surgery,
                    'patient_insurance': claim.patient_insurance,
                    'created_by': claim.created_by,
                    'claims': []
                }

            grouped_claims[key]['claims'].append(claim)

        # Create summaries
        summaries_created = 0
        claims_linked = 0

        for key, group_data in grouped_claims.items():
            source_type = key[0]

            if not dry_run:
                # Check if summary already exists
                filters = {
                    'patient_insurance': group_data['patient_insurance']
                }

                if source_type == 'consultation':
                    filters['consultation'] = group_data['consultation']
                elif source_type == 'admission':
                    filters['admission'] = group_data['admission']
                elif source_type == 'surgery':
                    filters['surgery'] = group_data['surgery']

                summary, created = InsuranceClaimSummary.objects.get_or_create(
                    **filters,
                    defaults={
                        'created_by': group_data['created_by']
                    }
                )

                if created:
                    summaries_created += 1

                # Link claims to summary
                for claim in group_data['claims']:
                    claim.claim_summary = summary
                    claim.save(update_fields=['claim_summary'])
                    claims_linked += 1

                # Recalculate totals
                summary.recalculate_totals()

                self.stdout.write(
                    f"Created/Updated summary {summary.summary_number} "
                    f"with {len(group_data['claims'])} claims"
                )
            else:
                self.stdout.write(
                    f"Would create summary for {source_type} "
                    f"with {len(group_data['claims'])} claims"
                )

        # Report orphaned claims
        if orphaned_claims:
            self.stdout.write(
                self.style.WARNING(
                    f'\nFound {len(orphaned_claims)} orphaned claims '
                    f'(no consultation/admission/surgery):'
                )
            )
            for claim in orphaned_claims[:10]:  # Show first 10
                self.stdout.write(f"  - {claim.claim_number}")
            if len(orphaned_claims) > 10:
                self.stdout.write(f"  ... and {len(orphaned_claims) - 10} more")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully created {summaries_created} summaries '
                    f'and linked {claims_linked} claims'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would create summaries for {len(grouped_claims)} groups '
                    f'and link {sum(len(g["claims"]) for g in grouped_claims.values())} claims'
                )
            )
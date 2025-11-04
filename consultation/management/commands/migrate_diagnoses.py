# Create this as: consultation/management/commands/migrate_diagnoses.py

from django.core.management.base import BaseCommand
from django.db.models import Q
from consultation.models import ConsultationSessionModel, DiagnosisOption
from difflib import get_close_matches


class Command(BaseCommand):
    help = 'Migrate existing text diagnoses to DiagnosisOption model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.8,
            help='Similarity threshold (0.0 to 1.0) for fuzzy matching',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']

        self.stdout.write(self.style.WARNING(f'\n{"DRY RUN - " if dry_run else ""}Starting diagnosis migration...\n'))

        # Get all consultations with text diagnosis but no primary_diagnosis
        consultations = ConsultationSessionModel.objects.filter(
            primary_diagnosis__isnull=True
        ).exclude(
            Q(diagnosis='') | Q(diagnosis__isnull=True)
        )

        total = consultations.count()
        self.stdout.write(f'Found {total} consultations to process\n')

        # Get all existing diagnosis options
        existing_diagnoses = {d.name.lower(): d for d in DiagnosisOption.objects.all()}

        matched = 0
        created = 0
        skipped = 0

        for consultation in consultations:
            diagnosis_text = consultation.diagnosis.strip()

            if not diagnosis_text:
                skipped += 1
                continue

            # Try exact match (case-insensitive)
            diagnosis_lower = diagnosis_text.lower()

            if diagnosis_lower in existing_diagnoses:
                if not dry_run:
                    consultation.primary_diagnosis = existing_diagnoses[diagnosis_lower]
                    consultation.save()
                matched += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Exact match: "{diagnosis_text}" → {existing_diagnoses[diagnosis_lower].name}')
                )
                continue

            # Try fuzzy matching
            close_matches = get_close_matches(
                diagnosis_lower,
                existing_diagnoses.keys(),
                n=1,
                cutoff=threshold
            )

            if close_matches:
                matched_diagnosis = existing_diagnoses[close_matches[0]]
                if not dry_run:
                    consultation.primary_diagnosis = matched_diagnosis
                    consultation.save()
                matched += 1
                self.stdout.write(
                    self.style.WARNING(f'≈ Fuzzy match: "{diagnosis_text}" → {matched_diagnosis.name}')
                )
                continue

            # Create new diagnosis if no match found
            if not dry_run:
                # Normalize the name (title case)
                normalized_name = diagnosis_text.title()

                # Check if this normalized name already exists
                diagnosis_obj, was_created = DiagnosisOption.objects.get_or_create(
                    name=normalized_name,
                    defaults={'is_active': True}
                )

                consultation.primary_diagnosis = diagnosis_obj
                consultation.save()

                if was_created:
                    created += 1
                    existing_diagnoses[normalized_name.lower()] = diagnosis_obj
                    self.stdout.write(
                        self.style.NOTICE(f'+ Created new: "{normalized_name}"')
                    )
                else:
                    matched += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Found existing: "{normalized_name}"')
                    )
            else:
                created += 1
                self.stdout.write(
                    self.style.NOTICE(f'+ Would create: "{diagnosis_text.title()}"')
                )

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'\nMigration {"Preview" if dry_run else "Complete"}!'))
        self.stdout.write(f'\nTotal consultations: {total}')
        self.stdout.write(self.style.SUCCESS(f'Matched to existing: {matched}'))
        self.stdout.write(self.style.NOTICE(f'New diagnoses {"would be " if dry_run else ""}created: {created}'))
        self.stdout.write(self.style.WARNING(f'Skipped (empty): {skipped}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠ This was a DRY RUN. Run without --dry-run to apply changes.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Data successfully migrated!'))
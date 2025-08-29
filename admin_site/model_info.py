TEMPORAL_STATUS = (
    ('pending', 'PENDING'), ('completed', 'COMPLETED')
)

CONFIRMATION_STATUS = (
    ('pending', 'PENDING'), ('confirmed', 'CONFIRMED')
)

LOAN_REFUND_TYPE = (
    ('salary', 'NEXT SALARY'), ('date', 'SPECIFIC DATE')
)

GENDER = (
    ('male', 'MALE'), ('female', 'FEMALE')
)


RELIGION = (
    ('christianity', 'CHRISTIANITY'), ('islam', 'ISLAM'), ('others', 'OTHERS')
)

BLOOD_GROUP = (
        ('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'), ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'),
        ('o-', 'O-'),
)

GENOTYPE = (
        ('aa', 'AA'), ('as', 'AS'), ('ac', 'AC'), ('ss', 'SS')
)

MARITAL_STATUS = (
        ('single', 'SINGLE'), ('married', 'MARRIED'), ('widowed', 'WIDOWED'), ('divorced', 'DIVORCED')
)

INSURANCE_PROVIDER = (
        ('nhis', 'NHIS'),
)

CERTIFICATE_TYPE = (
        ('school leaving', 'SCHOOL LEAVING'),
        ('ond', 'OND'), ('hnd', 'HND'),
        ('masters', 'MASTERS'), ('phd', 'PHD'),
        ('professional', 'PROFESSIONAL')
)

WARD_TYPE = (
    ('general', 'GENERAL'), ('special', 'SPECIAL'), ('icu', 'INTENSIVE CARE UNIT'), ('isolation', 'ISOLATION')
)

CONSULTATION_PAYMENT_DURATION = (
    ('daily', 'DAILY'), ('weekly', 'WEEKLY'), ('monthly', 'MONTHLY'), ('annually', 'ANNUALLY')
)


PAYMENT_STATUS = (
    ('not paid', 'NOT PAID'), ('paid', 'PAID')
    # always maintain the "not paid" status as the first item in the tuple
)

COLLECTION_STATUS = (
    ('not collected', 'NOT COLLECTED'), ('collected', 'COLLECTED')
    # always maintain the "not collected" status as the first item in the tuple
)

CONDUCTED_STATUS = (
    ('internal', 'INTERNAL'), ('external', 'EXTERNAL')
)

CONSULTATION_QUEUE_STATUS = (
    ('awaiting', 'AWAITING'), ('progress', 'PROGRESS'), ('paused', 'PAUSED'), ('complete', 'COMPLETE')
)

CONSULTATION_STATUS = (
    ('not posted', 'NOT POSTED'), ('posted', 'posted'), ('progress', 'PROGRESS'), ('complete', 'COMPLETE')
)

CONSULTATION_STAGE = (
    ('new', 'NEW'), ('follow up', 'FOLLOW UP'), ('conclusion', 'CONCLUSION'), ('admission', 'ADMISSION')
)


BANKS = (
    ('access bank', 'ACCESS BANK'), ('first bank', 'FIRST BANK'), ('uba', 'UNITED BANKS FOR AFRICA')
)

RECEIPT_FORMAT = (
    ('portrait', 'PORTRAIT'), ('landscape', 'LANDSCAPE')
)

ACTIVE_STATUS = (
    ('active', 'ACTIVE'), ('inactive', 'INACTIVE')
)

STAFF_SHIFT_TYPE = (
    ('fixed', 'FIXED'), ('variable', 'VARIABLE')
)

STAFF_ACTIVE_TYPE = (
    ('active', 'ACTIVE'), ('suspended', 'SUSPENDED'), ('retired', 'RETIRED')
)

LEAVE_TYPES = [
        ('Annual', 'Annual'),
        ('Casual', 'Casual'),
        ('Sick', 'Sick'),
        ('Maternity', 'Maternity'),
        ('Paternity', 'Paternity'),
        ('Compassionate', 'Compassionate'),
        ('Unpaid', 'Unpaid'),
        ('others', 'OTHERS')
    ]

DURATION_TYPE = (
    ('day', 'DAY'), ('week', 'WEEK'), ('month', 'MONTH'), ('year', 'YEAR')
)

LEAVE_STATUS = (
    ('pending', 'PENDING'), ('approved', 'APPROVED'), ('declined', 'DECLINED')
)

ASSET_TYPE = (
        ('fixed', 'FIXED'), ('movable', 'MOVABLE')
)

DRUG_FORM = (
    ('capsule', 'CAPSULE'), ('injection', 'INJECTION'), ('syrup', 'SYRUP'), ('balm', 'BALM')
)

MORTALITY_STATUS = (
    ('alive', 'ALIVE'), ('dead', 'DEAD')
)

CONTRACT_TYPE = (
    ('full time', 'FULL TIME'),
    ('part time', 'PART TIME'),
    ('internship', 'INTERNSHIP'),
    ('it', 'IT'),
    ('nysc', 'NYSC'),
    ('probation', 'PROBATION'),
)
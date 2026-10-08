from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

# Six decimal places leave room for 0/2/3 and higher minor-unit scales.
# Currency-specific rounding belongs to the future posting boundary.
MONEY_DIGITS = 24
MONEY_PLACES = 6
MONEY_LIMIT = Decimal('1000000000000000000')


def positive_money(field):
    # The upper bound also rejects PostgreSQL numeric NaN, which sorts above
    # finite numbers and would otherwise pass a simple > 0 CHECK.
    return Q(**{f'{field}__isnull': False, f'{field}__gt': 0, f'{field}__lt': MONEY_LIMIT})


class FinanceModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean_fields(self, exclude=None):
        excluded = set(exclude or [])
        errors = {}
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if field.name in excluded:
                continue
            if isinstance(field, models.DecimalField) and isinstance(value, float):
                errors[field.name] = 'Use Decimal or an exact decimal string, never float.'
            if isinstance(field, models.DateTimeField) and value is not None and hasattr(value, 'tzinfo'):
                if timezone.is_naive(value):
                    errors[field.name] = 'Use a timezone-aware timestamp.'
        if errors:
            raise ValidationError(errors)
        super().clean_fields(exclude=exclude)
        # Also check datetime strings after Django has parsed them.
        for field in self._meta.fields:
            if isinstance(field, models.DateTimeField) and field.name not in excluded:
                value = getattr(self, field.attname)
                if value is not None and timezone.is_naive(value):
                    raise ValidationError({field.name: 'Use a timezone-aware timestamp.'})

    def save(self, *args, **kwargs):
        # Structural validation only: no provisioning, posting or balancing.
        self.full_clean()
        return super().save(*args, **kwargs)

    def related(self, field, model):
        identifier = getattr(self, f'{field}_id')
        if identifier is None:
            return None
        # Query persisted values rather than trusting a potentially stale FK cache.
        obj = model.objects.filter(pk=identifier).first()
        if obj is None:
            raise ValidationError({field: 'Select an existing object.'})
        if obj.user_id != self.user_id:
            raise ValidationError({field: 'Related objects must belong to the same user.'})
        return obj


class OwnedModel(FinanceModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name='%(app_label)s_%(class)s_records')

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.pk:
            old_owner = type(self).objects.filter(pk=self.pk).values_list('user_id', flat=True).first()
            if old_owner is not None and old_owner != self.user_id:
                raise ValidationError({'user': 'Finance ownership cannot be reassigned.'})


class LedgerAccount(OwnedModel):
    class Kind(models.TextChoices):
        ASSET = 'asset', 'Asset'
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'
        EQUITY = 'equity', 'Equity'

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(kind__in=['asset', 'income', 'expense', 'equity']),
                                              name='finance_ledger_kind_valid')]

    def clean(self):
        super().clean()
        if self.pk:
            if FinancialAccount.objects.filter(ledger_account_id=self.pk).exists() and self.kind != self.Kind.ASSET:
                raise ValidationError({'kind': 'Financial accounts require an asset ledger account.'})
            if Category.objects.filter(ledger_account_id=self.pk).exclude(kind=self.kind).exists():
                raise ValidationError({'kind': 'Ledger class must match its linked category.'})

    def __str__(self):
        return self.name


class FinancialAccount(OwnedModel):
    class Kind(models.TextChoices):
        BANK = 'bank', 'Bank'
        WALLET = 'wallet', 'Wallet'
        CASH = 'cash', 'Cash'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    institution_name = models.CharField(max_length=120, blank=True)
    subtype = models.CharField(max_length=80, blank=True)
    last_four = models.CharField(max_length=4, blank=True,
                                validators=[RegexValidator(r'\A[0-9]{4}\Z', 'Enter exactly four digits.')])
    is_active = models.BooleanField(default=True, help_text='False means archived; historical references remain valid.')
    include_in_total = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    ledger_account = models.OneToOneField(LedgerAccount, null=True, blank=True, on_delete=models.PROTECT,
                                         related_name='financial_account')

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=['bank', 'wallet', 'cash', 'other']),
                                   name='finance_account_kind_valid'),
            models.CheckConstraint(condition=Q(last_four='') | Q(last_four__regex=r'\A[0-9]{4}\Z'),
                                   name='finance_account_last_four_valid'),
        ]

    def clean(self):
        super().clean()
        ledger = self.related('ledger_account', LedgerAccount)
        if ledger and ledger.kind != LedgerAccount.Kind.ASSET:
            raise ValidationError({'ledger_account': 'Select an asset ledger account.'})

    def __str__(self):
        return self.name


class Category(OwnedModel):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    is_active = models.BooleanField(default=True, help_text='False means archived; historical references remain valid.')
    ledger_account = models.OneToOneField(LedgerAccount, null=True, blank=True, on_delete=models.PROTECT,
                                         related_name='category')

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=['income', 'expense']), name='finance_category_kind_valid'),
            models.CheckConstraint(condition=Q(parent__isnull=True) | ~Q(parent=F('pk')),
                                   name='finance_category_not_self_parent'),
        ]

    def clean(self):
        super().clean()
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({'parent': 'A category cannot be its own parent.'})
        parent = self.related('parent', Category)
        if parent:
            if parent.kind != self.kind:
                raise ValidationError({'parent': 'Parent and child must have the same category type.'})
            if parent.parent_id is not None:
                raise ValidationError({'parent': 'Only a root category may have children.'})
            if self.pk and Category.objects.filter(parent_id=self.pk).exists():
                raise ValidationError({'parent': 'A category with children must remain a root.'})
        if self.pk:
            if Category.objects.filter(parent_id=self.pk).exclude(kind=self.kind).exists():
                raise ValidationError({'kind': 'Category type must remain compatible with its children.'})
            if Transaction.objects.filter(category_id=self.pk).exclude(kind=self.kind).exists():
                raise ValidationError({'kind': 'Category type must remain compatible with referencing transactions.'})
        ledger = self.related('ledger_account', LedgerAccount)
        if ledger and ledger.kind != self.kind:
            raise ValidationError({'ledger_account': 'Ledger class must match the category type.'})

    def __str__(self):
        return self.name


class Transaction(OwnedModel):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'
        TRANSFER = 'transfer', 'Transfer'
        # Special accounting events; not ordinary Add Transaction choices.
        OPENING_BALANCE = 'opening_balance', 'Opening balance'
        ADJUSTMENT = 'adjustment', 'Balance adjustment'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'

    kind = models.CharField(max_length=15, choices=Kind.choices)
    amount = models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    occurred_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    # account is the primary account for income/expense, source for transfer.
    # Drafts may omit links; completeness is enforced by the future posting service.
    account = models.ForeignKey(FinancialAccount, null=True, blank=True, on_delete=models.PROTECT,
                                related_name='transactions')
    destination_account = models.ForeignKey(FinancialAccount, null=True, blank=True, on_delete=models.PROTECT,
                                            related_name='incoming_transfers')
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT,
                                related_name='transactions')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='finance_transaction_user_idempotency'),
            models.CheckConstraint(condition=Q(kind__in=['income', 'expense', 'transfer', 'opening_balance', 'adjustment']),
                                   name='finance_transaction_kind_valid'),
            models.CheckConstraint(condition=positive_money('amount'), name='finance_transaction_amount_positive'),
            models.CheckConstraint(condition=Q(status='draft'), name='finance_transaction_draft_only'),
            models.CheckConstraint(condition=Q(kind__in=['income', 'expense']) | Q(category__isnull=True),
                                   name='finance_category_classified_only'),
            models.CheckConstraint(condition=Q(kind='transfer') | Q(destination_account__isnull=True),
                                   name='finance_destination_transfer_only'),
            models.CheckConstraint(condition=Q(account__isnull=True) | Q(destination_account__isnull=True)
                                   | ~Q(account=F('destination_account')), name='finance_transfer_distinct_accounts'),
        ]

    def clean(self):
        super().clean()
        self.related('account', FinancialAccount)
        self.related('destination_account', FinancialAccount)
        category = self.related('category', Category)
        if category and category.kind != self.kind:
            raise ValidationError({'category': 'Category type must match the transaction type.'})

    def __str__(self):
        return f'{self.kind} {self.amount}'


class JournalEntry(OwnedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'

    transaction = models.OneToOneField(Transaction, null=True, blank=True, on_delete=models.PROTECT,
                                       related_name='journal_entry')
    # Accounting-effective time, distinct from creation time. Opening balances
    # and adjustments will link visible Transactions through the posting service.
    entry_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(status='draft'), name='finance_journal_draft_only')]

    def clean(self):
        super().clean()
        self.related('transaction', Transaction)

    def __str__(self):
        return f'Journal {self.pk}'


class JournalLine(FinanceModel):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name='lines')
    ledger_account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name='lines')
    debit = models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES, null=True, blank=True)
    credit = models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES, null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(positive_money('debit') & Q(credit__isnull=True))
            | (positive_money('credit') & Q(debit__isnull=True)), name='finance_line_positive_debit_xor_credit')]

    def clean(self):
        super().clean()
        entry = JournalEntry.objects.filter(pk=self.journal_entry_id).first()
        ledger = LedgerAccount.objects.filter(pk=self.ledger_account_id).first()
        if entry and ledger and entry.user_id != ledger.user_id:
            raise ValidationError({'ledger_account': 'Ledger account must belong to the journal owner.'})

    def __str__(self):
        return f'Line {self.pk} in journal {self.journal_entry_id}'

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction as db_transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, FinancialAccount, JournalEntry, JournalLine, LedgerAccount, Transaction

User = get_user_model()
D = Decimal


class FinanceModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('finance-owner@example.com', base_currency='USD')
        cls.other = User.objects.create_user('finance-other@example.com', base_currency='EUR')

    def ledger(self, **fields):
        return LedgerAccount.objects.create(**({'user': self.owner, 'name': 'Ledger', 'kind': 'asset'} | fields))

    def account(self, **fields):
        return FinancialAccount.objects.create(**({'user': self.owner, 'name': 'Bank', 'kind': 'bank'} | fields))

    def category(self, **fields):
        return Category.objects.create(**({'user': self.owner, 'name': 'Salary', 'kind': 'income'} | fields))

    def event(self, **fields):
        return Transaction.objects.create(**({'user': self.owner, 'kind': 'income', 'amount': D('12.345678')} | fields))

    def entry(self, **fields):
        return JournalEntry.objects.create(**({'user': self.owner} | fields))

    def line(self, **fields):
        values = {'journal_entry': self.entry(), 'ledger_account': self.ledger(), 'debit': D('1')}
        return JournalLine(**(values | fields))

    def db_rejects(self, obj):
        # Raw SQL bypasses both model clean and DecimalField coercion, proving
        # PostgreSQL itself rejects invalid values (including numeric NaN).
        quote = connection.ops.quote_name
        fields = [field for field in obj._meta.fields if not field.primary_key]
        columns = [quote(field.column) for field in fields]
        values = [timezone.now() if getattr(field, 'auto_now', False)
                  or getattr(field, 'auto_now_add', False) else getattr(obj, field.attname)
                  for field in fields]
        table = quote(obj._meta.db_table)
        if obj.pk:
            assignments = ', '.join(f'{column} = %s' for column in columns)
            sql = f'UPDATE {table} SET {assignments} WHERE {quote(obj._meta.pk.column)} = %s'
            values.append(obj.pk)
        else:
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        with self.assertRaises(IntegrityError), db_transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, values)

    def test_accounts_owner_kinds_and_archive_fields(self):
        for kind in FinancialAccount.Kind.values:
            account = self.account(kind=kind, last_four='1234', institution_name='Test bank', subtype='Savings')
            self.assertEqual(account.user, self.owner)
            self.assertTrue(account.include_in_total)
            self.assertEqual(account.display_order, 0)
            account.is_active = False
            account.save()
            account.refresh_from_db()
            self.assertFalse(account.is_active)
            self.assertTrue(timezone.is_aware(account.created_at))
            self.assertGreaterEqual(account.updated_at, account.created_at)

    def test_account_has_no_balance_or_full_number_field(self):
        names = {field.name for field in FinancialAccount._meta.fields}
        self.assertNotIn('balance', names)
        self.assertNotIn('opening_balance', names)
        self.assertNotIn('account_number', names)
        self.assertNotIn('account_identifier', names)
        self.assertEqual(FinancialAccount._meta.get_field('last_four').max_length, 4)

    def test_last_four_is_optional_or_exactly_four_ascii_digits(self):
        self.account(last_four='')
        for value in ('1', '12345', 'abcd', '1234\n', '１２３４'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.account(last_four=value)
        self.db_rejects(FinancialAccount(user=self.owner, name='Invalid', kind='bank', last_four='12ab'))

    def test_invalid_account_kind_model_and_database(self):
        with self.assertRaises(ValidationError):
            self.account(kind='loan')
        self.db_rejects(FinancialAccount(user=self.owner, name='Invalid', kind='loan'))

    def test_account_ledger_link_same_owner_and_asset_only(self):
        self.account(ledger_account=self.ledger())
        for ledger in (self.ledger(user=self.other), self.ledger(kind='income')):
            with self.subTest(kind=ledger.kind), self.assertRaises(ValidationError):
                self.account(ledger_account=ledger)

    def test_optional_links_do_not_automatically_provision(self):
        account = self.account()
        category = self.category()
        event = self.event()
        self.assertIsNone(account.ledger_account_id)
        self.assertIsNone(category.ledger_account_id)
        self.assertEqual(LedgerAccount.objects.count(), 0)
        self.assertFalse(JournalEntry.objects.filter(transaction=event).exists())
        self.assertFalse(JournalLine.objects.exists())

    def test_category_types_and_rename_stable_identity(self):
        for kind in Category.Kind.values:
            category = self.category(kind=kind)
            identifier = category.pk
            category.name = 'Renamed'
            category.save()
            category.refresh_from_db()
            self.assertEqual(category.pk, identifier)
            self.assertEqual(category.user, self.owner)
        with self.assertRaises(ValidationError):
            self.category(kind='transfer')
        self.db_rejects(Category(user=self.owner, name='Invalid', kind='transfer'))

    def test_category_root_child_and_archive(self):
        parent = self.category()
        child = self.category(parent=parent)
        self.assertEqual(child.parent, parent)
        child.is_active = False
        child.save()
        self.assertEqual(parent.children.get(), child)

    def test_category_parent_owner_and_type(self):
        for parent in (self.category(user=self.other), self.category(kind='expense')):
            with self.subTest(parent=parent.pk), self.assertRaises(ValidationError):
                self.category(parent=parent)

    def test_category_self_parent_model_and_database(self):
        category = self.category()
        category.parent = category
        with self.assertRaises(ValidationError):
            category.save()
        self.db_rejects(category)

    def test_category_cannot_have_third_level_or_cycle(self):
        root = self.category()
        child = self.category(parent=root)
        with self.assertRaises(ValidationError):
            self.category(parent=child)
        root.parent = child
        with self.assertRaises(ValidationError):
            root.save()

    def test_category_with_children_cannot_be_reparented(self):
        root = self.category()
        self.category(parent=root)
        root.parent = self.category()
        with self.assertRaises(ValidationError):
            root.save()

    def test_category_type_change_preserves_reverse_relationships(self):
        parent = self.category()
        self.category(parent=parent)
        parent.kind = 'expense'
        with self.assertRaises(ValidationError):
            parent.save()
        category = self.category()
        self.event(category=category)
        category.kind = 'expense'
        with self.assertRaises(ValidationError):
            category.save()

    def test_category_ledger_matching_type_and_owner(self):
        for kind in Category.Kind.values:
            self.category(kind=kind, ledger_account=self.ledger(kind=kind))
        for ledger in (self.ledger(kind='expense'), self.ledger(kind='income', user=self.other), self.ledger()):
            with self.assertRaises(ValidationError):
                self.category(ledger_account=ledger)

    def test_ledger_classes_and_owner(self):
        for kind in LedgerAccount.Kind.values:
            self.assertEqual(self.ledger(kind=kind).user, self.owner)
        with self.assertRaises(ValidationError):
            self.ledger(kind='liability')
        self.db_rejects(LedgerAccount(user=self.owner, name='Invalid', kind='liability'))

    def test_ledger_class_changes_cannot_invalidate_backings(self):
        ledger = self.ledger()
        self.account(ledger_account=ledger)
        ledger.kind = 'equity'
        with self.assertRaises(ValidationError):
            ledger.save()
        ledger = self.ledger(kind='income')
        self.category(ledger_account=ledger)
        ledger.kind = 'expense'
        with self.assertRaises(ValidationError):
            ledger.save()

    def test_one_to_one_companions_and_transaction_journal(self):
        ledger = self.ledger()
        self.account(ledger_account=ledger)
        with self.assertRaises(ValidationError):
            self.account(ledger_account=ledger)
        ledger = self.ledger(kind='income')
        self.category(ledger_account=ledger)
        with self.assertRaises(ValidationError):
            self.category(ledger_account=ledger)
        event = self.event()
        self.entry(transaction=event)
        with self.assertRaises(ValidationError):
            self.entry(transaction=event)
        self.db_rejects(JournalEntry(user=self.owner, transaction=event))

    def test_transaction_types_decimal_and_aware_dates(self):
        for kind in Transaction.Kind.values:
            event = self.event(kind=kind)
            event.refresh_from_db()
            self.assertEqual(event.user, self.owner)
            self.assertEqual(event.amount, D('12.345678'))
            self.assertIsInstance(event.amount, Decimal)
            self.assertTrue(timezone.is_aware(event.occurred_at))
            self.assertTrue(timezone.is_aware(event.created_at))
            self.assertTrue(timezone.is_aware(event.updated_at))
            self.assertEqual(event.status, 'draft')
        backdated = timezone.now() - timedelta(days=7)
        self.assertEqual(self.event(occurred_at=backdated).occurred_at, backdated)

    def test_transaction_nonpositive_model_and_database(self):
        for value in (D('0'), D('-1')):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.event(amount=value)
            self.db_rejects(Transaction(user=self.owner, kind='income', amount=value))

    def test_money_precision_range_and_nonfinite(self):
        largest = D('999999999999999999.999999')
        event = self.event(amount=largest)
        event.refresh_from_db()
        self.assertEqual(event.amount, largest)
        for value in (D('0.0000001'), D('1000000000000000000'), D('NaN'), D('Infinity')):
            with self.subTest(value=str(value)), self.assertRaises(ValidationError):
                self.event(amount=value)
        self.db_rejects(Transaction(user=self.owner, kind='income', amount=D('NaN')))

    def test_float_inputs_and_naive_dates_rejected(self):
        with self.assertRaises(ValidationError):
            self.event(amount=0.1)
        with self.assertRaises(ValidationError):
            self.line(debit=0.1).save()
        with self.assertRaises(ValidationError):
            self.event(occurred_at=datetime(2026, 1, 1))
        with self.assertRaises(ValidationError):
            self.entry(entry_at=datetime(2026, 1, 1))
        with self.assertRaises(ValidationError):
            self.event(occurred_at='2026-01-01T12:00:00')
        event = self.event(amount='0.123456')
        self.assertIsInstance(event.amount, Decimal)

    def test_transaction_kind_model_and_database(self):
        with self.assertRaises(ValidationError):
            self.event(kind='opening')
        self.db_rejects(Transaction(user=self.owner, kind='opening', amount=D('1')))

    def test_transaction_relationship_owners(self):
        for field, related in (('account', self.account(user=self.other)),
                               ('destination_account', self.account(user=self.other)),
                               ('category', self.category(user=self.other))):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.event(kind='transfer' if field == 'destination_account' else 'income', **{field: related})

    def test_transaction_category_type_consistency(self):
        with self.assertRaises(ValidationError):
            self.event(category=self.category(kind='expense'))
        self.event(kind='expense', category=self.category(kind='expense'), account=self.account())

    def test_transfer_shape_constraints_model_and_database(self):
        account = self.account()
        destination = self.account()
        category = self.category()
        self.event(kind='transfer', account=account, destination_account=destination)
        invalid = [dict(kind='transfer', category=category),
                   dict(kind='income', destination_account=destination),
                   dict(kind='transfer', account=account, destination_account=account)]
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.event(**fields)
            self.db_rejects(Transaction(user=self.owner, amount=D('1'), **fields))

    def test_draft_only_no_claim_of_balancing(self):
        event = self.event()
        entry = self.entry(transaction=event)
        self.line(journal_entry=entry, debit=D('5')).save()
        # A one-line draft can exist; no save-time cross-row balancing is claimed.
        self.assertEqual(entry.lines.count(), 1)
        for obj in (event, entry):
            obj.status = 'posted'
            with self.assertRaises(ValidationError):
                obj.save()
            self.db_rejects(obj)

    def test_entry_transaction_owner_and_standalone_structure(self):
        entry = self.entry(transaction=self.event())
        self.assertEqual(entry.user, entry.transaction.user)
        self.assertTrue(timezone.is_aware(entry.entry_at))
        standalone = self.entry()
        self.assertIsNone(standalone.transaction_id)
        with self.assertRaises(ValidationError):
            self.entry(transaction=self.event(user=self.other))

    def test_journal_debit_only_credit_only_and_ownership(self):
        entry = self.entry(transaction=self.event())
        ledger = self.ledger()
        for debit, credit in ((D('12.345678'), None), (None, D('12.345678'))):
            line = JournalLine.objects.create(journal_entry=entry, ledger_account=ledger, debit=debit, credit=credit)
            line.refresh_from_db()
            self.assertEqual(line.journal_entry, entry)
            self.assertEqual(line.ledger_account, ledger)
            self.assertIsInstance(line.debit or line.credit, Decimal)

    def test_journal_line_impossible_states_model_and_database(self):
        entry = self.entry()
        ledger = self.ledger()
        for debit, credit in ((None, None), (D('1'), D('1')), (D('0'), None),
                              (None, D('0')), (D('-1'), None), (None, D('-1')),
                              (D('NaN'), None), (None, D('NaN'))):
            with self.subTest(debit=debit, credit=credit):
                obj = JournalLine(journal_entry=entry, ledger_account=ledger, debit=debit, credit=credit)
                with self.assertRaises(ValidationError):
                    obj.save()
                self.db_rejects(JournalLine(journal_entry=entry, ledger_account=ledger, debit=debit, credit=credit))

    def test_cross_owner_line_and_relink_rejected(self):
        with self.assertRaises(ValidationError):
            self.line(ledger_account=self.ledger(user=self.other)).save()
        line = self.line()
        line.save()
        line.journal_entry = self.entry(user=self.other)
        with self.assertRaises(ValidationError):
            line.save()

    def test_owner_reassignment_cannot_invalidate_existing_links(self):
        ledger = self.ledger()
        account = self.account(ledger_account=ledger)
        category = self.category()
        event = self.event(account=account, category=category)
        entry = self.entry(transaction=event)
        self.line(journal_entry=entry, ledger_account=ledger).save()
        for obj in (ledger, account, category, event, entry):
            original_owner = obj.user
            obj.user = self.other
            with self.subTest(model=type(obj).__name__), self.assertRaises(ValidationError):
                obj.save()
            obj.user = original_owner

    def test_validation_uses_current_persisted_related_values(self):
        ledger = self.ledger()
        # Keep a stale Python instance while valid, unrelated ledger kind changes.
        stale = LedgerAccount.objects.get(pk=ledger.pk)
        ledger.kind = 'equity'
        ledger.save()
        with self.assertRaises(ValidationError):
            self.account(ledger_account=stale)

    def test_archived_account_and_category_stay_referenceable(self):
        account = self.account(is_active=False)
        category = self.category(is_active=False)
        event = self.event(account=account, category=category)
        account.name = 'Renamed archived bank'
        category.name = 'Renamed archived income'
        account.save()
        category.save()
        event.refresh_from_db()
        self.assertEqual(event.account_id, account.pk)
        self.assertEqual(event.category_id, category.pk)

    def test_history_relations_protect_deletion(self):
        ledger = self.ledger()
        account = self.account(ledger_account=ledger)
        category = self.category()
        event = self.event(account=account, category=category)
        entry = self.entry(transaction=event)
        line = self.line(journal_entry=entry, ledger_account=ledger)
        line.save()
        for obj in (self.owner, account, category, ledger, event, entry):
            with self.subTest(model=type(obj).__name__), self.assertRaises(ProtectedError):
                obj.delete()
        with self.assertRaises(ProtectedError):
            FinancialAccount.objects.filter(pk=account.pk).delete()

    def test_parent_and_linked_ledger_are_protected_but_unused_entities_can_delete(self):
        parent = self.category()
        self.category(parent=parent)
        with self.assertRaises(ProtectedError):
            parent.delete()
        ledger = self.ledger(kind='expense')
        self.category(kind='expense', ledger_account=ledger)
        with self.assertRaises(ProtectedError):
            ledger.delete()
        account = self.account()
        account.delete()
        unused = self.category()
        unused.delete()

    def test_finance_admin_inspection_and_event_readonly_permissions(self):
        administrator = User.objects.create_superuser('finance-admin@example.com', base_currency='USD')
        self.client.force_login(administrator)
        instances = [self.account(), self.category(), self.ledger(), self.event(), self.entry(), self.line()]
        instances[-1].save()
        for obj in instances:
            model = type(obj)
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
                name = model._meta.model_name
                self.assertEqual(self.client.get(reverse(f'admin:finance_{name}_changelist')).status_code, 200)
                response = self.client.get(reverse(f'admin:finance_{name}_change', args=[obj.pk]))
                self.assertEqual(response.status_code, 200)
                if model in (Transaction, JournalEntry, JournalLine):
                    self.assertFalse(response.context['has_change_permission'])
                    self.assertFalse(response.context['has_delete_permission'])
                    self.assertFalse(response.context['has_add_permission'])

    def test_postgresql_and_decimal_schema(self):
        self.assertEqual(connection.vendor, 'postgresql')
        for model, fields in ((Transaction, ('amount',)), (JournalLine, ('debit', 'credit'))):
            for name in fields:
                field = model._meta.get_field(name)
                self.assertIsInstance(field, models.DecimalField)
                self.assertEqual((field.max_digits, field.decimal_places), (24, 6))

    def test_optional_idempotency_key_unique_per_owner(self):
        key = uuid4()
        self.event(idempotency_key=key)
        self.event(user=self.other, idempotency_key=key)
        self.event()
        self.event()
        with self.assertRaises(ValidationError):
            self.event(idempotency_key=key)
        self.db_rejects(Transaction(user=self.owner, kind='income', amount=D('1'), idempotency_key=key))

    def test_special_events_have_visible_transaction_and_explicit_journal_link(self):
        account = self.account()
        for kind in (Transaction.Kind.OPENING_BALANCE, Transaction.Kind.ADJUSTMENT):
            with self.subTest(kind=kind):
                event = self.event(kind=kind, account=account)
                event.refresh_from_db()
                self.assertEqual(event.kind, kind)
                self.assertEqual(event.amount, D('12.345678'))
                self.assertEqual(event.status, 'draft')
                self.assertIsNone(event.category_id)
                self.assertIsNone(event.destination_account_id)
                self.assertFalse(JournalEntry.objects.filter(transaction=event).exists())
                entry = self.entry(transaction=event)
                self.assertEqual(entry.transaction.journal_entry, entry)
                self.assertEqual(entry.user_id, event.user_id)
                self.assertEqual(entry.lines.count(), 0)
        self.assertFalse(LedgerAccount.objects.exists())

    def test_special_events_prohibit_category_at_model_and_database_layers(self):
        category = self.category()
        for kind in (Transaction.Kind.OPENING_BALANCE, Transaction.Kind.ADJUSTMENT):
            with self.subTest(kind=kind):
                with self.assertRaises(ValidationError):
                    self.event(kind=kind, category=category)
                self.db_rejects(Transaction(user=self.owner, kind=kind, amount=D('1'), category=category))

    def test_special_events_have_no_transfer_destination_semantics(self):
        account = self.account()
        destination = self.account()
        for kind in (Transaction.Kind.OPENING_BALANCE, Transaction.Kind.ADJUSTMENT):
            with self.subTest(kind=kind):
                # Drafts can be created with one account or incomplete links.
                self.event(kind=kind, account=account)
                self.event(kind=kind)
                with self.assertRaises(ValidationError):
                    self.event(kind=kind, account=account, destination_account=destination)
                self.db_rejects(Transaction(user=self.owner, kind=kind, amount=D('1'),
                                            account=account, destination_account=destination))
                for amount in (D('0'), D('-1')):
                    with self.assertRaises(ValidationError):
                        self.event(kind=kind, amount=amount)

    def test_special_event_ownership_and_journal_admin_remain_protected(self):
        foreign_account = self.account(user=self.other)
        administrator = User.objects.create_superuser('special-admin@example.com', base_currency='USD')
        self.client.force_login(administrator)
        for kind in (Transaction.Kind.OPENING_BALANCE, Transaction.Kind.ADJUSTMENT):
            with self.subTest(kind=kind):
                with self.assertRaises(ValidationError):
                    self.event(kind=kind, account=foreign_account)
                event = self.event(kind=kind)
                with self.assertRaises(ValidationError):
                    self.entry(user=self.other, transaction=event)
                entry = self.entry(transaction=event)
                with self.assertRaises(ValidationError):
                    self.line(journal_entry=entry, ledger_account=self.ledger(user=self.other)).save()
                for obj in (event, entry):
                    response = self.client.get(reverse(f'admin:finance_{obj._meta.model_name}_change', args=[obj.pk]))
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.context['has_change_permission'])
                    self.assertFalse(response.context['has_delete_permission'])

    def test_category_kind_groups_roots_without_synthetic_kind_rows(self):
        self.assertEqual(set(Category.Kind.values), {'income', 'expense'})
        root = self.category(name='Employment', kind='income')
        child = self.category(name='Salary', kind='income', parent=root)
        self.assertIsNone(root.parent_id)
        self.assertEqual(child.parent_id, root.pk)
        self.assertEqual(Category.objects.count(), 2)
        self.assertFalse(Category.objects.filter(name__in=['Income', 'Expense', 'Transfer']).exists())

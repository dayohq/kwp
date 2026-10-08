from django.contrib import admin

from .models import Category, FinancialAccount, JournalEntry, JournalLine, LedgerAccount, Transaction


class OwnedAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('user',)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, 'user') if obj else fields


@admin.register(FinancialAccount)
class FinancialAccountAdmin(OwnedAdmin):
    list_display = ('id', 'name', 'user', 'kind', 'is_active', 'include_in_total')
    list_filter = ('kind', 'is_active')


@admin.register(Category)
class CategoryAdmin(OwnedAdmin):
    list_display = ('id', 'name', 'user', 'kind', 'parent', 'is_active')
    list_filter = ('kind', 'is_active')


@admin.register(LedgerAccount)
class LedgerAccountAdmin(OwnedAdmin):
    list_display = ('id', 'name', 'user', 'kind')


class InspectionOnlyAdmin(admin.ModelAdmin):
    """Journal/event editing belongs to an atomic, validated posting service."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(InspectionOnlyAdmin):
    list_display = ('id', 'user', 'kind', 'amount', 'occurred_at', 'status')


@admin.register(JournalEntry)
class JournalEntryAdmin(InspectionOnlyAdmin):
    list_display = ('id', 'user', 'transaction', 'entry_at', 'status')


@admin.register(JournalLine)
class JournalLineAdmin(InspectionOnlyAdmin):
    list_display = ('id', 'journal_entry', 'ledger_account', 'debit', 'credit')

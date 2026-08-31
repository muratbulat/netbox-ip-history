from .vendor_file import VendorFileImporter


class RegisteredVendorImporter(VendorFileImporter):
    #: These adapters only declare capabilities/display metadata and delegate
    #: entirely to generic CSV/JSON sniffing — no vendor-specific field
    #: mapping or event parsing exists yet. See CLAUDE.md importer status.
    implemented = False

    def inspect(self):
        result = super().inspect()
        result.product = self.display_name
        return result
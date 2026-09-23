import pytest

from v2.probes.safety import GuardError, check_company, check_mutation_allowed, check_request

A = "Bharat Traders Probe Copy"


@pytest.mark.parametrize("xml", [
    "<COLLECTION><NATIVEMETHOD>*</NATIVEMETHOD></COLLECTION>",
    "<NATIVEMETHOD> AllLedgerEntries.* </NATIVEMETHOD>",
    "<FETCHLIST><FETCH>*</FETCH></FETCHLIST>",
    "<SYSTEM>$$InDateRange:$Date:$$Date:1:$$Date:2</SYSTEM>",
    "<system>$$indaterange</system>",
    '<NATIVEMETHOD TYPE="String">*</NATIVEMETHOD>',
    "<FETCH >*</FETCH>",
    "<NATIVEMETHOD>&#42;</NATIVEMETHOD>",
    "<FETCH>&#x2A;</FETCH>",
])
def test_forbidden_requests_refused(xml):
    with pytest.raises(GuardError):
        check_request(xml)


def test_native_method_with_attribute_and_real_value_allowed():
    check_request('<NATIVEMETHOD TYPE="String">GUID</NATIVEMETHOD>')


def test_clean_request_allowed():
    check_request("<NATIVEMETHOD>GUID</NATIVEMETHOD><SYSTEM>$AlterID > 5</SYSTEM>")


def test_company_guard_cases():
    check_company([A], A, mutating=False)
    check_company([A], A, mutating=True)
    with pytest.raises(GuardError, match="No company open"):
        check_company([], A, mutating=False)
    with pytest.raises(GuardError, match="2 companies are loaded"):
        check_company([A, "Other"], A, mutating=False)
    with pytest.raises(GuardError, match="expects"):
        check_company(["Bharat Traders Private Limited"], A, mutating=False)


def test_mutation_guard_needs_probe_in_name():
    with pytest.raises(GuardError, match="only companies with 'Probe'"):
        check_company(["Bharat Traders Private Limited"], "Bharat Traders Private Limited", mutating=True)


def test_check_mutation_allowed_standalone():
    check_mutation_allowed(A, mutating=True)
    check_mutation_allowed("Plain Co", mutating=False)
    with pytest.raises(GuardError, match="only companies with 'Probe'"):
        check_mutation_allowed("Plain Co", mutating=True)

"""SEC EDGAR CIK lookup and filing retrieval, adapted for use inside the
DocumentRetrieval Lambda.

Adapted from /app.py at the repo root -- keep in sync intentionally. The root
file is a standalone script (it instantiates SecEdgar and hits the network at
module level); this copy must never do that, since Lambda would re-run any
module-level code on every cold start. Differences from the root version:
  - from_dict() is the only constructor doc_retrieval uses (the ticker list
    is read from the S3 cache that EdgarFileRefresh populates, not fetched
    fresh from sec.gov on every request).
  - Every requests.get() call has an explicit timeout, so a slow/unresponsive
    SEC server raises requests.exceptions.Timeout instead of hanging until
    Lambda's own function timeout kills the process with no clean error.
  - _company_recent_filings() calls raise_for_status() (missing in the root
    version), so a non-200 from data.sec.gov raises instead of silently
    producing a bad JSON parse.
  - get_filing_content() uses BeautifulSoup's stdlib "html.parser" instead of
    "lxml" -- lxml is a C extension; a wheel pip-installed on a Mac may not
    match Lambda's Linux runtime unless built with `sam build --use-container`.
"""
import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = (5, 15)  # (connect, read) seconds


class SecEdgar:
    USER_AGENT = "NYU jj3945@nyu.edu"

    def __init__(self, fileurl):
        self.fileurl = fileurl
        self.name_dict = {}
        self.ticker_dict = {}

        headers = {"user-agent": self.USER_AGENT}
        r = requests.get(self.fileurl, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        self.filejson = r.json()
        self.cik_json_to_dict()

    @classmethod
    def from_dict(cls, filejson):
        """Build a SecEdgar instance from already-fetched JSON, skipping the network call in __init__."""
        instance = cls.__new__(cls)
        instance.fileurl = None
        instance.filejson = filejson
        instance.name_dict = {}
        instance.ticker_dict = {}
        instance.cik_json_to_dict()
        return instance

    def cik_json_to_dict(self):
        self.name_dict = {
            entry["title"]: [entry["cik_str"], entry["title"], entry["ticker"]]
            for entry in self.filejson.values()
        }
        self.ticker_dict = {
            entry["ticker"]: [entry["cik_str"], entry["title"], entry["ticker"]]
            for entry in self.filejson.values()
        }

    def name_to_cik(self, name):
        if name not in self.name_dict:
            raise KeyError(f"Name '{name}' not found in EDGAR data")
        return tuple(self.name_dict[name])

    def ticker_to_cik(self, ticker):
        if ticker not in self.ticker_dict:
            raise KeyError(f"Ticker '{ticker}' not found in EDGAR data")
        return tuple(self.ticker_dict[ticker])

    def _company_recent_filings(self, cik):
        headers = {"user-agent": self.USER_AGENT}
        padded_cik = "0" * (10 - len(cik)) + cik
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{padded_cik}.json",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _filing_url(self, cik, accession_number, primary_document):
        accession_number = accession_number.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"

    def _filter_filings(self, cik, form, year, quarter=None):
        filings = self._company_recent_filings(cik)
        recent = filings["filings"]["recent"]
        year = str(year)
        results = []

        for i in range(len(recent["accessionNumber"])):
            filing_date = recent["filingDate"][i]
            if recent["form"][i] != form or filing_date[:4] != year:
                continue
            if quarter is not None and (int(filing_date[5:7]) - 1) // 3 + 1 != quarter:
                continue

            results.append({
                "form": recent["form"][i],
                "filingDate": filing_date,
                "accessionNumber": recent["accessionNumber"][i],
                "primaryDocument": recent["primaryDocument"][i],
                "url": self._filing_url(cik, recent["accessionNumber"][i], recent["primaryDocument"][i]),
            })

        return results

    def annual_filing(self, cik, year):
        return self._filter_filings(cik, "10-K", year)

    def quarterly_filing(self, cik, year, quarter):
        return self._filter_filings(cik, "10-Q", year, quarter)

    def get_filing_content(self, cik, accession_number, primary_document):
        headers = {"user-agent": self.USER_AGENT}
        file_url = self._filing_url(cik, accession_number, primary_document)
        r = requests.get(file_url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        for hidden in soup.select('[style*="display:none"], [style*="display: none"]'):
            hidden.decompose()

        return soup.get_text(separator="\n", strip=True)

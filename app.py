import requests
from bs4 import BeautifulSoup

class SecEdgar:
    # EDGAR_TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'
    USER_AGENT = "NYU jj3945@nyu.edu"

    def __init__(self, fileurl):
        self.fileurl = fileurl
        self.name_dict = {}
        self.ticker_dict = {}

        headers = {'user-agent': self.USER_AGENT, 'Accept-Encoding': 'gzip', 'Host': 'www.sec.gov'}
        r = requests.get(self.fileurl, headers=headers)

        self.filejson = r.json()

        # print(r.text)
        # print(self.filejson)

        self.cik_json_to_dict()

    def cik_json_to_dict(self):
            self.name_dict = {
                entry['title']: [entry['cik_str'], entry['title'], entry['ticker']] for entry in self.filejson.values()
                }
            
            self.ticker_dict = {
                entry['ticker']: [entry['cik_str'], entry['title'], entry['ticker']] for entry in self.filejson.values()
                }

    def name_to_cik(self, name):
        if name not in self.name_dict:
            raise KeyError(f"Ticker '{name}' not found in EDGAR data")
        return tuple(self.name_dict[name])
    
    def ticker_to_cik(self, ticker):
        if ticker not in self.ticker_dict:
            raise KeyError(f"Ticker '{ticker}' not found in EDGAR data")
        return tuple(self.ticker_dict[ticker])
    
    def _company_recent_filings(self, cik):
        headers = {"user-agent": self.USER_AGENT}
        r = requests.get(f"https://data.sec.gov/submissions/CIK{"0" * (10 - len(cik))}{cik}.json", headers=headers)
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
        r = requests.get(file_url, headers=headers)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        for hidden in soup.select('[style*="display:none"], [style*="display: none"]'):
            hidden.decompose()
            
        return soup.get_text(separator="\n", strip=True)


se = SecEdgar('https://www.sec.gov/files/company_tickers.json')

# cik = se.name_to_cik('NVIDIA CORP')
# print(cik)

# cik = se.ticker_to_cik('NVDA')
# print(cik)

# cik = se.annual_filing("1045810", 2024)
# print(cik)

# cik = se.quarterly_filing("1045810", 2025, 3)
# print(cik)

filing_content = se.get_filing_content("1045810", '0001045810-25-000209', 'nvda-20250727.htm')
print(filing_content)

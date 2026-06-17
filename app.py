import requests

class SecEdgar:
    # EDGAR_TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'

    def __init__(self, fileurl):
        self.fileurl = fileurl
        self.name_dict = {}
        self.ticker_dict = {}

        headers = {'user-agent': 'NYU jj3945@nyu.edu', 'Accept-Encoding': 'gzip', 'Host': 'www.sec.gov'}
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

se = SecEdgar('https://www.sec.gov/files/company_tickers.json')

cik = se.name_to_cik('NVIDIA CORP')
print(cik)

cik = se.ticker_to_cik('NVDA')
print(cik)

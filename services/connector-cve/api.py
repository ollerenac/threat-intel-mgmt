import time

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, ConnectionError as RequestsConnectionError
from urllib3.util import Retry

from .endpoints import BASE_URL


class CVEClient:
    def __init__(self, api_key, helper, header):
        headers = {"Bearer": api_key, "User-Agent": header}
        self.token = api_key
        self.helper = helper
        self.session = requests.Session()
        self.session.headers.update(headers)

    @staticmethod
    def _request_data(self, api_url: str, params=None):
        try:
            response = self.request(api_url, params)
            self.helper.log_info(f"[API] HTTP Get Request to endpoint for path ({api_url})")
            response.raise_for_status()
            return response
        except requests.RequestException as err:
            self.helper.log_error(f"[API] Error while fetching data from {api_url}: {str(err)}")
            return None

    def request(self, api_url, params):
        retry_strategy = Retry(
            total=4,
            backoff_factor=6,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # ponytail: retry on connection/timeout errors — NVD drops or stalls large responses
        for attempt in range(5):
            try:
                response = self.session.get(api_url, params=params, timeout=180)
                if response.status_code == 200:
                    time.sleep(6)
                    return response
                raise Exception("[API] Attempting to retrieve data failed. Wait for connector to re-run...")
            except (ChunkedEncodingError, RequestsConnectionError):
                if attempt == 4:
                    raise
                wait = 20 * (attempt + 1)
                self.helper.log_warning(f"[API] Network error (attempt {attempt + 1}/5), retrying in {wait}s...")
                time.sleep(wait)

    def get_complete_collection(self, cve_params=None):
        try:
            response = self._request_data(self, BASE_URL, params=cve_params)
            cve_collection = response.json()
            return cve_collection
        except Exception as err:
            self.helper.log_error(err)

import sys
import time
from datetime import datetime, timedelta

from pycti import OpenCTIConnectorHelper  # type: ignore
from services import CVEConverter  # type: ignore
from services.utils import MAX_AUTHORIZED, ConfigCVE  # type: ignore


class CVEConnector:
    def __init__(self):
        self.config = ConfigCVE()
        self.helper = OpenCTIConnectorHelper(self.config.load)
        self.converter = CVEConverter(self.helper)

    def run(self) -> None:
        self.helper.log_info("[CONNECTOR] Fetching datasets...")
        get_run_and_terminate = getattr(self.helper, "get_run_and_terminate", None)
        if callable(get_run_and_terminate) and self.helper.get_run_and_terminate():
            self.process_data()
            self.helper.force_ping()
        else:
            while True:
                self.process_data()
                time.sleep(60)

    def _initiate_work(self, timestamp: int) -> str:
        now = datetime.utcfromtimestamp(timestamp)
        friendly_name = f"{self.helper.connect_name} run @ " + now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        work_id = self.helper.api.work.initiate_work(
            self.helper.connect_id, friendly_name
        )
        self.helper.log_info(f"[CONNECTOR] New work '{work_id}' initiated...")
        return work_id

    def update_connector_state(self, current_time: int, work_id: str) -> None:
        msg = (
            f"[CONNECTOR] Connector successfully run, storing last_run as "
            f"{datetime.utcfromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.helper.log_info(msg)
        self.helper.api.work.to_processed(work_id, msg)
        self.helper.set_state({"last_run": current_time})
        interval_in_hours = round(self.config.interval / 60 / 60, 2)
        self.helper.log_info(
            "[CONNECTOR] Last_run stored, next run in: "
            + str(interval_in_hours)
            + " hours"
        )

    def _import_recent(self, now: datetime, work_id: str) -> None:
        if self.config.max_date_range > MAX_AUTHORIZED:
            raise Exception(
                "The max_date_range cannot exceed {} days".format(MAX_AUTHORIZED)
            )
        date_range = timedelta(days=self.config.max_date_range)
        start_date = now - date_range
        cve_params = self._update_cve_params(start_date, now)
        self.converter.send_bundle(cve_params, work_id)

    def _import_history(
        self, start_date: datetime, end_date: datetime, work_id: str
    ) -> None:
        years = range(start_date.year, end_date.year + 1)
        start, end = start_date, end_date + timedelta(1)

        for year in years:
            year_start = datetime(year, 1, 1, 0, 0)
            year_end = datetime(year + 1, 1, 1, 0, 0)

            date_range = min(end, year_end) - max(start, year_start)
            days_in_year = date_range.days

            if year == end_date.year:
                date_range = end_date - year_start
                days_in_year = date_range.days

            start_date_current_year = year_start

            while days_in_year > 0:
                end_date_current_year = start_date_current_year + timedelta(
                    days=MAX_AUTHORIZED
                )
                self.helper.log_info(
                    f"[CONNECTOR] Connector retrieve CVE history for year {year}, "
                    f"{days_in_year} days left"
                )

                if year == end_date.year and days_in_year < MAX_AUTHORIZED:
                    end_date_current_year = start_date_current_year + timedelta(
                        days=days_in_year
                    )
                    cve_params = self._update_cve_params(
                        start_date_current_year, end_date_current_year
                    )
                    self.converter.send_bundle(cve_params, work_id)
                    days_in_year = 0

                if days_in_year > 6:
                    cve_params = self._update_cve_params(
                        start_date_current_year, end_date_current_year
                    )
                    self.converter.send_bundle(cve_params, work_id)
                    start_date_current_year += timedelta(days=MAX_AUTHORIZED)
                    days_in_year -= MAX_AUTHORIZED
                else:
                    end_date_current_year = start_date_current_year + timedelta(
                        days=days_in_year
                    )
                    cve_params = self._update_cve_params(
                        start_date_current_year, end_date_current_year
                    )
                    self.converter.send_bundle(cve_params, work_id)
                    days_in_year = 0

            self.helper.log_info(
                f"[CONNECTOR] Importing CVE history for year {year} finished"
            )

    def _maintain_data(self, now: datetime, last_run: float, work_id: str) -> None:
        self.helper.log_info("[CONNECTOR] Getting the last CVEs since the last run...")
        last_run_ts = datetime.utcfromtimestamp(last_run)
        cve_params = self._update_cve_params(last_run_ts, now)
        self.converter.send_bundle(cve_params, work_id)

    @staticmethod
    def _update_cve_params(start_date: datetime, end_date: datetime) -> dict:
        # ponytail: pubStartDate not lastModStartDate — lastMod fires on bulk rejections
        # and unscored submissions, leaving cvssMetricV31 filter with 0 results.
        # pubStartDate windows that are weeks old reliably have CVSS 3.1 scores.
        return {
            "pubStartDate": start_date.isoformat(),
            "pubEndDate": end_date.isoformat(),
        }

    def process_data(self) -> None:
        try:
            now = datetime.now()
            current_time = int(datetime.timestamp(now))
            current_state = self.helper.get_state()

            if current_state is not None and "last_run" in current_state:
                last_run = current_state["last_run"]
                self.helper.log_info(
                    "[CONNECTOR] Connector last run: "
                    + datetime.utcfromtimestamp(last_run).strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                last_run = None
                self.helper.log_info("[CONNECTOR] Connector has never run...")

            if last_run is None:
                work_id = self._initiate_work(current_time)
                if self.config.pull_history:
                    start_date = datetime(self.config.history_start_year, 1, 1)
                    end_date = now
                    self._import_history(start_date, end_date, work_id)
                else:
                    self._import_recent(now, work_id)
                self.update_connector_state(current_time, work_id)

            elif (
                last_run is not None
                and self.config.maintain_data
                and (current_time - last_run) >= int(self.config.interval)
            ):
                work_id = self._initiate_work(current_time)
                self._maintain_data(now, last_run, work_id)
                self.update_connector_state(current_time, work_id)

            else:
                new_interval = self.config.interval - (current_time - last_run)
                new_interval_in_hours = round(new_interval / 60 / 60, 2)
                self.helper.log_info(
                    "[CONNECTOR] Connector will not run, next run in: "
                    + str(new_interval_in_hours)
                    + " hours"
                )

            time.sleep(5)

        except (KeyboardInterrupt, SystemExit):
            self.helper.log_info("[CONNECTOR] Connector stop...")
            sys.exit(0)
        except Exception as e:
            self.helper.log_error(f"[CONNECTOR] Error while processing data: {str(e)}")

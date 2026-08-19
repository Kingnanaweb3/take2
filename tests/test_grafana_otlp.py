import os
import time
from dotenv import load_dotenv

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

import logging

load_dotenv()

# --- Metrics setup ---
metric_exporter = OTLPMetricExporter()
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=1000)
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
meter = metrics.get_meter("take2.smoke_test")
verdict_counter = meter.create_counter("take2_verdict_count", description="Test counter")

# --- Logs setup ---
logger_provider = LoggerProvider()
set_logger_provider(logger_provider)
log_exporter = OTLPLogExporter()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
py_logger = logging.getLogger("take2.smoke_test")
py_logger.setLevel(logging.INFO)
py_logger.addHandler(handler)

def main():
    verdict_counter.add(1, {"agent": "smoke_test", "verdict": "cleared"})
    py_logger.info("Take2 smoke test: audit trail entry — smoke_test_agent flagged nothing, verdict=cleared")

    print("Pushed 1 metric + 1 log line via OTLP. Waiting for export flush...")
    time.sleep(3)  # give the periodic exporter time to flush before exit
    print("Done. Check your Grafana dashboard/Explore view for 'take2_verdict_count' and the log line.")

if __name__ == "__main__":
    main()
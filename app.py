import logging
import os
import uuid
from flask import Flask, jsonify, request, make_response

# OpenTelemetry Instrumentation
from opentelemetry.trace import get_tracer_provider
from opentelemetry.instrumentation.requests import RequestsInstrumentor
RequestsInstrumentor().instrument()
# End of OpenTelemetry Instrumentation

# System Performance
from opentelemetry.metrics import set_meter_provider
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
exporter = ConsoleMetricExporter()
set_meter_provider(MeterProvider([PeriodicExportingMetricReader(exporter)]))
SystemMetricsInstrumentor().instrument()
configuration = {
    "system.memory.usage": ["used", "free", "cached"],
    "system.cpu.time": ["idle", "user", "system", "irq"],
    "system.network.io": ["transmit", "receive"],
    "process.memory.usage": None,
    "process.memory.virtual": None,
    "process.cpu.time": ["user", "system"],
    "process.context_switches": ["involuntary", "voluntary"],
}
# end of System Performance

log_level = os.getenv("APP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logging.getLogger('werkzeug').setLevel(getattr(logging, log_level, logging.INFO))
app = Flask(__name__)
redis_client = None
INTERNAL_ERROR = "INTERNAL SERVER ERROR"


def get_env_variable(var_name, default=None):
    value = os.environ.get(var_name)
    if value is None:
        if default is not None:
            return default
        else:
            raise ValueError(f"Environment variable '{var_name}' not set.")
    return value

def request_log(component: str, payload:dict = None ):
    transaction_id = str(uuid.uuid4())
    request_message = {
        'message': 'Request',
        'component': component,
        'transactionId': transaction_id
    }
    if payload:
        request_message['payload'] = payload
    logging.info(request_message)
    return transaction_id


def response_log(transaction_id:str, component: str, return_code, payload:dict = None):
    response_message = {
        'message': 'Response',
        'component': component,
        'transactionId': transaction_id,
        'returnCode': return_code
    }
    if payload:
        response_message['payload'] = payload
    logging.info(response_message)


@app.route("/login", methods=["POST"])
def login():
    return_code = 200
    component = 'login'
    transaction_id = None
    try:
        data = request.get_json()
        user_id = data.get("userId", None)
        payload = {
            'userId': user_id,
        }
        transaction_id = request_log(component, payload)
        if not user_id:
            return_code = 400
        else:
            url = get_env_variable("AUTHENTICATION_URL")
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                payload = response.json()
            else:
                return_code = response.status_code
                payload = {"error": "Error from authenticate service", "returnCode": response.status_code}
    except Exception as ex:
        return_code = 500
        payload = {"error": INTERNAL_ERROR, "details": str(ex)}
    response_log(transaction_id, component, return_code, payload)
    return make_response(jsonify(payload), return_code)

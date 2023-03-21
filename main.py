import base64
import logging
import os
import json

from fastapi import Body, FastAPI

# heavily cribbed from https://github.com/k-mitevski/kubernetes-mutating-webhook

app = FastAPI()

logger = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.removeHandler(
    uvicorn_logger.handlers[0]
)  # Turn off uvicorn duplicate log
logger.setLevel(int(os.getenv("PYTHON_LOG_LEVEL", logging.INFO)))
logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s")

_stack = os.environ["STACK"]
_environment = os.environ["ENVIRONMENT"]


def patch(object_in: dict, environment: str, stack: str, k8s_app: str) -> list[dict]:
    annot = "sumologic.com~1sourceCategory"  # you represent an in-line '/' as '~1' in json patch
    value = f"{environment}/{k8s_app}/{k8s_app}-{stack}/{k8s_app}"
    if object_in["metadata"].get("annotations", {}).get(annot):
        return []

    return [
        {
            "op": "add",
            "path": f"/metadata/annotations/{annot}",
            "value": value,
        }
    ]


@app.post("/mutate")
def mutate_request(
    request: dict = Body(...),
) -> dict:
    global _stack, _environment
    uid = request["request"]["uid"]
    object_in = request["request"]["object"]

    try:
        k8s_app = object_in["metadata"]["labels"].get(
            "app.kubernetes.io/name",
            "-".join(object_in["metadata"]["generateName"].split("-")[:-2]),
        )
        logging.debug(f"k8s_app:{k8s_app}")
    except KeyError:
        message = (
            f"Unable to retrieve app name from pod {object_in['metadata']['generateName']} in "
            f"namespace {object_in['metadata'].get('namespace', 'default')}"
        )
        return {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": True,
                "status": {"message": message},
            },
        }

    message = (
        f'Applying annotation for {object_in["kind"]}/{k8s_app} '
        f'in ns {object_in["metadata"].get("namespace", "default")}.'
    )
    logger.info(message)

    p = patch(
        object_in=object_in,
        stack=_stack,
        environment=_environment,
        k8s_app=k8s_app,
    )
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True,
            "patchType": "JSONPatch",
            "status": {"message": message},
            "patch": base64.b64encode(json.dumps(p).encode("UTF-8")),
        },
    }


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "OK"}

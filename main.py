import base64
from pprint import pformat as pf
import logging
import os

from fastapi import Body, FastAPI

app = FastAPI()

webhook = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.removeHandler(
    uvicorn_logger.handlers[0]
)  # Turn off uvicorn duplicate log
webhook.setLevel(logging.INFO)
logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s")


def patch(object_in: dict, environment: str, stack: str, k8s_app: str) -> list[dict]:
    annot = "sumologic.com/sourceCategory"
    value = f"{environment}/{k8s_app}/{k8s_app}-{stack}/{k8s_app}"
    if object_in["metadata"].get("annotations", {}).get(annot):
        op = "patch"
    else:
        op = "add"
    return [
        {
            "op": op,
            "path": f"/metadata/annotations/{annot}",
            "value": value,
        }
    ]


@app.post("/mutate")
def mutate_request(request: dict = Body(...)) -> dict:
    logging.info(pf(request))
    uid = request["request"]["uid"]
    object_in = request["request"]["object"]
    stack = os.environ["STACK"]
    environment = os.environ["ENVIRONMENT"]
    try:
        k8s_app = request["metadata"]["labels"]["app.kubernetes.io/name"]
    except KeyError:
        message = (
            f"Unable to retrieve label `app.kubernetes.io/name` from pod {object_in['metadata']['name']} in "
            f"namespace {object_in['metadata'].get('namespace', 'default')}"
        )
        return {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": False,
                "status": {"message": message},
            },
        }

    message = (
        f'Applying annotation for {object_in["kind"]}/{object_in["metadata"]["name"]} '
        f'in ns {object_in["metadata"].get("namespace", "default")}.'
    )
    webhook.info(message)

    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True,
            "patchType": "JSONPatch",
            "status": {"message": message},
            "patch": base64.b64encode(
                patch(
                    object_in=object_in,
                    stack=stack,
                    environment=environment,
                    k8s_app=k8s_app,
                )
            ),
        },
    }


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "OK"}

import base64
from pprint import pformat as pf
import logging
import os
import sys
import json

from fastapi import Body, FastAPI, HTTPException

app = FastAPI()

webhook = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.removeHandler(
    uvicorn_logger.handlers[0]
)  # Turn off uvicorn duplicate log
webhook.setLevel(logging.INFO)
logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s")


def patch(object_in: dict, environment: str, stack: str, k8s_app: str) -> list[dict]:
    annot = "sumologic.com~1sourceCategory"
    # annot = "foo"
    value = f"{environment}/{k8s_app}/{k8s_app}-{stack}/{k8s_app}"
    if object_in["metadata"].get("annotations", {}).get(annot):
        return []
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
    with open("/tmp/req", encoding="UTF-8", mode="w") as fp:
        print(json.dumps(request), file=fp)

    uid = request["request"]["uid"]
    object_in = request["request"]["object"]
    stack = os.environ["STACK"]
    environment = os.environ["ENVIRONMENT"]
    uvicorn_logger.info(pf(request))

    try:
        k8s_app = object_in["metadata"]["labels"]["app.kubernetes.io/name"]
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
        f'Applying annotation for {object_in["kind"]}/{k8s_app} '
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
                json.dumps(patch(
                    object_in=object_in,
                    stack=stack,
                    environment=environment,
                    k8s_app=k8s_app,
                )).encode("UTF-8")
            ),
        },
    }


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "OK"}
